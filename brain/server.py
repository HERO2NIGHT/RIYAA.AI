from flask import Flask, jsonify
from flask_cors import CORS
import logging
import threading
import time
import json
import numpy as np
import ollama
import asyncio
import edge_tts
import pygame
import os
import wave
import camera
import sounddevice as sd
from faster_whisper import WhisperModel
from ddgs import DDGS
import memory

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

pygame.mixer.init()

VOICE_MAP = {"en": "en-US-AriaNeural", "hi": "hi-IN-SwaraNeural", "kn": "kn-IN-SapnaNeural"}
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada"}

whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")

avatar_state = {
    "speaking": False, "mouth": 0.0, "emotion": "neutral",
    "user_waving": False, "last_reply": "", "play_video": False
}

is_awake = False

CORRECTIONS_PATH = os.path.join(os.path.dirname(__file__), "corrections.json")
CLAP_AMPLITUDE_THRESHOLD = 20000
CLAP_MAX_DURATION_SAMPLES = int(0.15 * 16000)

def load_corrections():
    try:
        with open(CORRECTIONS_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"en": {}, "hi": {}, "kn": {}}

def apply_corrections(text, lang):
    corrections = load_corrections()
    lang_map = corrections.get(lang, {})
    for wrong, right in lang_map.items():
        if wrong.lower() in text.lower():
            text = text.replace(wrong, right)
    return text

def detect_clap(audio_data):
    audio_data = np.abs(audio_data.flatten())
    above = np.where(audio_data > CLAP_AMPLITUDE_THRESHOLD)[0]
    if len(above) == 0:
        return False
    spread = above[-1] - above[0]
    return spread < CLAP_MAX_DURATION_SAMPLES and len(above) > 5

def record_audio(filename="input.wav", duration=5, samplerate=16000):
    print("Listening... (speak now)")
    audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16', device=2)
    sd.wait()
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(audio.tobytes())
    return filename

