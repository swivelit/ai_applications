# 📱 Android Device Setup Guide

## 🎯 Goal
Enable your Android device to receive ADB commands from PC

---

## ✅ Step-by-Step Setup

### 1️⃣ Enable Developer Options

1. Open **Settings** on your Android device
2. Scroll to **About Phone**
3. Find **Build Number**
4. **Tap 7 times** on Build Number
5. You'll see: "You are now a developer!"

---

### 2️⃣ Enable USB Debugging

1. Go back to **Settings**
2. Find **Developer Options** (or **System → Developer Options**)
3. Turn on **USB Debugging**
4. Confirm the popup

---

### 3️⃣ Connect to PC

**Option A: USB Cable (Recommended)**
1. Connect phone to PC with USB cable
2. Select **File Transfer** mode on phone
3. Accept "Allow USB debugging" popup

**Option B: Wireless ADB (Advanced)**
```bash
# On device connected via USB first:
adb tcpip 5555
adb connect <device-ip>:5555
```

---

### 4️⃣ Verify Connection

Open terminal on PC and run:
```bash
adb devices
```

**Expected output:**
```
List of devices attached
ABC123XYZ    device
```

If you see `unauthorized`, accept the prompt on your phone.

---

## 🔧 Install ADB on Windows

### Method 1: Minimal ADB (Quick)
1. Download: [Minimal ADB and Fastboot](https://androidfilehost.com/?w=files&flid=37081)
2. Extract to `C:\adb\`
3. Add to PATH or use from folder

### Method 2: Android Platform Tools (Official)
1. Download: [Android Platform Tools](https://developer.android.com/studio/releases/platform-tools)
2. Extract to desired location
3. Add to Windows PATH:
   - Right-click This PC → Properties
   - Advanced System Settings → Environment Variables
   - Edit PATH, add ADB folder path
   - Restart terminal

### Test Installation:
```bash
adb version
```

You should see the ADB version number.

---

## 🧪 Test App Opening

Once connected, test opening an app:

```bash
# Open Settings (should always work)
adb shell monkey -p com.android.settings -c android.intent.category.LAUNCHER 1

# Open Calculator
adb shell monkey -p com.android.calculator2 -c android.intent.category.LAUNCHER 1
```

If the app opens on your device, you're ready! ✅

---

## 🚨 Troubleshooting

### Device not listed
- Try different USB cable
- Try different USB port
- Restart phone and PC
- Disable and re-enable USB debugging

### Unauthorized
- Accept prompt on phone
- Run: `adb kill-server` then `adb devices`
- Revoke and re-grant USB debugging authorizations

### App not opening
- Check if app is installed:
  ```bash
  adb shell pm list packages | grep <package-name>
  ```
- Try alternative package name
- Verify app exists on your device

---

## 📝 Quick Commands Reference

```bash
# List connected devices
adb devices

# Get device info
adb shell getprop ro.product.model
adb shell getprop ro.build.version.release

# List installed packages
adb shell pm list packages

# Open an app
adb shell monkey -p <package.name> -c android.intent.category.LAUNCHER 1

# Restart ADB server
adb kill-server
adb start-server
```

---

## ✅ Device Ready Checklist

- [ ] Developer Options enabled
- [ ] USB Debugging enabled
- [ ] Device connected to PC
- [ ] `adb devices` shows device
- [ ] Test app opening works
- [ ] Authorization accepted

---

**Once all checked, you're ready to run `main.py`!** 🚀
