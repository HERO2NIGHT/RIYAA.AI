import ollama
import asyncio
import edge_tts
import pygame
import os
import wave
import sounddevice as sd
from faster_whisper import WhisperModel

pygame.mixer.init()

# ---- Voice map for text-to-speech ----
VOICE_MAP = {
    "en": "en-US-AriaNeural",
    "hi": "hi-IN-SwaraNeural",
    "kn": "kn-IN-SapnaNeural"
}
LANGUAGE_NAMES = {"en": "English", "hi": "Hindi", "kn": "Kannada"}

# ---- Speech-to-Text setup (Whisper) ----
whisper_model = WhisperModel("tiny", device="cpu", compute_type="int8")

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

def listen():
    audio_file = record_audio()
    segments, info = whisper_model.transcribe(audio_file, language=None)
    text = " ".join([seg.text for seg in segments]).strip()
    detected_lang = info.language
    return text, detected_lang

# ---- Text-to-Speech ----
async def speak(text, voice):
    if not text.strip():
        return
    output_file = "reply.mp3"
    try:
        communicate = edge_tts.Communicate(text, voice)
        await communicate.save(output_file)
        pygame.mixer.music.load(output_file)
        pygame.mixer.music.play()
        while pygame.mixer.music.get_busy():
            pygame.time.Clock().tick(10)
        pygame.mixer.music.unload()
        os.remove(output_file)
    except Exception as e:
        print(f"(Voice failed, but here's the text reply above) — {e}")

# ---- Main chat loop ----
print("Your AI is ready. Speak, or say 'quit' or 'stop' to exit.\n")

conversation = [
    {
        "role": "system",
        "content": (
            "You are a warm, friendly AI companion. "
            "Always reply in a short, sweet, and casual way — "
            "2-3 sentences max, unless the user clearly asks for detail. "
            "Sound cool and natural, not robotic. Use simple, modern language. "
            "IMPORTANT: Always reply in the SAME language the user spoke in "
            "(English, Hindi, or Kannada). Do not switch languages."
        )
    }
]

while True:
    user_input, detected = listen()
    print(f"You said ({detected}): {user_input}")

    if not user_input:
        continue

    if "quit" in user_input.lower() or "stop" in user_input.lower():
        print("Goodbye!")
        break

    lang_code = detected if detected in VOICE_MAP else "en"

    conversation.append({"role": "user", "content": user_input})

    response = ollama.chat(model="llama3.2:3b", messages=conversation)
    ai_reply = response["message"]["content"]
    print(f"AI ({LANGUAGE_NAMES.get(lang_code, 'English')}): {ai_reply}\n")

    conversation.append({"role": "assistant", "content": ai_reply})

    asyncio.run(speak(ai_reply, voice=VOICE_MAP[lang_code]))
