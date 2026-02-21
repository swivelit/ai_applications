import threading
import time
from datetime import datetime
import os
import platform
import webbrowser

# List to keep track of alarms
alarms = []
reminders = []

# -----------------------------
# ALARM SOUND
# -----------------------------
def play_alarm_sound():
    try:
        if platform.system() == "Windows":
            import winsound
            for _ in range(5):
                winsound.Beep(2500, 1000)
        else:
            for _ in range(5):
                os.system("echo -e '\a'")
                time.sleep(1)
    except Exception as e:
        print("Alarm sound error:", e)

# -----------------------------
# ALARM WORKER
# -----------------------------
def alarm_worker(alarm_time):
    print(f"⏰ Alarm set for {alarm_time}")
    while True:
        now = datetime.now().strftime("%H:%M")
        if now == alarm_time:
            print("🔔 ALARM RINGING!!! 🔔")
            play_alarm_sound()
            break
        time.sleep(5)

# -----------------------------
# SET ALARM
# -----------------------------
def set_alarm(time_str):
    try:
        thread = threading.Thread(target=alarm_worker, args=(time_str,))
        thread.daemon = True
        thread.start()
        alarms.append(time_str)
        return f"Alarm scheduled at {time_str}"
    except Exception as e:
        return f"Error setting alarm: {str(e)}"

# -----------------------------
# OPEN APP
# -----------------------------
def open_app(text):
    try:
        text = text.lower()
        if "youtube" in text:
            webbrowser.open("https://www.youtube.com")
            return "Opening YouTube"
        elif "google" in text:
            webbrowser.open("https://www.google.com")
            return "Opening Google"
        elif "gmail" in text:
            webbrowser.open("https://mail.google.com")
            return "Opening Gmail"
        else:
            return "App not recognized"
    except Exception as e:
        return f"Error opening app: {str(e)}"

# -----------------------------
# ADD REMINDER
# -----------------------------
def add_reminder(text):
    try:
        # Store reminder text and timestamp
        reminders.append({"text": text, "time": datetime.now().strftime("%H:%M:%S")})
        return f"Reminder added: {text}"
    except Exception as e:
        return f"Error adding reminder: {str(e)}"
