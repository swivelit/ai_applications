# 🚀 QUICK START GUIDE - Run Full Automation

## Complete Step-by-Step Instructions

---

## ✅ STEP 1: Open PowerShell

1. Press **Windows + X**
2. Click **"Windows PowerShell"** or **"Terminal"**

---

## ✅ STEP 2: Navigate to Project Folder

Copy and paste this command:

```powershell
cd C:\Users\janas\Documents\GitHub\ai_applications\action_execution_process\console_app
```

Press **Enter**

---

## ✅ STEP 3: Connect Your Phone

1. **Plug in USB cable** to phone and PC
2. On your phone:
   - Pull down notification
   - Tap "USB for charging"
   - Select **"File transfer"**
3. **Accept USB debugging** popup (if appears)

---

## ✅ STEP 4: Verify Connection

Run this command:

```powershell
.\adb.exe devices
```

**You should see:**
```
List of devices attached
ZA222MBTV6    device
```

✅ If you see "device" → **Perfect! Continue!**
❌ If empty or "unauthorized" → Check phone popup, try again

---

## ✅ STEP 5: Run Full Automation App

```powershell
python full_automation.py
```

**You'll see:**
```
============================================================
AI Assistant - FULL AUTOMATION Version
============================================================
This version ACTUALLY sets alarms, creates events, etc.!
============================================================

Checking prerequisites...
   [OK] ADB available
   [OK] Device connected

Choose an action:
  1. Set alarm for 8:00 PM (REAL)
  2. Set custom alarm
  3. Open SMS with pre-filled message
  4. Open a website
  5. Just open an app
  6. Exit
```

---

## 🎯 STEP 6: Test Each Feature

### Test 1: Set Alarm for 8 PM
```
1. Type: 1
2. Press Enter
3. Check your phone Clock app → Alarms tab
4. You should see alarm for 20:00! ✅
```

### Test 2: Set Custom Alarm
```
1. Type: 2
2. Enter hour: 21
3. Enter minute: 30
4. Enter label: Test Alarm
5. Check phone → Alarm is set! ✅
```

### Test 3: Pre-fill SMS
```
1. Type: 3
2. Enter phone: 1234567890 (fake number OK for test)
3. Enter message: Hello from my PC!
4. SMS app opens with message pre-filled! ✅
```

### Test 4: Open Website
```
1. Type: 4
2. Enter URL: https://www.google.com
3. Browser opens on phone! ✅
```

### Test 5: Open App
```
1. Type: 5
2. Enter app: calculator
3. Calculator opens! ✅
```

### Exit
```
Type: 6
```

---

## 🎮 ANYTIME YOU WANT TO USE IT:

### Quick Commands:
```powershell
# Step 1: Open PowerShell

# Step 2: Go to folder
cd C:\Users\janas\Documents\GitHub\ai_applications\action_execution_process\console_app

# Step 3: Run app
python full_automation.py
```

**That's it!** 3 commands total!

---

## 📱 Before Each Use - Quick Checklist:

- [ ] Phone connected via USB
- [ ] USB debugging enabled
- [ ] File transfer mode selected
- [ ] PC authorized on phone

---

## ⚡ EVEN FASTER - Create Desktop Shortcut

### Create a `.bat` file:

1. Open Notepad
2. Paste this:

```batch
@echo off
cd C:\Users\janas\Documents\GitHub\ai_applications\action_execution_process\console_app
python full_automation.py
pause
```

3. Save as: `Desktop\RunAutomation.bat`
4. Double-click anytime to run!

---

## 🎯 What Each Feature Does:

| Option | What Happens | Where to Check |
|--------|--------------|----------------|
| 1 | Sets alarm for 20:00 (8 PM) | Clock app → Alarms |
| 2 | Sets alarm for any time you choose | Clock app → Alarms |
| 3 | Opens SMS with message typed | Messages app |
| 4 | Opens website in browser | Chrome/Browser |
| 5 | Launches any app | Phone screen |

---

## ❓ Troubleshooting

