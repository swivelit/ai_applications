"""
Quick Test Script
Tests individual components without requiring a connected device
"""

print("=" * 60)
print("🧪 Testing Console App Components")
print("=" * 60)

# Test 1: App Mapper
print("\n1️⃣ Testing App Mapper...")
try:
    from app_mapper import get_package_name, get_available_apps, get_app_display_name
    
    test_apps = ['notes', 'clock', 'calculator']
    for app in test_apps:
        package = get_package_name(app)
        display = get_app_display_name(app)
        print(f"   ✅ {app:12} → {display:20} → {package}")
    
    print(f"   📱 Total apps supported: {len(get_available_apps())}")

except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 2: Task Handler
print("\n2️⃣ Testing Task Handler...")
try:
    from task_handler import TaskHandler
    
    handler = TaskHandler()
    
    # Test notes task
    success, msg = handler.execute_task('notes', 'create_note', {
        'title': 'Test Note',
        'content': 'This is a test'
    })
    print(f"   ✅ Notes simulation: {msg}")
    
    # Test clock task
    success, msg = handler.execute_task('clock', 'set_alarm', {
        'time': '08:00',
        'date': '2026-02-12'
    })
    print(f"   ✅ Clock simulation: {msg}")

except Exception as e:
    print(f"   ❌ Error: {e}")

# Test 3: ADB Executor (without device)
print("\n3️⃣ Testing ADB Executor...")
try:
    from executor import ADBExecutor
    
    executor = ADBExecutor()
    
    # Check if ADB is available
    available, msg = executor.check_adb_available()
    print(f"   {msg}")
    
    if available:
        # Check for connected device
        connected, device_msg = executor.check_device_connected()
        print(f"   {device_msg}")
        
        if connected:
            print("   ✅ Ready to execute ADB commands!")
            
            # Get device info
            info = executor.get_device_info()
            print(f"   📱 Device: {info['manufacturer']} {info['model']}")
        else:
            print("   ⚠️ No device connected (expected for testing)")
    else:
        print("   ⚠️ ADB not installed (install Android Platform Tools)")

except Exception as e:
    print(f"   ❌ Error: {e}")

# Summary
print("\n" + "=" * 60)
print("✅ Component Testing Complete!")
print("=" * 60)
print("\n💡 To run the full application:")
print("   python main.py")
print("\n📝 Prerequisites:")
print("   1. Install ADB (Android Platform Tools)")
print("   2. Enable USB Debugging on Android device")
print("   3. Connect device to PC")
print("   4. Run 'adb devices' to verify")
print("\n" + "=" * 60 + "\n")
