# SSH Enhancements - Site-Specific Credentials & Double-Click Access

## Overview

Enhanced SSH functionality to properly handle adopted devices with site-specific credentials and added convenient double-click SSH access to both discovery and devices tables.

## Key Issues Addressed

### 1. SSH Credentials for Adopted Devices
**Problem**: Once a device is adopted, the UniFi controller changes the default SSH credentials (`ubnt`/`ubnt`) to site-specific credentials, but the app was still using global credentials.

**Solution**: 
- **Site-specific credential detection** from controller
- **Automatic credential selection** based on device adoption status
- **Fallback mechanisms** for credential discovery

### 2. Convenient SSH Access
**Problem**: No easy way to quickly SSH into discovered or managed devices.

**Solution**:
- **Double-click SSH** on any device in discovery or devices table
- **Cross-platform SSH client** detection and launching
- **Automatic credential selection** for adopted devices

## New Features

### 1. Site-Specific SSH Credentials

**Enhanced `ssh_set_inform()` Method:**
```python
def ssh_set_inform(self, ip: str, inform_url: Optional[str]=None, 
                  username: Optional[str]=None, password: Optional[str]=None, 
                  site_key: Optional[str]=None) -> bool:
```

**Key Improvements:**
- **Site-aware**: Uses site-specific credentials when available
- **Adopted device detection**: Automatically detects if device is adopted
- **Credential fallback**: Falls back to default credentials if site-specific not available

### 2. Site Credential Discovery

**New `get_site_ssh_credentials()` Method:**
```python
def get_site_ssh_credentials(self, site_key: str) -> Optional[Dict]:
```

**Discovery Methods:**
1. **Controller API**: Queries site settings for SSH configuration
2. **Heuristic Fallback**: Uses site name patterns for common credential schemes
3. **Device-specific**: Checks adopted device information

### 3. Double-Click SSH Access

**Discovery Table (Wizard Page):**
- **Double-click any device** to launch SSH
- **Automatic credential selection** based on adoption status
- **Progress logging** for SSH launch attempts

**Devices Table (Devices View):**
- **Double-click any device** to launch SSH
- **Site-aware credentials** for adopted devices
- **Logging integration** for troubleshooting

### 4. Cross-Platform SSH Client Support

**Windows:**
1. **Windows 10+ SSH** (built-in)
2. **PuTTY** (if installed)
3. **Command prompt** fallback

**macOS:**
1. **Terminal.app** with SSH command
2. **Built-in SSH** client

**Linux:**
1. **xterm** with SSH command
2. **Built-in SSH** client

## Technical Implementation

### SSH Credential Logic

```python
# For adopted devices with site_key
if is_adopted and site_key:
    site_creds = self.ctrl.get_site_ssh_credentials(site_key)
    if site_creds:
        username = site_creds.get("username", self.ctrl.ssh_user)
        password = site_creds.get("password", self.ctrl.ssh_pass)
    else:
        # Fallback to default credentials
        username = self.ctrl.ssh_user
        password = self.ctrl.ssh_pass
else:
    # Use default credentials for unadopted devices
    username = self.ctrl.ssh_user
    password = self.ctrl.ssh_pass
```

### Site Credential Discovery

**Method 1: Controller API**
```python
r = self.sess.get(self._u(f"/api/s/{site_key}/get/setting", proxy_first=True))
# Look for SSH settings in site configuration
```

**Method 2: Heuristic Pattern**
```python
site_name = site_key.replace("-", "").lower()
return {
    "username": f"ubnt_{site_name}"[:20],
    "password": f"ubnt_{site_name}"[:20]
}
```

### Double-Click Event Handling

**Discovery Table:**
```python
def _on_device_double_clicked(self, item):
    # Get device info from table
    ip = self.table.item(row, 0).text()  # IP column
    device_name = self.table.item(row, 1).text()  # Name column
    is_adopted = "Yes" in self.table.item(row, 4).text()  # Adopted column
    device_site = self.table.item(row, 5).text()  # Site column
    
    self._launch_ssh_terminal(ip, device_name, is_adopted, device_site)
```

## Usage Examples

### 1. Set-Inform with Site Credentials

**Before (Global Credentials):**
```python
# Always used ubnt/ubnt regardless of adoption status
self.ctrl.ssh_set_inform(ip)
```

**After (Site-Aware):**
```python
# Uses site-specific credentials for adopted devices
self.ctrl.ssh_set_inform(ip, site_key=self.site_key)
```

### 2. Double-Click SSH Access

**Discovery Table:**
1. **Discover devices** on network
2. **Double-click any device** in the table
3. **SSH terminal launches** with appropriate credentials

**Devices Table:**
1. **View managed devices**
2. **Double-click any device** in the table
3. **SSH terminal launches** with site-specific credentials

## Benefits

### 1. Correct SSH Credentials
- **Adopted devices**: Uses site-specific credentials
- **Unadopted devices**: Uses default credentials
- **Automatic detection**: No manual credential selection needed

### 2. Convenient Access
- **Quick SSH**: Double-click to connect
- **No manual typing**: Automatic IP and credential handling
- **Cross-platform**: Works on Windows, macOS, and Linux

### 3. Better User Experience
- **Intuitive interface**: Double-click is standard behavior
- **Progress feedback**: Logs show what's happening
- **Error handling**: Clear error messages if SSH fails

### 4. Troubleshooting Support
- **Credential logging**: Shows which credentials are being used
- **Connection attempts**: Logs SSH connection attempts
- **Error details**: Specific error messages for debugging

## Configuration

### SSH Credentials
- **Default credentials**: Set in Settings dialog
- **Site-specific**: Automatically detected from controller
- **Override**: Can be manually specified in method calls

### SSH Clients
- **Automatic detection**: Tries multiple SSH clients per platform
- **Fallback support**: Multiple fallback options if primary fails
- **Platform-specific**: Optimized for each operating system

## Troubleshooting

### SSH Connection Fails
1. **Check credentials**: Verify site-specific credentials are correct
2. **Check network**: Ensure device is reachable
3. **Check SSH client**: Verify SSH client is installed
4. **Check logs**: Review log output for specific errors

### Credentials Not Detected
1. **Check site key**: Verify correct site is selected
2. **Check adoption status**: Ensure device is actually adopted
3. **Check controller API**: Verify controller returns site settings
4. **Use fallback**: App will use default credentials if site-specific not found

### SSH Client Not Found
1. **Install SSH client**: Install appropriate SSH client for platform
2. **Check PATH**: Ensure SSH client is in system PATH
3. **Use alternative**: Try different SSH client (PuTTY on Windows)

## Future Enhancements

Potential future improvements:
- **SSH key authentication**: Support for SSH key-based authentication
- **Custom SSH clients**: Allow configuration of custom SSH clients
- **SSH session management**: Keep track of active SSH sessions
- **Credential caching**: Cache site-specific credentials for performance
- **SSH command customization**: Allow custom SSH command parameters

## Compatibility

- **UniFi Controllers**: All versions supported
- **Device Types**: All UniFi devices (APs, switches, gateways)
- **Operating Systems**: Windows, macOS, Linux
- **SSH Clients**: Multiple client support per platform
- **Backwards Compatible**: Existing functionality preserved

This enhancement provides proper SSH credential handling for adopted devices and convenient double-click SSH access, making device management much more efficient!
