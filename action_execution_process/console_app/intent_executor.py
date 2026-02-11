"""
Intent Executor Module
Uses Android Intents to actually perform actions inside apps

This REALLY sets alarms, creates notes, etc.
Much more powerful than just opening apps!
"""

import subprocess
from typing import Tuple


class IntentExecutor:
    """Execute Android Intents to perform real actions"""
    
    def __init__(self):
        self.adb_path = "adb"
    
    def set_alarm(self, hour: int, minute: int, message: str = "Alarm") -> Tuple[bool, str]:
        """
        Actually set an alarm on the phone
        
        Args:
            hour: Hour (0-23)
            minute: Minute (0-59)
            message: Alarm label
            
        Returns:
            Tuple of (success, message)
        """
        try:
            command = [
                self.adb_path,
                "shell",
                "am", "start",
                "-a", "android.intent.action.SET_ALARM",
                "--ei", "android.intent.extra.alarm.HOUR", str(hour),
                "--ei", "android.intent.extra.alarm.MINUTES", str(minute),
                "--es", "android.intent.extra.alarm.MESSAGE", message
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return True, f"[OK] Alarm set for {hour:02d}:{minute:02d} - {message}"
            else:
                return False, f"[ERROR] Failed to set alarm: {result.stderr}"
        
        except Exception as e:
            return False, f"[ERROR] Error setting alarm: {str(e)}"
    
    def set_timer(self, seconds: int, message: str = "Timer") -> Tuple[bool, str]:
        """
        Set a timer on the phone
        
        Args:
            seconds: Duration in seconds
            message: Timer label
            
        Returns:
            Tuple of (success, message)
        """
        try:
            command = [
                self.adb_path,
                "shell",
                "am", "start",
                "-a", "android.intent.action.SET_TIMER",
                "--ei", "android.intent.extra.alarm.LENGTH", str(seconds),
                "--es", "android.intent.extra.alarm.MESSAGE", message,
                "--ez", "android.intent.extra.alarm.SKIP_UI", "true"
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                minutes = seconds // 60
                secs = seconds % 60
                return True, f"[OK] Timer set for {minutes}m {secs}s - {message}"
            else:
                return False, f"[ERROR] Failed to set timer: {result.stderr}"
        
        except Exception as e:
            return False, f"[ERROR] Error setting timer: {str(e)}"
    
    def create_calendar_event(self, title: str, begin_time_ms: int, end_time_ms: int) -> Tuple[bool, str]:
        """
        Create a calendar event
        
        Args:
            title: Event title
            begin_time_ms: Start time in milliseconds since epoch
            end_time_ms: End time in milliseconds since epoch
            
        Returns:
            Tuple of (success, message)
        """
        try:
            command = [
                self.adb_path,
                "shell",
                "am", "start",
                "-a", "android.intent.action.INSERT",
                "-d", "content://com.android.calendar/events",
                "--es", "title", title,
                "--el", "beginTime", str(begin_time_ms),
                "--el", "endTime", str(end_time_ms)
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return True, f"[OK] Calendar event created: {title}"
            else:
                return False, f"[ERROR] Failed to create event: {result.stderr}"
        
        except Exception as e:
            return False, f"[ERROR] Error creating event: {str(e)}"
    
    def send_sms(self, phone_number: str, message: str) -> Tuple[bool, str]:
        """
        Open SMS app with pre-filled message
        
        Args:
            phone_number: Recipient phone number
            message: Message text
            
        Returns:
            Tuple of (success, message)
        """
        try:
            command = [
                self.adb_path,
                "shell",
                "am", "start",
                "-a", "android.intent.action.SENDTO",
                "-d", f"sms:{phone_number}",
                "--es", "sms_body", message
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return True, f"[OK] SMS draft created to {phone_number}"
            else:
                return False, f"[ERROR] Failed to open SMS: {result.stderr}"
        
        except Exception as e:
            return False, f"[ERROR] Error sending SMS: {str(e)}"
    
    def make_call(self, phone_number: str) -> Tuple[bool, str]:
        """
        Initiate a phone call
        
        Args:
            phone_number: Number to call
            
        Returns:
            Tuple of (success, message)
        """
        try:
            command = [
                self.adb_path,
                "shell",
                "am", "start",
                "-a", "android.intent.action.CALL",
                "-d", f"tel:{phone_number}"
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return True, f"[OK] Calling {phone_number}"
            else:
                return False, f"[ERROR] Failed to make call: {result.stderr}"
        
        except Exception as e:
            return False, f"[ERROR] Error making call: {str(e)}"
    
    def open_url(self, url: str) -> Tuple[bool, str]:
        """
        Open a URL in browser
        
        Args:
            url: URL to open
            
        Returns:
            Tuple of (success, message)
        """
        try:
            command = [
                self.adb_path,
                "shell",
                "am", "start",
                "-a", "android.intent.action.VIEW",
                "-d", url
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode == 0:
                return True, f"[OK] Opened URL: {url}"
            else:
                return False, f"[ERROR] Failed to open URL: {result.stderr}"
        
        except Exception as e:
            return False, f"[ERROR] Error opening URL: {str(e)}"


# Test the intent executor
if __name__ == "__main__":
    print("=" * 60)
    print("Intent Executor - Testing")
    print("=" * 60)
    
    executor = IntentExecutor()
    
    # Test setting an alarm for 8:00 PM
    print("\nTesting alarm creation for 20:00...")
    success, msg = executor.set_alarm(20, 0, "Test Alarm")
    print(msg)
    
    print("\n" + "=" * 60)
    print("Check your phone - alarm should be set!")
    print("=" * 60)
