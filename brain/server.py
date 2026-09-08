from flask import Flask, jsonify
from flask_cors import CORS
import logging
import threading
import ollama
import asyncio
import edge_tts
import pygame
import os
import wave
import sounddevice as sd
from faster_whisper import WhisperModel
from duckduckgo_search import DDGS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

log = logging.getLogger('werkzeug')
log.setLevel(logging.ERROR)

pygame.mixer.init()

VOICE_MAP = {"en": "en-US-AriaNeural", "hi": "hi-IN-SwaraNeural", "kn": "kn-IN-SapnaNeural"}
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada"}

whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")

avatar_state = {"speaking": False, "last_reply": ""}

def record_audio(filename="input.wav", duration=5, samplerate=16000):
    print("Listening... (speak now)")
    audio = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
    sd.wait()
    with wave.open(filename, 'wb') as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(samplerate)
        wf.writeframes(audio.tobytes())
    return filename

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
    segments, info = whisper_model.transcribe(audio_file, language=None)
    text = " ".join([seg.text for seg in segments]).strip()
    script_lang = detect_script_language(text)
    final_lang = script_lang if script_lang else info.language
    return text, final_lang

async def speak(text, voice):
    if not text.strip():
        return
    output_file = "reply.mp3"
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        avatar_state["speaking"] = True
        pygame.mixer.music.load(output_file)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        avatar_state["speaking"] = False
        pygame.mixer.music.unload()
        os.remove(output_file)
    except Exception as e:
        print(f"(Voice failed) — {e}")
        avatar_state["speaking"] = False

@app.route("/status")
def status():
    return jsonify(avatar_state)

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

def chat_loop():
    conversation = [
        {
            "role": "system",
            "content": (
                "You are a warm, friendly AI companion. "
                "Reply in ONE short sentence only. Never more than one sentence. "
                "Be sweet, casual, and cool — no long explanations, no lists. "
                "IMPORTANT: Always reply in the SAME language the user spoke in "
                "(English, Hindi, or Kannada). Do not switch languages."
            )
        }
    ]

    print("Your AI is ready. Speak, or say 'quit' or 'stop' to exit.\n")

    while True:
        user_input, detected = listen()
        print(f"You said ({detected}): {user_input}")

        if not user_input:
            continue
        if "quit" in user_input.lower() or "stop" in user_input.lower():
            print("Goodbye!")
            break

        lang_code = detected if detected in VOICE_MAP else "en"

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

        response = ollama.chat(
            model="llama3.2:3b",
            messages=conversation,
            options={"num_predict": 40}
        )
        ai_reply = response["message"]["content"]
        print(f"AI ({LANGUAGE_NAMES.get(lang_code, 'English')}): {ai_reply}\n")

        conversation.append({"role": "assistant", "content": ai_reply})
        avatar_state["last_reply"] = ai_reply

        asyncio.run(speak(ai_reply, voice=VOICE_MAP[lang_code]))

if __name__ == "__main__":
    threading.Thread(target=chat_loop, daemon=True).start()
    app.run(port=5050)
