#!/usr/bin/env python3
"""
Windows compatibility test script
Run this on Windows to diagnose issues
"""
import sys
import platform

def test_imports():
    """Test all required imports"""
    print("Testing imports...")
    
    try:
        import PyQt5
        print("✓ PyQt5 imported successfully")
    except ImportError as e:
        print(f"✗ PyQt5 import failed: {e}")
        return False
    
    try:
        from PyQt5 import QtWidgets, QtCore, QtGui
        print("✓ PyQt5 modules imported successfully")
    except ImportError as e:
        print(f"✗ PyQt5 modules import failed: {e}")
        return False
    
    try:
        import requests
        print("✓ requests imported successfully")
    except ImportError as e:
        print(f"✗ requests import failed: {e}")
        return False
    
    try:
        import paramiko
        print("✓ paramiko imported successfully")
    except ImportError as e:
        print(f"✗ paramiko import failed: {e}")
        return False
    
    try:
        import psutil
        print("✓ psutil imported successfully")
    except ImportError as e:
        print(f"✗ psutil import failed: {e}")
        return False
    
    return True

def test_platform():
    """Test platform-specific functionality"""
    print("\nTesting platform-specific functionality...")
    
    print(f"Platform: {platform.platform()}")
    print(f"Python version: {sys.version}")
    print(f"Architecture: {platform.architecture()}")
    
    # Test Windows detection
    is_windows = sys.platform.startswith("win")
    print(f"Windows detected: {is_windows}")
    
    if is_windows:
        print("✓ Windows platform detection working")
    else:
        print("! Not running on Windows")
    
    return True

def test_qt_application():
    """Test if Qt application can be created"""
    print("\nTesting Qt application creation...")
    
    try:
        from PyQt5 import QtWidgets
        app = QtWidgets.QApplication([])
        print("✓ Qt application created successfully")
        app.quit()
        return True
    except Exception as e:
        print(f"✗ Qt application creation failed: {e}")
        return False

def test_network_discovery():
    """Test network discovery functionality"""
    print("\nTesting network discovery...")
    
    try:
        from innovative_unifi.core.discovery import local_ipv4_interfaces, _is_windows
        interfaces = local_ipv4_interfaces()
        print(f"✓ Found {len(interfaces)} network interfaces")
        for iface, ip, mask in interfaces:
            print(f"  - {iface}: {ip}/{mask}")
        return True
    except Exception as e:
        print(f"✗ Network discovery failed: {e}")
        return False

def test_controller_client():
    """Test controller client creation"""
    print("\nTesting controller client...")
    
    try:
        from innovative_unifi.core.settings_store import SettingsStore
        from innovative_unifi.core.controller import ControllerClient
        
        store = SettingsStore()
        ctrl = ControllerClient(store)
        print("✓ Controller client created successfully")
        return True
    except Exception as e:
        print(f"✗ Controller client creation failed: {e}")
        return False

def main():
    """Run all tests"""
    print("Windows Compatibility Test")
    print("=" * 40)
    
    tests = [
        test_imports,
        test_platform,
        test_qt_application,
        test_network_discovery,
        test_controller_client
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        try:
            if test():
                passed += 1
        except Exception as e:
            print(f"✗ Test {test.__name__} failed with exception: {e}")
    
    print("\n" + "=" * 40)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("✓ All tests passed! The app should work on Windows.")
    else:
        print("✗ Some tests failed. Check the output above for details.")
        print("\nCommon solutions:")
        print("1. Install missing dependencies: pip install -r requirements.txt")
        print("2. Install PyQt5: pip install PyQt5")
        print("3. Run as Administrator if needed")
        print("4. Check Windows Firewall settings")

if __name__ == "__main__":
    main()
