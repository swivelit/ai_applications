# 🚀 QUICK START - Console App

## ⚡ Fastest Way to Run

### 1️⃣ **Test Components** (No device needed)
```bash
cd action_execution_process/console_app
python test_components.py
```

This verifies all code works! ✅

---

### 2️⃣ **Install ADB** (If not installed)

**Download:** https://developer.android.com/studio/releases/platform-tools

**Quick Test:**
```bash
adb version
```

---

### 3️⃣ **Setup Android Device**

**Quick Steps:**
1. Settings → About Phone → Tap "Build Number" 7 times
2. Settings → Developer Options → Enable "USB Debugging"  
3. Connect device to PC via USB
4. Accept authorization popup on phone

**Verify:**
```bash
adb devices
```

You should see your device listed!

---

### 4️⃣ **Run the App**

```bash
cd action_execution_process/console_app
python main.py
```

---

## 🎯 Quick Demo

**Try opening Settings (works on any Android):**

```
Enter app name: settings
Enter action: open
```

Watch it open Settings on your device! 📱

---

## 📚 More Help

- **Full Guide:** See `README.md`
- **Device Setup:** See `SETUP_DEVICE.md`  
- **Project Info:** See `PROJECT_COMPLETE.md`

---

**That's it! You're ready to test Android app automation! 🎉**
