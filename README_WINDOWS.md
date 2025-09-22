# UniFi GUI - Windows Installation Guide

## Quick Start

### Option 1: Easy Installation (Recommended)
1. Double-click `install_windows.bat`
2. Follow the prompts
3. Run `python app.py`

### Option 2: Manual Installation
1. Install Python 3.8+ from [python.org](https://python.org)
2. Open Command Prompt as Administrator
3. Run: `pip install -r requirements-windows.txt`
4. Run: `python app.py`

## Prerequisites

- **Python 3.8 or higher**
- **Windows 10/11** (Windows 7/8 may work but not tested)
- **Internet connection** for initial setup

## Installation Steps

### 1. Install Python
- Download from [python.org](https://python.org)
- **Important**: Check "Add Python to PATH" during installation
- Verify installation: Open Command Prompt and run `python --version`

### 2. Install Dependencies
```cmd
# Run as Administrator
pip install -r requirements-windows.txt
```

### 3. Test Installation
```cmd
python windows_test.py
```

### 4. Run the Application
```cmd
python app.py
```

## Troubleshooting

### Common Issues

#### "ModuleNotFoundError: No module named 'PyQt5'"
**Solution**: Install PyQt5
```cmd
pip install PyQt5
```

#### "Permission denied" or "Access denied"
**Solution**: Run Command Prompt as Administrator

#### "SSL: CERTIFICATE_VERIFY_FAILED"
**Solution**: This is handled by the app's settings. Check your UniFi controller's SSL certificate.

#### Network discovery not working
**Solutions**:
- Run as Administrator
- Check Windows Firewall settings
- Add exception for Python/your app in Windows Defender

#### Antivirus blocking the app
**Solution**: Add exception for the app in your antivirus software

### Advanced Troubleshooting

#### Check Python Installation
```cmd
python --version
python -c "import sys; print(sys.executable)"
```

#### Check Installed Packages
```cmd
pip list
```

#### Test Individual Components
```cmd
python -c "import PyQt5; print('PyQt5 OK')"
python -c "import requests; print('requests OK')"
python -c "import paramiko; print('paramiko OK')"
python -c "import psutil; print('psutil OK')"
```

## Building Windows Executable

If you want to create a standalone executable:

### Option 1: Easy Build
1. Double-click `build_windows.bat`
2. The executable will be in the `dist` folder

### Option 2: Manual Build
```cmd
# Install PyInstaller
pip install pyinstaller

# Build executable
pyinstaller app.spec
```

## Windows-Specific Features

- **Settings Storage**: Settings are stored in `%USERPROFILE%\.innovative_unifi_tool.json`
- **Network Discovery**: Uses Windows-specific ping and ARP commands
- **Path Handling**: Uses cross-platform `os.path.join()` for file paths
- **SSL Handling**: Automatically handles Windows certificate store

## System Requirements

- **OS**: Windows 10/11 (64-bit recommended)
- **RAM**: 4GB minimum, 8GB recommended
- **Disk Space**: 100MB for application + dependencies
- **Network**: Access to UniFi controller

## Security Considerations

- The app may be flagged by antivirus software due to network operations
- Windows Defender may need to allow the app
- Consider running as Administrator for full network discovery features
- SSL verification can be disabled in settings if needed

## Getting Help

If you encounter issues:

1. Run `python windows_test.py` and check the output
2. Check the `WINDOWS_TROUBLESHOOTING.md` file
3. Ensure all dependencies are installed correctly
4. Try running as Administrator
5. Check Windows Firewall and antivirus settings

## File Structure

```
├── app.py                          # Main application
├── requirements-windows.txt        # Windows-specific dependencies
├── install_windows.bat            # Easy installation script
├── build_windows.bat              # Build executable script
├── windows_test.py                # Compatibility test script
├── WINDOWS_TROUBLESHOOTING.md     # Detailed troubleshooting guide
└── innovative_unifi/              # Application modules
    ├── core/                      # Core functionality
    └── ui/                        # User interface
```

## License

This application is provided as-is. Use at your own risk.
