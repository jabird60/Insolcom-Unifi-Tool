# 🚀 Innovative Solutions UniFi GUI

A comprehensive, enhanced UniFi Network Management GUI with advanced features for device management, WiFi configuration, and network monitoring.

## ✨ **Key Features**

### 🔧 **Enhanced UniFi Management**
- **Device Discovery & Adoption** - Automatic device discovery with SSH set-inform
- **WiFi Network Management** - Create, configure, and manage WLANs with advanced settings
- **Site Management** - Multi-site support with validation and active site filtering
- **Real-time Monitoring** - Live device status and network statistics

### 🚀 **Advanced Capabilities**
- **Smart API Detection** - Automatic v1/v2 API version detection and hybrid approach
- **Performance Optimized** - Intelligent caching for faster operations
- **Enhanced Error Handling** - Comprehensive validation and user-friendly error messages
- **Cross-Platform Support** - Windows, macOS, and Linux compatibility

### 📊 **System Information**
- **Controller Status** - Version, uptime, hostname, and system health
- **Device Counts** - Total devices across all sites
- **Site Statistics** - Active sites, device distribution, and site validation

## 🛠️ **Installation**

### **Prerequisites**
- Python 3.8 or higher
- UniFi Network Controller (version 6.0+ recommended)
- Network access to UniFi controller

### **Quick Start**

1. **Clone the repository:**
   ```bash
   git clone https://github.com/yourusername/InnovativeSolutions-UnifiGUI.git
   cd InnovativeSolutions-UnifiGUI
   ```

2. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

3. **Run the application:**
   ```bash
   python app.py
   ```

### **Windows Installation**
```bash
# Run the Windows installer
install_windows.bat

# Or build from source
build_windows.bat
```

## 📋 **Usage**

### **Initial Setup**
1. Launch the application
2. Configure UniFi controller settings:
   - Controller URL (e.g., `https://your-controller.com:8443`)
   - Username and password
   - SSL verification preferences
3. Test connection and save settings

### **Device Management**
- **Discovery**: Automatically discover unadopted devices
- **Adoption**: One-click device adoption with SSH set-inform
- **Configuration**: Set device aliases and manage settings
- **Monitoring**: Real-time device status and statistics

### **WiFi Management**
- **WLAN Creation**: Create new WiFi networks with advanced settings
- **Site-Specific**: Automatic site validation and group ID detection
- **Security Options**: WPA2/WPA3, guest networks, VLAN support
- **AP Assignment**: Configure which access points broadcast each network

## 🔧 **Advanced Features**

### **Enhanced API Integration**
- **v2 API Support**: Automatic detection and use of UniFi v2 API endpoints
- **Hybrid Approach**: v2 for AP groups, v1 for WLAN groups and creation
- **Smart Fallbacks**: Automatic fallback to compatible API versions
- **Performance Caching**: 5-minute cache for system info and sites

### **Site Management**
- **Validation**: Pre-operation site validation prevents errors
- **Active Filtering**: Show only sites with devices or marked as active
- **Comprehensive Info**: Device counts, descriptions, and status per site

### **Error Handling**
- **Site Validation**: Verify site exists before operations
- **Group ID Detection**: Automatic detection of AP and WLAN group IDs
- **Graceful Failures**: Clear error messages and recovery suggestions

## 📁 **Project Structure**

```
InnovativeSolutions-UnifiGUI/
├── app.py                    # Main application entry point
├── innovative_unifi/         # Core application package
│   ├── core/                # Core functionality
│   │   ├── controller.py    # Enhanced UniFi controller client
│   │   ├── discovery.py     # Device discovery system
│   │   ├── logger_bus.py    # Logging infrastructure
│   │   └── settings_store.py # Settings management
│   └── ui/                  # User interface
│       ├── main_window.py   # Main application window
│       ├── devices_view.py  # Device management interface
│       ├── wifi_view.py     # WiFi management interface
│       ├── settings_dialog.py # Settings configuration
│       └── wizard_page.py   # Setup wizard
├── requirements.txt         # Python dependencies
└── docs/                   # Documentation
```

## 🔧 **Configuration**

### **UniFi Controller Settings**
- **URL**: Full URL to your UniFi controller (including port)
- **Credentials**: Admin username and password
- **SSL**: Enable/disable SSL certificate verification
- **SSH**: SSH credentials for device adoption (default: ubnt/ubnt)

### **Advanced Options**
- **API Version**: Automatic detection with manual override
- **Cache Duration**: Configurable cache duration (default: 5 minutes)
- **Logging**: Comprehensive logging with toggle controls
- **Proxy Settings**: Support for proxy configurations


## 📚 **Documentation**

- [Device View Enhancements](docs/DEVICES_VIEW_ENHANCEMENTS.md)
- [Discovery Features](docs/DISCOVERY_ENHANCEMENTS.md)
- [Logging System](docs/LOG_TOGGLE_FEATURE.md)
- [SSH Features](docs/SSH_ENHANCEMENTS.md)
- [Windows Troubleshooting](docs/WINDOWS_TROUBLESHOOTING.md)

## 🤝 **Contributing**

We welcome contributions! Please see our contributing guidelines:

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests if applicable
5. Submit a pull request

## 📝 **Recent Enhancements**

### **v2.0.0 - Major Update**
- ✅ **Enhanced System Information**: Version, uptime, hostname display
- ✅ **Smart API Detection**: v1/v2 hybrid approach
- ✅ **Performance Optimization**: Intelligent caching system
- ✅ **Site Validation**: Pre-operation validation prevents errors
- ✅ **Corrected WLAN Creation**: Fixed payload structure and endpoints
- ✅ **Cross-Platform Support**: Windows, macOS, Linux compatibility

### **Key Improvements**
- **75+ Sites Supported**: Enhanced site management with validation
- **289+ Devices**: Optimized device handling across multiple sites
- **v2 API Integration**: Future-proof API compatibility
- **Error Prevention**: Comprehensive validation and error handling

## 🐛 **Troubleshooting**

### **Common Issues**
- **Connection Failed**: Check controller URL, credentials, and network access
- **SSL Errors**: Disable SSL verification or install proper certificates
- **Device Not Found**: Ensure devices are powered on and network accessible
- **WLAN Creation Failed**: Verify site has adopted access points

### **Windows Issues**
See [Windows Troubleshooting Guide](docs/WINDOWS_TROUBLESHOOTING.md) for specific Windows-related issues.

## 📄 **License**

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 **Acknowledgments**

- **UniFi Community** - For API documentation and community support
- **PyQt5** - For the excellent GUI framework
- **Requests** - For robust HTTP client functionality
- **Paramiko** - For SSH connectivity

## 📞 **Support**

- **Issues**: Report bugs and request features on GitHub Issues
- **Discussions**: Join community discussions on GitHub Discussions
- **Documentation**: Check the docs/ folder for detailed guides

---

**Made with ❤️ for the UniFi community**