### Problem: "python not found"
**Solution:**
```powershell
# Check Python version
python --version

# If not found, install Python 3.8+
# Download from: https://www.python.org/downloads/
```

### Problem: "adb not found"
**Solution:**
```powershell
# Use the full path
.\adb.exe devices
```

### Problem: "No devices connected"
**Solution:**
1. Unplug USB cable
2. Plug back in
3. On phone: Select "File Transfer"
4. Accept USB debugging popup
5. Try again:
```powershell
.\adb.exe devices
```

### Problem: "Alarm not setting"
**Solution:**
- Check if Clock app supports intents
- Some custom Android versions may not support it
- Try opening app manually first (Option 5)

---

## 📊 Expected Results

### When Working Correctly:

**Option 1 (Set 8 PM Alarm):**
```
[ACTION] Setting alarm for 20:00 (8 PM)...

[SUCCESS] Alarm ACTUALLY set for 20:00!
[INFO] Check your phone - alarm should be visible in Clock app!
```

**Then on your phone:**
- Open Clock app
- Tap Alarms tab
- See alarm for 20:00 ✅

---

## 🎉 SUCCESS INDICATORS

You'll know it's working when:

1. ✅ PowerShell shows "[SUCCESS]" messages
2. ✅ Phone screen changes (app opens, etc.)
3. ✅ Alarm appears in Clock app
4. ✅ SMS app opens with text
5. ✅ Browser opens to website

---

## 💡 Tips for Best Results

### Before Running:
1. **Unlock your phone** (not just connected)
2. **Keep screen on** while testing
3. **Close apps** that might interfere

### While Running:
1. **Watch your phone** to see changes
2. **Don't unplug USB** during execution
3. **Check results** after each action

### After Running:
1. **Verify alarms** in Clock app
2. **Test alarms** (set for 1 minute ahead)
3. **Show your team!** 🎯

---

## 🚀 COMPLETE EXAMPLE SESSION

```powershell
# Open PowerShell
PS C:\> cd C:\Users\janas\Documents\GitHub\ai_applications\action_execution_process\console_app
PS C:\...\console_app> python full_automation.py

# You see menu, you type:
1

# Result on screen:
[SUCCESS] Alarm ACTUALLY set for 20:00!

# Result on phone:
Clock app → Alarms → "20:00" alarm visible! ✅

# Test SMS:
3
1234567890
Hello from PC!

# Result on phone:
Messages app opens with "Hello from PC!" pre-typed! ✅

# Exit:
6
Goodbye!
```

---

## 📁 Project Files Reference

**Main App:**
- `full_automation.py` ← **Run this!**

**Support Files:**
- `executor.py` - ADB commands
- `app_mapper.py` - App names
- `intent_executor.py` - Android intents

**Documentation:**
- `FULL_AUTOMATION_SUCCESS.md` - What's working
- `POC_TEST_RESULTS.md` - Original POC results
- `README.md` - Full documentation

---

## 🎯 Next Steps After Success

### 1. Show Your Team
- Run live demo
- Show alarm setting
- Show SMS pre-filling
- Explain architecture

### 2. Customize
- Add more apps to `app_mapper.py`
- Add more intents to `full_automation.py`
- Create shortcuts for common tasks

### 3. Expand (Optional)
- Add calendar events
- Add more automation
- Build Android Accessibility Service for full control

---

## ✅ YOU'RE READY!

**Just 3 commands:**
```powershell
cd C:\Users\janas\Documents\GitHub\ai_applications\action_execution_process\console_app
python full_automation.py
# Choose 1-6
```

**That's it!** 🎉

---

## 🆘 Need Help?

**Quick Checks:**
1. Is phone connected? → `.\adb.exe devices`
2. Is Python installed? → `python --version`
3. Are you in right folder? → `dir` (should see full_automation.py)

**Common Issues:**
- Phone not detected → Reconnect USB, accept popup
- Python error → Check Python 3.8+ installed
- ADB error → Use `.\adb.exe` instead of `adb`

---

**NOW GO TRY IT!** 🚀