def listen_for_wake():
    audio = sd.rec(int(1.5 * 16000), samplerate=16000, channels=1, dtype='int16', device=2)
    sd.wait()

    if detect_clap(audio):
        return True, "clap"

    with wave.open("wake_check.wav", "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(16000)
        wf.writeframes(audio.tobytes())

    segments, info = whisper_model.transcribe("wake_check.wav", language="en")
    text = " ".join([s.text for s in segments]).strip().lower()
    if "wake up" in text:
        return True, "voice"

    return False, None

def detect_script_language(text):
    for char in text:
        code = ord(char)
        if 0x0900 <= code <= 0x097F:
            return "hi"
        if 0x0C80 <= code <= 0x0CFF:
            return "kn"
    return None

def listen():
    audio_file = record_audio()

    best_text = ""
    best_lang = "en"
    best_score = -999

    for lang in ["en", "hi", "kn"]:
        segments, info = whisper_model.transcribe(audio_file, language=lang)
        segs = list(segments)
        text = " ".join([s.text for s in segs]).strip()
        if not text:
            continue
        avg_logprob = sum(s.avg_logprob for s in segs) / len(segs)
        if avg_logprob > best_score:
            best_score = avg_logprob
            best_text = text
            best_lang = lang

    script_lang = detect_script_language(best_text)
    final_lang = script_lang if script_lang else best_lang

    final_text = apply_corrections(best_text, final_lang)

    return final_text, final_lang

async def speak(text, voice):
    if not text.strip():
        return
    output_file = "reply.mp3"
    word_boundaries = []

    try:
        communicate = edge_tts.Communicate(text, voice)
        with open(output_file, "wb") as f:
            async for chunk in communicate.stream():
                if chunk["type"] == "audio":
                    f.write(chunk["data"])
                elif chunk["type"] == "WordBoundary":
                    word_boundaries.append({
                        "offset": chunk["offset"] / 10_000_000,
                        "duration": chunk["duration"] / 10_000_000
                    })

        avatar_state["speaking"] = True

        pygame.mixer.music.load(output_file)
        start_time = time.time()
        pygame.mixer.music.play()

        wb_index = 0
        while pygame.mixer.music.get_busy():
            elapsed = time.time() - start_time

            if wb_index < len(word_boundaries):
                wb = word_boundaries[wb_index]
                if wb["offset"] <= elapsed <= wb["offset"] + wb["duration"]:
                    avatar_state["mouth"] = 0.7
                elif elapsed > wb["offset"] + wb["duration"]:
                    wb_index += 1
                    avatar_state["mouth"] = 0.15
                else:
                    avatar_state["mouth"] = 0.15
            else:
                avatar_state["mouth"] = 0.15

            pygame.time.Clock().tick(30)

        avatar_state["speaking"] = False
        avatar_state["mouth"] = 0.0
        pygame.mixer.music.unload()
        os.remove(output_file)

    except Exception as e:
        print(f"(Voice failed) — {e}")
        avatar_state["speaking"] = False
        avatar_state["mouth"] = 0.0

@app.route("/status")
def status():
    return jsonify(avatar_state)

@app.route("/video_done", methods=["POST"])
def video_done():
    avatar_state["play_video"] = False
    return jsonify({"ok": True})

def needs_fact_check(text):
    factual_triggers = [
        "what is", "what are", "who is", "who was", "when did", "when is",
        "where is", "how many", "how much", "which", "why does", "why is",
        "capital of", "population of", "latest", "current", "price of",
        "kya hai", "kaun hai", "kab", "kahan", "kitne"
    ]
    lowered = text.lower()
    return any(trigger in lowered for trigger in factual_triggers)

def search_facts(query, max_results=2):
    try:
        results = DDGS().text(query, max_results=max_results, timelimit=None)
        summaries = []
        for r in results:
            summaries.append(f"- {r['title']}: {r['body'][:120]}")
        return "\n".join(summaries) if summaries else None
    except Exception as e:
        print(f"(Search failed: {e})")
        return None

def extract_facts(user_msg, ai_msg):
    try:
        fact_check = ollama.chat(
            model="llama3.2:3b",
            messages=[{
                "role": "user",
                "content": (
                    f"User said: {user_msg}\n"
                    f"If this reveals a personal fact worth remembering long-term "
                    f"(like their name, job, likes, dislikes, or important details), "
                    f"reply with just that fact in one short sentence. "
                    f"If there's nothing worth remembering, reply with exactly: NONE"
                )
            }],
            options={"num_predict": 20}
        )
        result = fact_check["message"]["content"].strip()
        if result and result.upper() != "NONE":
            memory.save_fact(result)
            print(f"(Remembered: {result})")
    except Exception as e:
        print(f"(Fact extraction failed: {e})")

def detect_emotion(text):
    lowered = text.lower()
    if "?" in text:
        return "curious"
    if "!" in text or any(w in lowered for w in ["great", "awesome", "love", "happy", "yay", "nice", "good"]):
        return "happy"
    if any(w in lowered for w in ["sorry", "sad", "unfortunately", "worried"]):
        return "concerned"
    return "neutral"

def say_goodbye(lang_code):
    goodbye_text = {
        "en": "Goodbye! Take care.",
        "hi": "अलविदा! अपना ख्याल रखना।",
        "kn": "ವಿದಾಯ! ನಿಮ್ಮ ಬಗ್ಗೆ ಕಾಳಜಿ ವಹಿಸಿ."
    }
    text = goodbye_text.get(lang_code, goodbye_text["en"])
    asyncio.run(speak(text, VOICE_MAP.get(lang_code, VOICE_MAP["en"])))

def chat_loop():
    global is_awake
    memory.init_db()

    known_facts = memory.load_facts()
    facts_text = ""
    if known_facts:
        facts_text = "\nThings you know about the user:\n" + "\n".join(f"- {f}" for f in known_facts)

    conversation = [
        {
            "role": "system",
            "content": (
                "You are a warm, friendly AI companion. "
                "Reply in ONE short sentence only. Never more than one sentence. "
                "Be sweet, casual, and cool — no long explanations, no lists. "
                "IMPORTANT: Always reply in the SAME language the user spoke in "
                "(English, Hindi, or Kannada). Do not switch languages."
                + facts_text
            )
        }
    ]
    conversation.extend(memory.load_recent_history(limit=10))

    print("Sleeping... clap or say 'wake up' to activate.\n")

    turn_count = 0

    while True:
        if not is_awake:
            woke, method = listen_for_wake()
            if woke:
                is_awake = True
                print(f"Awake! (triggered by {method})\n")
                asyncio.run(speak("I'm here!", VOICE_MAP["en"]))
            continue

        user_input, detected = listen()
        print(f"You said ({detected}): {user_input}")

        if not user_input:
            continue

        lang_code = detected if detected in VOICE_MAP else "en"

        if "quit" in user_input.lower() or "stop" in user_input.lower():
            print("Goodbye!")
            say_goodbye(lang_code)
            is_awake = False
            print("Sleeping... clap or say 'wake up' to activate.\n")
            continue

        if "let's go" in user_input.lower() or "lets go" in user_input.lower():
            print("Playing video...")
            avatar_state["play_video"] = True
            continue

        if needs_fact_check(user_input):
            print("Checking facts...")
            facts = search_facts(user_input)
            if facts:
                grounded_prompt = (
                    f"User asked: {user_input}\n"
                    f"Search results:\n{facts}\n"
                    f"Answer in ONE short sentence using this info."
                )
                conversation.append({"role": "user", "content": grounded_prompt})
            else:
                conversation.append({"role": "user", "content": user_input})
        else:
            conversation.append({"role": "user", "content": user_input})

        memory.save_message("user", user_input)

        response = ollama.chat(
            model="llama3.2:3b",
            messages=conversation,
            options={"num_predict": 25},
            keep_alive="30m"
        )
        ai_reply = response["message"]["content"]
        avatar_state["emotion"] = detect_emotion(ai_reply)
        print(f"AI ({LANGUAGE_NAMES.get(lang_code, 'English')}): {ai_reply}\n")

        conversation.append({"role": "assistant", "content": ai_reply})
        memory.save_message("assistant", ai_reply)
        avatar_state["last_reply"] = ai_reply

        asyncio.run(speak(ai_reply, voice=VOICE_MAP[lang_code]))

        turn_count += 1
        if turn_count % 4 == 0:
            extract_facts(user_input, ai_reply)

if __name__ == "__main__":
    threading.Thread(target=chat_loop, daemon=True).start()
    threading.Thread(target=camera.start_camera_thread, args=(avatar_state,), daemon=True).start()
    app.run(port=5050)
