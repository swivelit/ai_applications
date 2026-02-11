"""
JSON Task Processor
Accepts JSON commands and executes them automatically

Usage:
    python process_task.py task.json
    OR
    echo '{"app":"clock","action":"set_alarm",...}' | python process_task.py
"""

import json
import sys
import subprocess
import time
from datetime import datetime


class JSONTaskProcessor:
    """Process JSON task commands"""
    
    def __init__(self):
        self.adb_path = ".\\adb.exe"
        self.app_dir = r"C:\Users\janas\Documents\GitHub\ai_applications\action_execution_process\console_app"
    
    def execute_adb_command(self, cmd):
        """Execute ADB shell command"""
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            cwd=self.app_dir
        )
        return result
    
    def go_home(self):
        """Return to Home screen (close app)"""
        print("[ACTION] Closing app (Returning to Home)...")
        time.sleep(2) # Wait a moment for the user to see the result
        cmd = f'{self.adb_path} shell input keyevent 3' # KEYCODE_HOME
        self.execute_adb_command(cmd)

    def set_alarm(self, data):
        """Set alarm from JSON data"""
        time_str = data.get("time", "08:00")
        hour, minute = map(int, time_str.split(":"))
        label = data.get("label", "Alarm")
        
        print(f"[ACTION] Setting alarm for {hour:02d}:{minute:02d}")
        print(f"[LABEL] {label}")
        
        # Build ADB command
        cmd = f'{self.adb_path} shell "am start -a android.intent.action.SET_ALARM --ei android.intent.extra.alarm.HOUR {hour} --ei android.intent.extra.alarm.MINUTES {minute}"'
        
        result = self.execute_adb_command(cmd)
        
        if "Starting: Intent" in result.stdout:
            self.go_home()
            return {
                "status": "success",
                "message": f"Alarm set for {hour:02d}:{minute:02d}",
                "label": label,
                "time": time_str
            }
        else:
            return {
                "status": "error",
                "message": "Failed to set alarm",
                "error": result.stderr
            }
    
    def create_note(self, data):
        """Create note (opens Keep app with text)"""
        title = data.get("title", "Note")
        content = data.get("content", "")
        
        print(f"[ACTION] Creating note: {title}")
        print(f"[CONTENT] {content}")
        
        # Use SEND intent to pass text to Keep
        # This acts like "Sharing" text to the Keep app
        cmd = f'{self.adb_path} shell "am start -a android.intent.action.SEND -t text/plain -p com.google.android.keep --es android.intent.extra.SUBJECT \\"{title}\\" --es android.intent.extra.TEXT \\"{content}\\""'
        
        result = self.execute_adb_command(cmd)
        
        if "Starting: Intent" in result.stdout:
            self.go_home()
            return {
                "status": "success",
                "message": "Note created (Text sent to Keep)",
                "title": title,
                "content": content
            }
        else:
            # Fallback if Keep is not installed or different package
            return {
                "status": "error",
                "message": "Failed to create note. Ensure Google Keep is installed.",
                "error": result.stderr
            }
    
    def send_sms(self, data):
        """Pre-fill SMS"""
        recipient = data.get("recipient", "")
        message = data.get("message", "")
        
        print(f"[ACTION] Preparing SMS to {recipient}")
        print(f"[MESSAGE] {message}")
        
        # URL encode message
        import urllib.parse
        encoded_msg = urllib.parse.quote(message)
        
        cmd = f'{self.adb_path} shell "am start -a android.intent.action.SENDTO -d sms:{recipient} --es sms_body \\"{message}\\""'
        
        result = self.execute_adb_command(cmd)
        
        if result.returncode == 0:
            self.go_home()
            return {
                "status": "success",
                "message": f"SMS draft created to {recipient}",
                "recipient": recipient,
                "content": message
            }
        else:
            return {
                "status": "error",
                "message": "Failed to create SMS",
                "error": result.stderr
            }
    
    def open_app(self, package_name):
        """Open any app by package name"""
        print(f"[ACTION] Opening app: {package_name}")
        
        cmd = f'{self.adb_path} shell monkey -p {package_name} -c android.intent.category.LAUNCHER 1'
        
        result = self.execute_adb_command(cmd)
        
        if "Events injected: 1" in result.stdout:
            return {
                "status": "success",
                "message": f"App opened: {package_name}",
                "package": package_name
            }
        else:
            return {
                "status": "error",
                "message": f"Failed to open app: {package_name}",
                "error": result.stderr
            }
    
    def process_task(self, task_json):
        """Process a task from JSON"""
        try:
            # Parse JSON if string
            if isinstance(task_json, str):
                task = json.loads(task_json)
            else:
                task = task_json
            
            request_id = task.get("request_id", "unknown")
            app = task.get("app", "").lower()
            action = task.get("action", "").lower()
            data = task.get("data", {})
            
            print("\n" + "=" * 60)
            print(f"[REQUEST] ID: {request_id}")
            print(f"[APP] {app}")
            print(f"[ACTION] {action}")
            print("=" * 60)
            
            # Route to appropriate handler
            if app == "clock" and action == "set_alarm":
                result = self.set_alarm(data)
            
            elif app == "notes" and action == "create_note":
                result = self.create_note(data)
            
            elif app == "messages" and action == "send_sms":
                result = self.send_sms(data)
            
            elif action == "open_app":
                package = data.get("package", "")
                result = self.open_app(package)
            
            else:
                result = {
                    "status": "error",
                    "message": f"Unknown app/action combination: {app}/{action}"
                }
            
            # Add request metadata
            result["request_id"] = request_id
            result["app"] = app
            result["action"] = action
            result["timestamp"] = datetime.now().isoformat()
            
            return result
        
        except json.JSONDecodeError as e:
            return {
                "status": "error",
                "message": f"Invalid JSON: {str(e)}"
            }
        
        except Exception as e:
            return {
                "status": "error",
                "message": f"Processing error: {str(e)}"
            }


def main():
    """Main entry point"""
    processor = JSONTaskProcessor()
    
    # Check if JSON file provided
    if len(sys.argv) > 1:
        json_file = sys.argv[1]
        print(f"[INFO] Reading from file: {json_file}")
        
        with open(json_file, 'r') as f:
            task_json = f.read()
    else:
        # Read from stdin
        print("[INFO] Reading from stdin...")
        print("[INFO] Paste JSON and press Ctrl+Z then Enter (Windows)")
        task_json = sys.stdin.read()
    
    # Process the task
    result = processor.process_task(task_json)
    
    # Output result as JSON
    print("\n" + "=" * 60)
    print("[RESULT]")
    print("=" * 60)
    print(json.dumps(result, indent=2))
    
    # Exit with appropriate code
    sys.exit(0 if result["status"] == "success" else 1)


if __name__ == "__main__":
    main()
