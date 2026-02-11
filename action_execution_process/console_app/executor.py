"""
ADB Executor Module
Executes Android Debug Bridge (ADB) commands to open apps

IMPORTANT LIMITATIONS:
1. This only OPENS apps - it does NOT control what happens inside the app
2. Requires USB debugging enabled on Android device
3. Device must be connected via USB or Wi-Fi ADB
4. Cannot bypass Android security or permissions
5. Cannot automate UI interactions (requires Accessibility Services)

For full app automation, you need:
- Android Accessibility Services
- UI Automator Framework
- Native Android code
- Or third-party automation tools (Appium, etc.)
"""

import subprocess
import sys
from typing import Tuple


class ADBExecutor:
    """Execute ADB commands to control Android device"""
    
    def __init__(self):
        self.adb_path = "adb"  # Assumes ADB is in PATH
    
    def check_adb_available(self) -> Tuple[bool, str]:
        """
        Check if ADB is installed and in PATH
        
        Returns:
            Tuple of (is_available, message)
        """
        try:
            result = subprocess.run(
                [self.adb_path, "version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0:
                version = result.stdout.split('\n')[0]
                return True, f"[OK] ADB available: {version}"
            else:
                return False, "[ERROR] ADB command failed"
        
        except FileNotFoundError:
            return False, "[ERROR] ADB not found in PATH. Please install Android Platform Tools."
        
        except Exception as e:
            return False, f"[ERROR] Error checking ADB: {str(e)}"
    
    def check_device_connected(self) -> Tuple[bool, str]:
        """
        Check if any Android device is connected
        
        Returns:
            Tuple of (is_connected, message)
        """
        try:
            result = subprocess.run(
                [self.adb_path, "devices"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode != 0:
                return False, "[ERROR] ADB devices command failed"
            
            # Parse output to find connected devices
            lines = result.stdout.strip().split('\n')[1:]  # Skip header
            devices = [line for line in lines if line.strip() and '\tdevice' in line]
            
            if devices:
                device_id = devices[0].split('\t')[0]
                return True, f"[OK] Device connected: {device_id}"
            else:
                return False, "[ERROR] No devices connected. Please connect Android device and enable USB debugging."
        
        except Exception as e:
            return False, f"[ERROR] Error checking devices: {str(e)}"
    
    def open_app(self, package_name: str) -> Tuple[bool, str]:
        """
        Open an Android app using its package name
        
        Args:
            package_name: Android package name (e.g., 'com.google.android.keep')
            
        Returns:
            Tuple of (success, message)
        """
        try:
            # Use monkey command to launch app
            # This is more reliable than 'am start' for various apps
            command = [
                self.adb_path,
                "shell",
                "monkey",
                "-p", package_name,
                "-c", "android.intent.category.LAUNCHER",
                "1"
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # Check if command executed successfully
            output = result.stdout + result.stderr
            
            if result.returncode == 0 and "Events injected: 1" in output:
                return True, f"[OK] App opened successfully: {package_name}"
            elif "No activities found" in output or "monkey: not found" in output:
                return False, f"[ERROR] App not found on device: {package_name}"
            else:
                return False, f"[ERROR] Failed to open app. Output: {output[:100]}"
        
        except subprocess.TimeoutExpired:
            return False, "[ERROR] Command timed out. Device may be unresponsive."
        
        except Exception as e:
            return False, f"[ERROR] Error opening app: {str(e)}"
    
    def check_app_installed(self, package_name: str) -> Tuple[bool, str]:
        """
        Check if an app is installed on the device
        
        Args:
            package_name: Android package name
            
        Returns:
            Tuple of (is_installed, message)
        """
        try:
            command = [
                self.adb_path,
                "shell",
                "pm", "list", "packages",
                package_name
            ]
            
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if result.returncode == 0 and package_name in result.stdout:
                return True, f"✅ App is installed: {package_name}"
            else:
                return False, f"❌ App not installed: {package_name}"
        
        except Exception as e:
            return False, f"❌ Error checking app: {str(e)}"
    
    def get_device_info(self) -> dict:
        """
        Get basic device information
        
        Returns:
            Dictionary with device info
        """
        info = {
            'manufacturer': 'Unknown',
            'model': 'Unknown',
            'android_version': 'Unknown'
        }
        
        try:
            # Get manufacturer
            result = subprocess.run(
                [self.adb_path, "shell", "getprop", "ro.product.manufacturer"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                info['manufacturer'] = result.stdout.strip()
            
            # Get model
            result = subprocess.run(
                [self.adb_path, "shell", "getprop", "ro.product.model"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                info['model'] = result.stdout.strip()
            
            # Get Android version
            result = subprocess.run(
                [self.adb_path, "shell", "getprop", "ro.build.version.release"],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                info['android_version'] = result.stdout.strip()
        
        except Exception:
            pass
        
        return info


# Example usage and testing
if __name__ == "__main__":
    print("🤖 ADB Executor Module - Testing")
    print("=" * 60)
    
    executor = ADBExecutor()
    
    # Check ADB
    available, msg = executor.check_adb_available()
    print(msg)
    
    if not available:
        print("\n⚠️ Please install ADB to continue.")
        sys.exit(1)
    
    # Check device
    connected, msg = executor.check_device_connected()
    print(msg)
    
    if not connected:
        print("\n⚠️ Please connect your Android device.")
        sys.exit(1)
    
    # Get device info
    print("\n📱 Device Information:")
    info = executor.get_device_info()
    print(f"   Manufacturer: {info['manufacturer']}")
    print(f"   Model: {info['model']}")
    print(f"   Android: {info['android_version']}")
    
    # Test opening Settings (should always be available)
    print("\n🧪 Testing app launch (Settings)...")
    success, msg = executor.open_app("com.android.settings")
    print(msg)
    
    print("\n" + "=" * 60)
    print("✅ ADB Executor test complete!")
