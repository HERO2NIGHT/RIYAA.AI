import sounddevice as sd
import numpy as np

print("Clap in 3 seconds...")
audio = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype='int16', device=0)
sd.wait()
print("Max amplitude:", np.abs(audio).max())
