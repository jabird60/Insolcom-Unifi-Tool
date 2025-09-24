#!/usr/bin/env python3
"""
GUI launcher script - runs the app without console window
"""
import sys
import os
import subprocess

def main():
    """Launch the GUI application"""
    try:
        # Get the directory of this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        app_script = os.path.join(script_dir, "app.py")
        
        # Check if app.py exists
        if not os.path.exists(app_script):
            print("Error: app.py not found")
            return 1
        
        # On Windows, use pythonw to suppress console
        if sys.platform.startswith("win"):
            # Use pythonw.exe to run without console window
            pythonw = os.path.join(os.path.dirname(sys.executable), "pythonw.exe")
            if os.path.exists(pythonw):
                subprocess.Popen([pythonw, app_script])
            else:
                # Fallback to regular python
                subprocess.Popen([sys.executable, app_script])
        else:
            # On other platforms, run normally
            subprocess.Popen([sys.executable, app_script])
        
        return 0
        
    except Exception as e:
        print(f"Error launching application: {e}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
