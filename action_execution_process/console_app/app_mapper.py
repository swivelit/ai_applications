"""
App Mapper Module
Maps application names to Android package names

IMPORTANT LIMITATION:
This mapping is approximate. Actual package names vary by:
- Device manufacturer (Samsung, Xiaomi, OnePlus, etc.)
- Android version
- Pre-installed vs downloaded apps

For production use, implement dynamic package discovery.
"""

# Standard Android app package names
APP_PACKAGES = {
    # Notes apps
    'notes': 'com.google.android.keep',
    'keep': 'com.google.android.keep',
    'note': 'com.google.android.keep',
    
    # Clock/Alarm apps
    'clock': 'com.google.android.deskclock',
    'alarm': 'com.google.android.deskclock',
    'timer': 'com.google.android.deskclock',
    
    # Calculator
    'calculator': 'com.android.calculator2',
    'calc': 'com.android.calculator2',
    
    # Settings
    'settings': 'com.android.settings',
    
    # Calendar
    'calendar': 'com.google.android.calendar',
    'cal': 'com.google.android.calendar',
    
    # Messages
    'messages': 'com.google.android.apps.messaging',
    'sms': 'com.google.android.apps.messaging',
    'text': 'com.google.android.apps.messaging',
    
    # Phone/Dialer
    'phone': 'com.google.android.dialer',
    'dialer': 'com.google.android.dialer',
    'call': 'com.google.android.dialer',
    
    # Contacts
    'contacts': 'com.google.android.contacts',
    
    # Camera
    'camera': 'com.android.camera2',
    'cam': 'com.android.camera2',
    
    # Gallery/Photos
    'gallery': 'com.google.android.apps.photos',
    'photos': 'com.google.android.apps.photos',
    
    # Browser
    'chrome': 'com.android.chrome',
    'browser': 'com.android.browser',
    
    # Maps
    'maps': 'com.google.android.apps.maps',
    
    # YouTube
    'youtube': 'com.google.android.youtube',
    
    # WhatsApp
    'whatsapp': 'com.whatsapp',
    
    # Gmail
    'gmail': 'com.google.android.gm',
    'email': 'com.google.android.gm',
}

# Alternative package names for different manufacturers
ALTERNATIVE_PACKAGES = {
    'notes': [
        'com.google.android.keep',
        'com.samsung.android.app.notes',
        'com.miui.notes',
        'com.oneplus.note'
    ],
    'clock': [
        'com.google.android.deskclock',
        'com.sec.android.app.clockpackage',  # Samsung
        'com.android.deskclock'
    ],
    'calculator': [
        'com.android.calculator2',
        'com.google.android.calculator',
        'com.sec.android.app.calculator',  # Samsung
        'com.miui.calculator'  # Xiaomi
    ],
    'camera': [
        'com.android.camera2',
        'com.google.android.GoogleCamera',
        'com.sec.android.app.camera',  # Samsung
        'com.android.camera'
    ]
}


def get_package_name(app_name: str) -> str:
    """
    Get Android package name for an app
    
    Args:
        app_name: User-friendly app name (e.g., 'notes', 'clock')
        
    Returns:
        Android package name string
        
    Raises:
        ValueError: If app name is not recognized
    """
    app_name = app_name.lower().strip()
    
    if app_name in APP_PACKAGES:
        return APP_PACKAGES[app_name]
    else:
        raise ValueError(f"Unknown app: '{app_name}'. Available apps: {', '.join(get_available_apps())}")


def get_available_apps() -> list:
    """
    Get list of all supported app names
    
    Returns:
        List of app name strings
    """
    # Remove duplicates by converting to set
    unique_apps = sorted(set(APP_PACKAGES.keys()))
    return unique_apps


def get_primary_apps() -> list:
    """
    Get list of primary/main app names (not aliases)
    
    Returns:
        List of primary app names
    """
    primary = ['notes', 'clock', 'calculator', 'settings', 'calendar', 
               'messages', 'phone', 'camera', 'chrome', 'whatsapp']
    return primary


def get_alternative_packages(app_name: str) -> list:
    """
    Get alternative package names for different manufacturers
    
    Args:
        app_name: User-friendly app name
        
    Returns:
        List of alternative package names to try
    """
    app_name = app_name.lower().strip()
    
    if app_name in ALTERNATIVE_PACKAGES:
        return ALTERNATIVE_PACKAGES[app_name]
    else:
        # Return primary package in a list
        try:
            return [get_package_name(app_name)]
        except ValueError:
            return []


def is_app_supported(app_name: str) -> bool:
    """
    Check if an app is supported
    
    Args:
        app_name: User-friendly app name
        
    Returns:
        True if supported, False otherwise
    """
    return app_name.lower().strip() in APP_PACKAGES


def get_app_display_name(app_name: str) -> str:
    """
    Get display-friendly app name
    
    Args:
        app_name: User-friendly app name
        
    Returns:
        Capitalized display name
    """
    display_names = {
        'notes': 'Google Keep',
        'keep': 'Google Keep',
        'clock': 'Clock',
        'calculator': 'Calculator',
        'settings': 'Settings',
        'calendar': 'Google Calendar',
        'messages': 'Messages',
        'phone': 'Phone',
        'camera': 'Camera',
        'chrome': 'Chrome',
        'whatsapp': 'WhatsApp',
        'gmail': 'Gmail'
    }
    
    app_name = app_name.lower().strip()
    return display_names.get(app_name, app_name.capitalize())


# Example usage and testing
if __name__ == "__main__":
    print("🗺️ App Mapper Module - Testing")
    print("=" * 50)
    
    # Test getting package names
    test_apps = ['notes', 'clock', 'calculator', 'settings']
    
    for app in test_apps:
        try:
            package = get_package_name(app)
            display = get_app_display_name(app)
            print(f"✅ {app:12} → {display:20} → {package}")
        except ValueError as e:
            print(f"❌ {app}: {e}")
    
    print("\n" + "=" * 50)
    print(f"📱 Total supported apps: {len(get_available_apps())}")
    print(f"🎯 Primary apps: {', '.join(get_primary_apps())}")
