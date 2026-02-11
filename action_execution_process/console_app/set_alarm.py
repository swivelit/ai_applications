"""
Direct Command Executor
No menus - just run and it does what you want!

Usage:
    python set_alarm.py 20 0 "Evening Alarm"
    python set_alarm.py 21 30 "Test"
"""

import sys
import subprocess


def set_alarm(hour, minute, label="Alarm"):
    """Set alarm directly - no menu!"""
    
    # Validate inputs
    hour = int(hour)
    minute = int(minute)
    
    if not (0 <= hour <= 23):
        print(f"[ERROR] Hour must be 0-23, got {hour}")
        return False
    
    if not (0 <= minute <= 59):
        print(f"[ERROR] Minute must be 0-59, got {minute}")
        return False
    
    print(f"\n[ACTION] Setting alarm for {hour:02d}:{minute:02d} - {label}")
    
    # Execute ADB command
    cmd = f'.\\adb.exe shell "am start -a android.intent.action.SET_ALARM --ei android.intent.extra.alarm.HOUR {hour} --ei android.intent.extra.alarm.MINUTES {minute}"'
    
    result = subprocess.run(
        cmd, 
        shell=True, 
        capture_output=True, 
        text=True,
        cwd=r"C:\Users\janas\Documents\GitHub\ai_applications\action_execution_process\console_app"
    )
    
    if "Starting: Intent" in result.stdout:
        print(f"[SUCCESS] Alarm set for {hour:02d}:{minute:02d}!")
        print(f"[INFO] Label: {label}")
        print(f"[INFO] Check your phone Clock app now!")
        return True
    else:
        print(f"[ERROR] Failed: {result.stderr}")
        return False


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("\n" + "="*60)
        print("USAGE: Set Alarm Directly")
        print("="*60)
        print("\nFormat:")
        print("  python set_alarm.py HOUR MINUTE [LABEL]")
        print("\nExamples:")
        print("  python set_alarm.py 20 0 \"Evening Alarm\"")
        print("  python set_alarm.py 21 30 \"Night Alarm\"")
        print("  python set_alarm.py 8 15 \"Morning Alarm\"")
        print("\nQuick Commands:")
        print("  python set_alarm.py 20 0     (8 PM)")
        print("  python set_alarm.py 21 0     (9 PM)")
        print("  python set_alarm.py 22 0     (10 PM)")
        print("\n" + "="*60)
        sys.exit(1)
    
    # Get arguments
    hour = sys.argv[1]
    minute = sys.argv[2]
    label = sys.argv[3] if len(sys.argv) > 3 else "Alarm"
    
    # Set the alarm!
    set_alarm(hour, minute, label)
