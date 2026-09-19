# RIYAA.AI

A multilingual AI companion with a live, expressive 3D avatar — built entirely from free and open-source tools. Talks back in English, Hindi, and Kannada, sees you through a camera, remembers you across sessions, and reacts with natural expressions and gestures.

Built as a rapid prototype on a low-spec laptop (Intel i3, 8GB RAM, no dedicated GPU) — proof that you don't need expensive hardware or paid APIs to build something like this.

## Features

- **Multilingual voice chat** — speaks and understands English, Hindi, and Kannada
- **Local AI brain** — runs entirely offline using [Ollama](https://ollama.com) (Llama 3.2), no API costs
- **Realistic 3D avatar** — VRM-based avatar with natural idle motion, word-synced lip movement, and emotion-reactive expressions (smiles, winks, teacher-style talking gestures)
- **Camera interaction** — detects hand waves via webcam (or phone camera) and reacts with a smile
- **Persistent memory** — remembers facts about you across sessions using a local SQLite database
- **Live fact-checking** — optionally verifies factual questions via web search before answering
- **Custom triggers** — say "let's go" to play a custom video; intro video plays on launch
- **Phone as mic/camera** — supports DroidCam so your phone can act as an external mic and camera, with auto-detection

## Tech stack

| Component | Tool |
|---|---|
| AI brain | [Ollama](https://ollama.com) running `llama3.2:3b` |
| Speech-to-text | [faster-whisper](https://github.com/SYSTRAN/faster-whisper) |
| Text-to-speech | [edge-tts](https://github.com/rany2/edge-tts) |
| Avatar rendering | [Three.js](https://threejs.org) + [@pixiv/three-vrm](https://github.com/pixiv/three-vrm) |
| Camera/gesture detection | [OpenCV](https://opencv.org) + [MediaPipe](https://developers.google.com/mediapipe) |
| Backend | [Flask](https://flask.palletsprojects.com) |
| Memory | SQLite |
| Web search (fact-check) | [ddgs](https://pypi.org/project/ddgs/) (DuckDuckGo search) |

## Prerequisites

- Windows 10/11
- [Python 3.11](https://www.python.org/downloads/release/python-3119/) (mediapipe and some dependencies are not yet compatible with newer Python versions)
- [Node.js LTS](https://nodejs.org) (used only to serve the avatar's web files)
- [Ollama](https://ollama.com/download) installed and running
- A webcam and microphone (built-in or via a phone using [DroidCam](https://www.dev47apps.com/))

## Setup

**1. Clone the repository**
```bash
git clone https://github.com/<your-username>/<repo-name>.git
cd <repo-name>
```

**2. Install Python dependencies**
```bash
py -3.11 -m pip install flask flask-cors ollama edge-tts pygame faster-whisper ddgs opencv-python mediapipe sounddevice numpy
```

**3. Pull the AI model**
```bash
ollama pull llama3.2:3b
```

**4. Add your assets**

Place the following files in the `avatar/` folder:
- `avatar.vrm` — your 3D avatar model (get one free from [VRoid Hub](https://vroid.com/en/hub) or [VIVERSE Avatar Maker](https://avatar.viverse.com))
- `background.png` — a background image for the scene
- `intro.mp4` — a video that plays on launch
- `letsgo.mp4` — a video that plays when you say "let's go"

**5. Set up corrections file**

Create `brain/corrections.json` if it doesn't already exist:
```json
{
  "en": {},
  "hi": {},
  "kn": {}
}
```
Use this to fix recurring speech-recognition mistakes — add `"misheard word": "correct word"` pairs as you notice them.

## Running it

Open two terminals:

**Terminal 1 — serves the avatar's web files**
```bash
cd avatar
py -3.11 -m http.server 8000
```

**Terminal 2 — runs the AI brain, voice, and camera**
```bash
cd brain
py -3.11 server.py
```

Then open your browser to:
```
http://localhost:8000
```

Make sure the Ollama app is running in the background before starting Terminal 2.

### One-click launch (optional)

Create a `start.bat` file in the project root:
```bat
@echo off
start "Avatar Server" cmd /k "cd /d %~dp0avatar && py -3.11 -m http.server 8000"
timeout /t 2 /nobreak >nul
start "Brain Server" cmd /k "cd /d %~dp0brain && py -3.11 server.py"
timeout /t 3 /nobreak >nul
start http://localhost:8000
```
Double-click it to launch everything at once.

## Using your phone as mic/camera (optional)

1. Install [DroidCam](https://www.dev47apps.com/) on both your phone and PC
2. Connect them over the same WiFi network
3. `server.py` and `camera.py` auto-detect a connected DroidCam device and use it automatically — no manual configuration needed. If DroidCam isn't connected, they fall back to your laptop's built-in mic/camera.

## Project structure

```
├── avatar/
│   ├── index.html          # Avatar renderer (Three.js + VRM)
│   ├── avatar.vrm          # Your 3D avatar model
│   ├── background.png      # Scene background
│   ├── intro.mp4           # Intro video
│   └── letsgo.mp4          # "Let's go" trigger video
├── brain/
│   ├── server.py           # Main backend: voice, AI, memory, Flask server
│   ├── camera.py           # Camera-based wave detection
│   ├── memory.py           # SQLite persistent memory
│   └── corrections.json    # Speech recognition correction dictionary
└── start.bat                # One-click launcher (optional)
```

## Known limitations

- Speech recognition uses Whisper's `tiny` model for speed on low-spec hardware — Hindi and Kannada accuracy is noticeably weaker than English. Swap to `small` or `medium` in `server.py` for better accuracy at the cost of speed.
- Lip-sync is word-level (mouth opens per spoken word), not phoneme-accurate.
- Arm-wave animation is disabled by default due to differences in avatar rigging between models — currently the avatar reacts to a detected wave with a smile instead of waving back. Enabling a matching arm animation requires tuning rotation values to your specific avatar's skeleton.
- Edge-tts and web search require an internet connection; the AI brain (Ollama) runs fully offline.

## Acknowledgments

Built end-to-end in a short sprint, with help from Claude (Anthropic) for architecture, debugging, and implementation guidance throughout.

## License

Add your preferred license here (e.g. MIT) before making the repository public.
