# 🤖 AI Assistant Execution Engine - Console-Based ADB Prototype

## 📌 Project Purpose

**This is a Proof of Concept (POC) for internal technical validation.**

### ✅ What This IS:
- Simple console-based prototype
- Tests if Python + ADB can open Android apps automatically
- Demonstrates execution layer feasibility
- Testing tool for developers

### ❌ What This is NOT:
- Not a production system
- Not a full AI assistant
- Not controlling app internals
- Not bypassing Android security

---

## 🎯 Project Goal

Demonstrate that **Python can trigger Android apps using ADB** and that the execution-layer architecture is technically feasible.

---

## 🔧 Prerequisites

### 1. Android Device Setup
- ✅ Android phone/emulator
- ✅ USB Debugging enabled
  - Settings → Developer Options → USB Debugging
- ✅ Connected to PC via USB or Wi-Fi ADB

### 2. ADB Installation
**Windows:**
```bash
# Download Android Platform Tools
# Add to PATH or use from folder directly
adb version  # Test if working
```

**Check device connection:**
```bash
adb devices
```
You should see your device listed.

### 3. Python
- Python 3.8+ installed
- No additional libraries needed (uses subprocess)

---

## 📁 Project Structure

```
console_app/
├── main.py              # Entry point - console interface
├── app_mapper.py        # Maps app names to package names
├── executor.py          # ADB execution engine
├── task_handler.py      # Task simulation logic
└── README.md           # This file
```

---

## 🚀 How to Run

### Quick Start:
```bash
# Navigate to console app folder
cd action_execution_process/console_app

# Run the program
python main.py
```

### Follow the prompts:
1. Enter app name (notes/clock/calculator/settings)
2. Enter action
3. Provide required details
4. Watch app open on your device!

---

## 📱 Supported Apps

| App Name | Action | Package Name | Required Info |
|----------|--------|--------------|---------------|
| notes | create_note | com.google.android.keep | Title, Content |
| clock | set_alarm | com.google.android.deskclock | Time, Date |
| calculator | open | com.android.calculator2 | None |
| settings | open | com.android.settings | None |

---

## 🧪 Example Output

### Example 1: Opening Notes App
```
=================================================
🤖 AI Assistant Execution Engine - ADB Prototype
=================================================

Available apps: notes, clock, calculator, settings

Enter app name: notes
Enter action: create_note
Enter note title: Meeting Notes
Enter note content: Discuss project roadmap

----------------------------------------
🔄 Executing Task...
----------------------------------------
Opening Notes app...
✅ Notes app opened successfully.

Creating note with title: Meeting Notes
Content: Discuss project roadmap

✅ Note created successfully (Simulation)
```

### Example 2: Setting Alarm
```
Enter app name: clock
Enter action: set_alarm
Enter alarm time (HH:MM): 22:00
Enter alarm date (YYYY-MM-DD): 2026-02-12

----------------------------------------
🔄 Executing Task...
----------------------------------------
Opening Clock app...
✅ Clock app opened successfully.

Setting alarm for 2026-02-12 at 22:00

✅ Alarm set successfully (Simulation)
```

---

## ⚙️ How It Works

### Execution Flow:
```
1. User enters app name + action
         ↓
2. Collect required parameters
         ↓
3. Map app name → Android package name
         ↓
4. Execute ADB command to open app
         ↓
5. Simulate task execution (console print)
         ↓
6. Show success confirmation
```

### ADB Command Used:
```bash
adb shell monkey -p <package_name> -c android.intent.category.LAUNCHER 1
```

---

## 🔍 Technical Details

### What This Does:
- ✅ Opens Android apps via ADB
- ✅ Validates app existence
- ✅ Handles errors gracefully
- ✅ Simulates task completion

### What This Does NOT Do:
- ❌ Automatically type in apps
- ❌ Save notes automatically
- ❌ Set alarms programmatically
- ❌ Bypass Android permissions

**Full automation requires:**
- Native Android code (Java/Kotlin)
- Android Accessibility Services
- UI Automator framework
- Or root access (not recommended)

---

## 🛠️ Troubleshooting

### Device not found:
```bash
adb devices
# If empty, check:
# - USB cable connected
# - USB debugging enabled
# - Authorize PC on phone
```

### App doesn't open:
```bash
# Check if package exists on device:
adb shell pm list packages | grep <package_name>

# Try manually:
adb shell monkey -p com.google.android.keep -c android.intent.category.LAUNCHER 1
```

### Permission denied:
- Grant ADB permissions on device
- Re-authorize PC connection

---

## 🎯 Next Steps

This prototype demonstrates:
- ✅ Python → ADB → Android app pipeline works
- ✅ Execution layer is feasible
- ✅ Structured input → execution works
- ✅ Can be expanded for production

### For Production:
1. Integrate with backend API
2. Use Android Accessibility Services for automation
3. Implement proper error handling
4. Add logging and monitoring
5. Scale to support more apps

---

## 📝 Important Notes

> **⚠️ LIMITATION**: This prototype only opens apps. It does NOT automate internal app actions. That requires native Android development or accessibility services.

> **💡 PURPOSE**: This is a feasibility test to show that the execution layer architecture is viable and can trigger Android apps programmatically.

---

## 📞 Support

**Device Setup Issues**: Check Android Developer documentation  
**ADB Problems**: Verify `adb devices` shows your device  
**App Not Opening**: Verify package name exists on your device

---

**Created**: February 2026  
**Type**: Proof of Concept  
**Platform**: Windows + Android  
**Language**: Python 3.8+

🚀 **Ready to test Android app automation!**
