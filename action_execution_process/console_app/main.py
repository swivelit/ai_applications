"""
AI Assistant Execution Engine - Console-Based ADB Prototype
Main Entry Point

PURPOSE:
This is a Proof of Concept (POC) to demonstrate that Python can trigger
Android apps using ADB and that the execution-layer architecture is feasible.

WHAT THIS DOES:
✅ Opens Android apps via ADB
✅ Simulates task execution in console
✅ Validates the execution pipeline

WHAT THIS DOES NOT DO:
❌ Automate internal app operations
❌ Type text into apps
❌ Set alarms programmatically
❌ Bypass Android security

For full automation, you need Android Accessibility Services or native code.
"""

import sys
from app_mapper import get_package_name, get_available_apps, get_app_display_name, is_app_supported
from executor import ADBExecutor
from task_handler import TaskHandler


class ConsoleApp:
    """Main console application"""
    
    def __init__(self):
        self.executor = ADBExecutor()
        self.task_handler = TaskHandler()
        self.running = True
    
    def print_header(self):
        """Print application header"""
        print("\n" + "=" * 60)
        print("AI Assistant Execution Engine - ADB Prototype")
        print("=" * 60)
        print("Proof of Concept - Demonstrates App Launching via ADB")
        print("=" * 60 + "\n")
    
    def check_prerequisites(self) -> bool:
        """
        Check if ADB and device are ready
        
        Returns:
            True if ready, False otherwise
        """
        print("🔍 Checking prerequisites...\n")
        
        # Check ADB
        available, msg = self.executor.check_adb_available()
        print(f"   {msg}")
        
        if not available:
            print("\n❌ ERROR: ADB not found!")
            print("   Please install Android Platform Tools:")
            print("   https://developer.android.com/studio/releases/platform-tools")
            return False
        
        # Check device
        connected, msg = self.executor.check_device_connected()
        print(f"   {msg}")
        
        if not connected:
            print("\n❌ ERROR: No Android device connected!")
            print("   Steps to fix:")
            print("   1. Enable USB Debugging: Settings → Developer Options → USB Debugging")
            print("   2. Connect device via USB")
            print("   3. Authorize PC on device when prompted")
            print("   4. Run 'adb devices' to verify connection")
            return False
        
        # Get device info
        info = self.executor.get_device_info()
        print(f"\n📱 Device: {info['manufacturer']} {info['model']} (Android {info['android_version']})")
        
        return True
    
    def show_available_apps(self):
        """Display available apps"""
        apps = ['notes', 'clock', 'calculator', 'settings', 'calendar', 
                'messages', 'phone', 'camera', 'chrome', 'whatsapp']
        
        print("\n📱 Available apps:")
        for i, app in enumerate(apps, 1):
            display_name = get_app_display_name(app)
            print(f"   {i:2}. {app:12} ({display_name})")
    
    def get_user_input(self, prompt: str, validation_func=None) -> str:
        """
        Get validated user input
        
        Args:
            prompt: Input prompt
            validation_func: Optional validation function
            
        Returns:
            User input string
        """
        while True:
            try:
                value = input(f"{prompt}: ").strip()
                
                if not value:
                    print("   ⚠️ Input cannot be empty. Try again.")
                    continue
                
                if validation_func and not validation_func(value):
                    continue
                
                return value
            
            except KeyboardInterrupt:
                print("\n\n👋 Cancelled by user.")
                sys.exit(0)
    
    def collect_task_parameters(self, app_name: str, action: str) -> dict:
        """
        Collect task-specific parameters
        
        Args:
            app_name: Application name
            action: Action to perform
            
        Returns:
            Dictionary of parameters
        """
        params = {}
        
        if app_name == 'notes' and action == 'create_note':
            print("\n📝 Note Details:")
            params['title'] = self.get_user_input("   Title")
            params['content'] = self.get_user_input("   Content")
        
        elif app_name == 'clock' and action == 'set_alarm':
            print("\n⏰ Alarm Details:")
            params['time'] = self.get_user_input("   Time (HH:MM)")
            params['date'] = self.get_user_input("   Date (YYYY-MM-DD)")
            params['label'] = input("   Label (optional): ").strip()
        
        elif app_name == 'clock' and action == 'set_timer':
            print("\n⏱️  Timer Details:")
            params['duration'] = self.get_user_input("   Duration (MM:SS)")
            params['label'] = input("   Label (optional): ").strip()
        
        elif app_name == 'calendar' and action == 'create_event':
            print("\n📅 Event Details:")
            params['title'] = self.get_user_input("   Event Title")
            params['date'] = self.get_user_input("   Date (YYYY-MM-DD)")
            params['time'] = self.get_user_input("   Time (HH:MM)")
        
        elif app_name == 'messages' and action == 'send_message':
            print("\n💬 Message Details:")
            params['recipient'] = self.get_user_input("   Recipient")
            params['message'] = self.get_user_input("   Message")
        
        elif app_name == 'phone' and action == 'make_call':
            print("\n📞 Call Details:")
            params['number'] = self.get_user_input("   Phone Number")
        
        return params
    
    def execute_task_flow(self):
        """Main task execution flow"""
        print("\n" + "─" * 60)
        
        # Show available apps
        self.show_available_apps()
        
        # Get app name
        print()
        app_name = self.get_user_input("Enter app name", is_app_supported).lower()
        
        # Get action
        supported_actions = self.task_handler.get_supported_actions(app_name)
        print(f"\n💡 Supported actions: {', '.join(supported_actions)}")
        action = self.get_user_input("Enter action").lower()
        
        # Collect parameters
        params = self.collect_task_parameters(app_name, action)
        
        # Execute
        print("\n" + "─" * 60)
        print("🔄 Executing Task...")
        print("─" * 60)
        
        # Step 1: Get package name
        try:
            package_name = get_package_name(app_name)
            display_name = get_app_display_name(app_name)
            print(f"\n📦 Package: {package_name}")
        except ValueError as e:
            print(f"❌ {e}")
            return
        
        # Step 2: Open app via ADB
        print(f"🚀 Opening {display_name} app...")
        success, msg = self.executor.open_app(package_name)
        print(msg)
        
        if not success:
            print("\n💡 Tip: Check if app is installed on your device")
            return
        
        # Step 3: Simulate task execution
        print(f"\n🎯 Executing action: {action}")
        success, msg = self.task_handler.execute_task(app_name, action, params)
        print(f"\n{msg}")
        
        print("\n" + "=" * 60)
    
    def run(self):
        """Main application loop"""
        self.print_header()
        
        # Check prerequisites
        if not self.check_prerequisites():
            return
        
        print("\n✅ All prerequisites met. Ready to execute tasks!")
        
        # Main loop
        while self.running:
            try:
                self.execute_task_flow()
                
                # Ask to continue
                print("\n" + "─" * 60)
                choice = input("\n🔄 Execute another task? (y/n): ").strip().lower()
                
                if choice != 'y':
                    self.running = False
                    print("\n👋 Thank you for using the AI Assistant Execution Engine!")
                    print("=" * 60 + "\n")
            
            except KeyboardInterrupt:
                print("\n\n👋 Goodbye!")
                break
            
            except Exception as e:
                print(f"\n❌ Unexpected error: {e}")
                print("Please try again.\n")


def main():
    """Entry point"""
    app = ConsoleApp()
    app.run()


if __name__ == "__main__":
    main()
