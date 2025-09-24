@echo off
echo Building UniFi GUI for Windows...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    pause
    exit /b 1
)

REM Check if PyInstaller is installed
pip show pyinstaller >nul 2>&1
if errorlevel 1 (
    echo Installing PyInstaller...
    pip install pyinstaller
    if errorlevel 1 (
        echo ERROR: Failed to install PyInstaller
        pause
        exit /b 1
    )
)

REM Create app icon
echo Creating app icon...
python setup_icon.py
if errorlevel 1 (
    echo WARNING: Icon creation failed, continuing without custom icon...
)

echo Building executable...
pyinstaller app.spec

if errorlevel 1 (
    echo.
    echo ERROR: Build failed
    echo Check the output above for details
    pause
    exit /b 1
)

echo.
echo Build completed successfully!
echo The executable is in the 'dist' folder
echo The app will launch without a console window
echo.
pause
