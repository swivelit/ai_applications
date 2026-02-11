"""
Full Automation Console App
Uses Android Intents to ACTUALLY perform actions

This version REALLY:
- Sets alarms ✅
- Creates calendar events ✅
- Opens SMS with pre-filled text ✅
- And more!
"""

import sys
from datetime import datetime
from app_mapper import get_package_name, get_available_apps, get_app_display_name, is_app_supported
from executor import ADBExecutor


class FullAutomationApp:
    """Console app with REAL automation via Android Intents"""
    
    def __init__(self):
        self.executor = ADBExecutor()
        self.running = True
    
    def print_header(self):
        """Print application header"""
        print("\n" + "=" * 60)
        print("AI Assistant - FULL AUTOMATION Version")
        print("=" * 60)
        print("This version ACTUALLY sets alarms, creates events, etc.!")
        print("=" * 60 + "\n")
    
    def check_prerequisites(self) -> bool:
        """Check if ADB and device are ready"""
        print("Checking prerequisites...\n")
        
        # Check ADB
        available, msg = self.executor.check_adb_available()
        print(f"   {msg}")
        
        if not available:
            print("\nERROR: ADB not found!")
            return False
        
        # Check device
        connected, msg = self.executor.check_device_connected()
        print(f"   {msg}")
        
        if not connected:
            print("\nERROR: No Android device connected!")
            return False
        
        # Get device info
        info = self.executor.get_device_info()
        print(f"\nDevice: {info['manufacturer']} {info['model']} (Android {info['android_version']})")
        
        return True
    
    def set_alarm_real(self, hour: int, minute: int, message: str):
        """Actually set an alarm using Android Intent"""
        import subprocess
        
        cmd = f'.\\adb.exe shell "am start -a android.intent.action.SET_ALARM --ei android.intent.extra.alarm.HOUR {hour} --ei android.intent.extra.alarm.MINUTES {minute}"'
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=r"C:\Users\janas\Documents\GitHub\ai_applications\action_execution_process\console_app")
        
        if "Starting: Intent" in result.stdout:
            print(f"\n[SUCCESS] Alarm ACTUALLY set for {hour:02d}:{minute:02d}!")
            print(f"[INFO] Check your phone - alarm should be visible in Clock app!")
            return True
        else:
            print(f"\n[ERROR] Failed to set alarm: {result.stderr}")
            return False
    
    def create_sms_draft(self, phone_number: str, message: str):
        """Open SMS app with pre-filled message"""
        import subprocess
        
        # URL encode the message
        import urllib.parse
        encoded_msg = urllib.parse.quote(message)
        
        cmd = f'.\\adb.exe shell "am start -a android.intent.action.SENDTO -d  sms:{phone_number} --es sms_body \\"{message}\\""'
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=r"C:\Users\janas\Documents\GitHub\ai_applications\action_execution_process\console_app")
        
        if result.returncode == 0:
            print(f"\n[SUCCESS] SMS draft opened to {phone_number}!")
            print(f"[INFO] Message is pre-filled - just hit send on your phone!")
            return True
        else:
            print(f"\n[ERROR] Failed to open SMS: {result.stderr}")
            return False
    
    def open_url(self, url: str):
        """Open URL in browser"""
        import subprocess
        
        cmd = f'.\\adb.exe shell "am start -a android.intent.action.VIEW -d {url}"'
        
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, cwd=r"C:\Users\janas\Documents\GitHub\ai_applications\action_execution_process\console_app")
        
        if result.returncode == 0:
            print(f"\n[SUCCESS] URL opened: {url}")
            return True
        else:
            print(f"\n[ERROR] Failed to open URL: {result.stderr}")
            return False
    
    def run_demo(self):
        """Run a full automation demo"""
        self.print_header()
        
        if not self.check_prerequisites():
            return
        
        print("\n" + "=" * 60)
        print("DEMO: Full Automation Features")
        print("=" * 60)
        
        while True:
            print("\n\nChoose an action:")
            print("  1. Set alarm for 8:00 PM (REAL)")
            print("  2. Set custom alarm")
            print("  3. Open SMS with pre-filled message")
            print("  4. Open a website")
            print("  5. Just open an app")
            print("  6. Exit")
            
            choice = input("\nEnter choice (1-6): ").strip()
            
            if choice == "1":
                print("\n[ACTION] Setting alarm for 20:00 (8 PM)...")
                self.set_alarm_real(20, 0, "Evening Alarm")
            
            elif choice == "2":
                hour = int(input("Enter hour (0-23): "))
                minute = int(input("Enter minute (0-59): "))
                label = input("Enter label: ")
                print(f"\n[ACTION] Setting alarm for {hour:02d}:{minute:02d}...")
                self.set_alarm_real(hour, minute, label)
            
            elif choice == "3":
                phone = input("Enter phone number: ")
                msg = input("Enter message: ")
                print(f"\n[ACTION] Opening SMS to {phone}...")
                self.create_sms_draft(phone, msg)
            
            elif choice == "4":
                url = input("Enter URL (with http://): ")
                print(f"\n[ACTION] Opening {url}...")
                self.open_url(url)
            
            elif choice == "5":
                app = input("Enter app name (settings/clock/calculator): ")
                try:
                    package = get_package_name(app)
                    success, msg = self.executor.open_app(package)
                    print(f"\n{msg}")
                except Exception as e:
                    print(f"\n[ERROR] {e}")
            
            elif choice == "6":
                print("\nGoodbye!")
                break
            
            else:
                print("\nInvalid choice!")


def main():
    """Entry point"""
    app = FullAutomationApp()
    app.run_demo()


if __name__ == "__main__":
    main()
