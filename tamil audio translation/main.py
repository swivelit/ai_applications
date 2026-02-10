import speech_recognition as sr
from googletrans import Translator

def tamil_speech_to_english():
    recognizer = sr.Recognizer()
    translator = Translator()

    with sr.Microphone() as source:
        print("Speak in Tamil...")
        recognizer.adjust_for_ambient_noise(source)
        audio = recognizer.listen(source)

    try:
        tamil_text = recognizer.recognize_google(audio, language='ta-IN')
        print("Tamil Text:", tamil_text)

        translated = translator.translate(tamil_text, src='ta', dest='en')
        print("English Translation:", translated.text)

    except sr.UnknownValueError:
        print("Could not understand audio")
    except sr.RequestError as e:
        print("API Error:", e)

if __name__ == "__main__":
    tamil_speech_to_english()
