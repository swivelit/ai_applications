import speech_recognition as sr
import sounddevice as sd
import numpy as np

r = sr.Recognizer()

SAMPLERATE = 44100
CHANNELS = 1
SAMPLE_WIDTH = 2
DURATION = 5

print("🎤 தமிழில் பேசுங்கள்... (அடிப்படை பதிவு: {} விநாடிகள்)".format(DURATION))

try:
    recording = sd.rec(int(DURATION * SAMPLERATE), samplerate=SAMPLERATE, channels=CHANNELS, dtype='int16')
    sd.wait()

    audio_bytes = recording.tobytes()
    audio_data = sr.AudioData(audio_bytes, SAMPLERATE, SAMPLE_WIDTH)

    text = r.recognize_google(audio_data, language="ta-IN")

    print("📝 நீங்கள் சொன்னது:", text)

    with open("output.txt", "a", encoding="utf-8") as f:
        f.write(text + "\n")

    print("✅ Text saved in output.txt")

except sr.UnknownValueError:
    print("❌ புரியவில்லை")

except sr.RequestError:
    print("❌ Internet required")

except Exception as e:
    print("❌ Error:", e)
