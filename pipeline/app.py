from flask import Flask, request, render_template
from deep_translator import GoogleTranslator
import re
import pyttsx3
from task_engine import set_alarm, open_app, add_reminder

app = Flask(__name__)

# -------------------------
# TEXT TO SPEECH
# -------------------------
engine = pyttsx3.init()

def speak(text):
    try:
        engine.say(text)
        engine.runAndWait()
    except:
        pass

# -------------------------
# TRANSLATE TAMIL -> ENGLISH
# -------------------------
def translate_to_english(text):
    try:
        return GoogleTranslator(source='auto', target='en').translate(text)
    except:
        return text

# -------------------------
# EXTRACT TIME
# -------------------------
def extract_time(text):
    match = re.search(r'(\d{1,2})(:(\d{2}))?\s*(am|pm)?', text, re.IGNORECASE)
    if match:
        hour = int(match.group(1))
        minute = match.group(3)
        am_pm = match.group(4)
        if minute is None:
            minute = "00"
        if am_pm:
            am_pm = am_pm.lower()
            if am_pm == "pm" and hour < 12:
                hour += 12
            if am_pm == "am" and hour == 12:
                hour = 0
        return f"{hour:02d}:{minute}"
    return None

# -------------------------
# INTENT DETECTION
# -------------------------
def detect_intent(english_text):
    text = english_text.lower()
    if any(word in text for word in ["alarm", "wake", "remind"]):
        return "set_alarm"
    if any(word in text for word in ["open", "start", "launch"]):
        return "open_app"
    if any(word in text for word in ["reminder", "note", "remember"]):
        return "add_reminder"
    if any(word in text for word in ["hello", "hi", "வணக்கம்"]):
        return "greeting"
    return "unknown"

# -------------------------
# RESPONSE ENGINE
# -------------------------
def generate_response(intent, english_text):

    text = english_text.lower()

    if intent == "set_alarm":
        time_str = extract_time(text)
        if time_str:
            response = set_alarm(time_str)
            speak(f"அலாரம் அமைக்கப்பட்டது {time_str} மணிக்கு")
        else:
            response = "Please specify time"
            speak("நேரத்தை சொல்லுங்கள்")

    elif intent == "open_app":
        response = open_app(text)

    elif intent == "add_reminder":
        response = add_reminder(text)

    elif intent == "greeting":
        response = "Hello! How can I help you?"
        speak("வணக்கம் நான் உங்களுக்கு உதவலாமா")

    else:
        response = "Command not understood"
        speak("மன்னிக்கவும் புரியவில்லை")

    return response

# -------------------------
# MAIN ROUTE
# -------------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    result = {}
    if request.method == 'POST':
        tamil_text = request.form['tamil']
        english = translate_to_english(tamil_text)
        normalized = english.lower()
        intent = detect_intent(normalized)
        response = generate_response(intent, normalized)

        result = {
            "tamil": tamil_text,
            "english": english,
            "intent": intent,
            "response": response
        }
    return render_template('index.html', result=result)

# -------------------------
# RUN SERVER
# -------------------------
if __name__ == '__main__':
    app.run(debug=True)
