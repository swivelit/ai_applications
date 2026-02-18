import speech_recognition as sr
from deep_translator import GoogleTranslator
from gtts import gTTS
import pygame
import tempfile
import os
import time
import re

# ---------- Language Detection ----------
def is_tamil(text):
    return any('\u0B80' <= ch <= '\u0BFF' for ch in text)


# ---------- English → Tamil ----------
def en_to_ta(text):
    return GoogleTranslator(source="en", target="ta").translate(text)


# ---------- Writing Tamil → Spoken Tamil ----------


def writing_to_spoken(text):
    # remove punctuation
    text = re.sub(r"[?.!]", "", text)

    rules = {
        "நீங்கள்": "நீ",
        "உங்களுக்கு": "உனக்கு",
        "தயவுசெய்து": "ப்ளீஸ்",
        "உதவி": "ஹெல்ப்",
        "செய்யுங்கள்": "பண்ணு",
        "செய்கிறேன்": "பண்ணுறேன்",
        "இருக்கிறது": "இருக்கு",
        "இருக்கிறேன்": "இருக்கேன்",
        "வருகிறேன்": "வரேன்",
        "போகிறேன்": "போறேன்",
        "நன்றி": "தேங்க்ஸ்",
        "எப்படி": "எப்படி",
        "இருக்கிறீர்கள்": "இருக்க"
    }

    for k, v in rules.items():
        text = text.replace(k, v)

    return text


# ---------- Theni Slang ----------
def theni_slang(text):
    if text and text[-1] not in "?!":
        text += " லே"

    replacements = {
        "இருக்கு": "இருக்கே",
        "வரேன்": "வரேன்லே",
        "போறேன்": "போறேன்லே"
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


# ---------- Speech → Text ----------
def listen_voice():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        print("🎤 பேசுங்க...")
        audio = r.listen(source)

    try:
        text = r.recognize_google(audio, language="en-IN")
        print("You said:", text)
        return text.lower()
    except:
        return ""


# ---------- Speak (Temporary file, auto-delete) ----------
def speak_tamil(text):
    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp3") as fp:
        temp_name = fp.name

    tts = gTTS(text=text, lang="ta")
    tts.save(temp_name)

    pygame.mixer.init()
    pygame.mixer.music.load(temp_name)
    pygame.mixer.music.play()

    while pygame.mixer.music.get_busy():
        time.sleep(0.1)

    pygame.mixer.quit()
    os.remove(temp_name)


# ---------- Continuous Voice Pipeline ----------
def voice_pipeline():
    while True:
        text = listen_voice()

        
        if text in ["bye", "exit", "stop", "quit"]:
            speak_tamil("சரி லே, பாக்கலாம்லே")
            print(" Exiting...")
            break

        if not text:
            speak_tamil("சரியா கேக்கல லே")
            continue

        if not is_tamil(text):
            text = en_to_ta(text)

        text = writing_to_spoken(text)
        text = theni_slang(text)

        speak_tamil(text)


# ---------- Run ----------
voice_pipeline()
