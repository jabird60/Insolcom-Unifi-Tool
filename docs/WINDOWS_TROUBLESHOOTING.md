# Windows Troubleshooting Guide

## Common Windows Issues and Solutions

### 1. PyQt5 Installation Issues

**Problem**: `ModuleNotFoundError: No module named 'PyQt5'`

**Solutions**:
```bash
# Option 1: Install via pip
pip install PyQt5

# Option 2: Install via conda (if using Anaconda)
conda install pyqt

# Option 3: Install specific version
pip install PyQt5==5.15.11

# Option 4: Install with all dependencies
pip install PyQt5 requests paramiko psutil
```

### 2. SSL/TLS Certificate Issues

**Problem**: SSL certificate verification errors on Windows

**Solutions**:
- The app already handles SSL verification with `verify_ssl` setting
- If issues persist, try setting `verify_ssl` to `False` in settings
- Ensure Windows has updated certificates

### 3. Missing Dependencies

**Problem**: Missing Windows-specific modules

**Solutions**:
```bash
# Install all requirements
pip install -r requirements.txt

# Install additional Windows dependencies
pip install pywin32
pip install cryptography
```

### 4. Path Issues

**Problem**: File path handling differences between Windows and macOS

**Solutions**:
- The app uses `os.path.join()` which is cross-platform compatible
- Settings file is stored in user home directory: `~/.innovative_unifi_tool.json`

### 5. Network Discovery Issues

**Problem**: Network discovery not working on Windows

**Solutions**:
- Ensure Windows Firewall allows Python/your app
- Run as Administrator if needed
- Check if Windows Defender is blocking the app

### 6. PyInstaller Issues (if building executable)

**Problem**: Missing modules when building with PyInstaller

**Solutions**:
```bash
# Install PyInstaller
pip install pyinstaller

# Build with additional hidden imports
pyinstaller --hidden-import=PyQt5.QtCore --hidden-import=PyQt5.QtWidgets --hidden-import=PyQt5.QtGui app.py

# Or use the provided spec file
pyinstaller app.spec
```

## Step-by-Step Windows Setup

1. **Install Python 3.8+**:
   - Download from python.org
   - Make sure to check "Add Python to PATH"

2. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the Application**:
   ```bash
   python app.py
   ```

4. **If PyQt5 Issues Persist**:
   ```bash
   # Try installing from conda-forge
   conda install -c conda-forge pyqt
   
   # Or try the wheel version
   pip install --only-binary=all PyQt5
   ```

## Windows-Specific Considerations

- **Antivirus Software**: May flag the app as suspicious due to network operations
- **Windows Defender**: May need to add exception for the app
- **User Account Control**: May need to run as Administrator for network operations
- **Firewall**: Windows Firewall may block network discovery

## Debugging Steps

1. **Check Python Version**:
   ```bash
   python --version
   ```

2. **Check Installed Packages**:
   ```bash
   pip list
   ```

3. **Run with Verbose Output**:
   ```bash
   python -v app.py
   ```

4. **Check for Import Errors**:
   ```bash
   python -c "import PyQt5; print('PyQt5 OK')"
   python -c "import requests; print('requests OK')"
   python -c "import paramiko; print('paramiko OK')"
   python -c "import psutil; print('psutil OK')"
   ```

## Common Error Messages and Solutions

### "No module named 'PyQt5'"
- Install PyQt5: `pip install PyQt5`

### "SSL: CERTIFICATE_VERIFY_FAILED"
- This is handled by the app's SSL verification setting
- Check your controller's SSL certificate

### "Permission denied" or "Access denied"
- Run as Administrator
- Check Windows Firewall settings

### "ModuleNotFoundError: No module named 'psutil'"
- Install psutil: `pip install psutil`

## Building Windows Executable

If you want to create a Windows executable:

```bash
# Install PyInstaller
pip install pyinstaller

# Build the executable
pyinstaller app.spec

# The executable will be in the 'dist' folder
```

## Still Having Issues?

If you're still experiencing problems, please provide:
1. The exact error message
2. Python version (`python --version`)
3. Operating system version
4. Whether you're running from source or executable
5. Any antivirus software running
