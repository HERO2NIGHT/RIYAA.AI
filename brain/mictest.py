import sounddevice as sd
import numpy as np

print("Recording 3 seconds... speak now")
audio = sd.rec(int(3 * 16000), samplerate=16000, channels=1, dtype='int16', device=2)
sd.wait()
print("Done recording.")
print("Max volume level:", np.abs(audio).max())
