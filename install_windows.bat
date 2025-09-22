@echo off
echo Installing UniFi GUI for Windows...
echo.

REM Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ERROR: Python is not installed or not in PATH
    echo Please install Python 3.8+ from https://python.org
    echo Make sure to check "Add Python to PATH" during installation
    pause
    exit /b 1
)

echo Python found. Installing dependencies...
echo.

REM Install requirements
pip install -r requirements-windows.txt

if errorlevel 1 (
    echo.
    echo ERROR: Failed to install some dependencies
    echo Try running as Administrator or check your internet connection
    pause
    exit /b 1
)

echo.
echo Dependencies installed successfully!
echo.

REM Test the installation
echo Testing installation...
python windows_test.py

if errorlevel 1 (
    echo.
    echo WARNING: Some tests failed. Check the output above.
    echo You may need to install additional dependencies or run as Administrator.
) else (
    echo.
    echo Installation test passed! You can now run the application.
)

echo.
echo To run the application, use: python app.py
echo.
pause
