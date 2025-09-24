from PyQt5 import QtWidgets, QtCore, QtGui
from ..core.controller import ControllerClient

def _fmt_speed(mbps):
    try:
        m = float(mbps)
        if m >= 1000:
            g = m/1000.0
            if abs(round(g) - g) < 1e-6:
                return f"{int(round(g))} Gbps"
            return f"{g:.1f} Gbps"
        return f"{int(m)} Mbps"
    except Exception:
        return str(mbps)

def _check_update_available(dev: dict) -> str:
    """Check if a firmware update is available for the device"""
    try:
        # Check if device has update information
        version = dev.get("version", "")
        upgradable = dev.get("upgradable", False)
        need_upgrade = dev.get("need_upgrade", False)
        
        # Check various update indicators
        if upgradable or need_upgrade:
            return "Yes"
        
        # Check if there's a newer version available (heuristic)
        # This is a basic check - the controller should provide more accurate info
        if dev.get("upgrade_to_firmware"):
            return "Yes"
            
        return "No"
    except Exception:
        return "Unknown"

def _max_cap_from_tables(dev: dict):
    """Get maximum uplink capability from device data or known model specifications"""
    
    # First try to get from ethernet/port tables (prefer uplink port)
    uplink_port = None
    upl = dev.get("uplink") or {}
    if isinstance(upl, dict):
        uplink_port = upl.get("port_idx")
    
    best = 0
    for key in ("ethernet_table", "port_table"):
        for p in dev.get(key, []) or []:
            caps = p.get("speed_caps") or []
            if isinstance(caps, list):
                best = max(best, max(caps) if caps else 0)
                if uplink_port is not None and p.get("port_idx") == uplink_port and caps:
                    return max(caps)
            elif isinstance(caps, int):
                best = max(best, caps)
                if uplink_port is not None and p.get("port_idx") == uplink_port:
                    return caps
    
    # If we found something from tables, use it
    if best > 0:
        return best
    
    # Fallback to known model specifications
    model = (dev.get("model") or "").lower()
    device_type = (dev.get("type") or dev.get("device_type") or "").lower()
    
    # UniFi Access Points
    if "uap" in device_type or "ap" in device_type:
        if "u6-pro" in model:
            return 1000  # 1 Gbps
        elif "u6-lr" in model:
            return 1000  # 1 Gbps
        elif "u6-lite" in model:
            return 1000  # 1 Gbps
        elif "u6-mesh" in model:
            return 1000  # 1 Gbps
        elif "u6-extender" in model:
            return 1000  # 1 Gbps
        elif "u6-enterprise" in model:
            return 2500  # 2.5 Gbps
        elif "u6-enterprise-in-wall" in model:
            return 1000  # 1 Gbps
        elif "u7-pro" in model:
            return 2500  # 2.5 Gbps
        elif "u7-enterprise" in model:
            return 10000  # 10 Gbps
        elif "uap-ac-pro" in model:
            return 1000  # 1 Gbps
        elif "uap-ac-lr" in model:
            return 1000  # 1 Gbps
        elif "uap-ac-lite" in model:
            return 1000  # 1 Gbps
        elif "uap-ac-mesh" in model:
            return 1000  # 1 Gbps
        elif "uap-ac-iw" in model:
            return 1000  # 1 Gbps
        elif "uap-ac-m" in model:
            return 1000  # 1 Gbps
        elif "uap-ac-hd" in model:
            return 1000  # 1 Gbps
        elif "uap-ac-shd" in model:
            return 1000  # 1 Gbps
        elif "uap-ac-xg" in model:
            return 10000  # 10 Gbps
        elif "uap-iw-hd" in model:
            return 1000  # 1 Gbps
        elif "uap-flexhd" in model:
            return 1000  # 1 Gbps
        elif "uap-beaconhd" in model:
            return 1000  # 1 Gbps
        elif "uap-nanohd" in model:
            return 1000  # 1 Gbps
        elif "uap-iw" in model:
            return 1000  # 1 Gbps
        elif "uap" in model and "ac" in model:
            return 1000  # Default for AC series
        elif "uap" in model and "6" in model:
            return 1000  # Default for U6 series
    
    # UniFi Switches
    elif "usw" in device_type or "switch" in device_type:
        if "usw-enterprise-24-poe" in model:
            return 10000  # 10 Gbps SFP+
        elif "usw-enterprise-48-poe" in model:
            return 10000  # 10 Gbps SFP+
        elif "usw-enterprise-8-poe" in model:
            return 10000  # 10 Gbps SFP+
        elif "usw-enterprise-24" in model:
            return 10000  # 10 Gbps SFP+
        elif "usw-enterprise-48" in model:
            return 10000  # 10 Gbps SFP+
        elif "usw-enterprise-8" in model:
            return 10000  # 10 Gbps SFP+
        elif "usw-pro-24-poe" in model:
            return 10000  # 10 Gbps SFP+
        elif "usw-pro-48-poe" in model:
            return 10000  # 10 Gbps SFP+
        elif "usw-pro-24" in model:
            return 10000  # 10 Gbps SFP+
        elif "usw-pro-48" in model:
            return 10000  # 10 Gbps SFP+
        elif "usw-24-poe" in model:
            return 1000  # 1 Gbps
        elif "usw-48-poe" in model:
            return 1000  # 1 Gbps
        elif "usw-24" in model:
            return 1000  # 1 Gbps
        elif "usw-48" in model:
            return 1000  # 1 Gbps
        elif "usw-16-poe" in model:
            return 1000  # 1 Gbps
        elif "usw-8-poe" in model:
            return 1000  # 1 Gbps
        elif "usw-8" in model:
            return 1000  # 1 Gbps
        elif "usw-flex" in model:
            return 1000  # 1 Gbps
        elif "usw-lite-8-poe" in model:
            return 1000  # 1 Gbps
        elif "usw-lite-16-poe" in model:
            return 1000  # 1 Gbps
        elif "usw" in model:
            return 1000  # Default for USW series
    
    # UniFi Gateways/Routers
    elif "ugw" in device_type or "gateway" in device_type or "router" in device_type:
        if "udm-pro" in model:
            return 10000  # 10 Gbps SFP+
        elif "udm-se" in model:
            return 10000  # 10 Gbps SFP+
        elif "udr" in model:
            return 1000  # 1 Gbps
        elif "udm" in model:
            return 1000  # 1 Gbps
        elif "usg" in model:
            return 1000  # 1 Gbps
        elif "uxg" in model:
            return 10000  # 10 Gbps SFP+
    
    # Default fallback
    return None

class DevicesView(QtWidgets.QWidget):
    def __init__(self, ctrl: ControllerClient, log_bus=None, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.log = (log_bus.log if log_bus else (lambda s: None))
        self.site_key = "default"

        # Controls
        top = QtWidgets.QHBoxLayout()
        self.ed_filter = QtWidgets.QLineEdit()
        self.ed_filter.setPlaceholderText("Filter by name/model/MAC…")
        self.btn_refresh = QtWidgets.QPushButton("Refresh")
        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_upgrade_sel = QtWidgets.QPushButton("Upgrade Firmware (Selected)")
        self.btn_upgrade_sel.clicked.connect(self.upgrade_selected)
        self.btn_upgrade_all = QtWidgets.QPushButton("Bulk Upgrade (All upgradable)")
        self.btn_upgrade_all.clicked.connect(self.upgrade_all)
        self.btn_debug = QtWidgets.QPushButton("Debug Speed Info")
        self.btn_debug.clicked.connect(self.debug_speed_info)
        self.btn_test_ssh = QtWidgets.QPushButton("Test SSH Launch")
        self.btn_test_ssh.clicked.connect(self.test_ssh_launch)
        self.btn_filter_updates = QtWidgets.QPushButton("Show Updates Only")
        self.btn_filter_updates.setCheckable(True)
        self.btn_filter_updates.clicked.connect(self.toggle_update_filter)

        top.addWidget(self.ed_filter, 1)
        top.addWidget(self.btn_refresh)
        top.addSpacing(16)
        top.addWidget(self.btn_upgrade_sel)
        top.addWidget(self.btn_upgrade_all)
        top.addWidget(self.btn_debug)
        top.addWidget(self.btn_test_ssh)
        top.addWidget(self.btn_filter_updates)

        # Table
        self.table = QtWidgets.QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(["Name","Model","Type","MAC","State","Uplink","IP","Adopted","Update","Locate"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        
        # Connect double-click event for SSH
        self.table.itemDoubleClicked.connect(self._on_device_double_clicked)

        # Actions under table
        act = QtWidgets.QHBoxLayout()
        self.btn_loc_on = QtWidgets.QPushButton("Locate ON")
        self.btn_loc_off = QtWidgets.QPushButton("Locate OFF")
        self.btn_alias = QtWidgets.QPushButton("Set Alias…")
        self.btn_adopt = QtWidgets.QPushButton("Adopt (Selected)")
        self.btn_setinform = QtWidgets.QPushButton("SSH set‑inform (Selected)")

        self.btn_loc_on.clicked.connect(lambda: self._locate(True))
        self.btn_loc_off.clicked.connect(lambda: self._locate(False))
        self.btn_alias.clicked.connect(self._alias)
        self.btn_adopt.clicked.connect(self._adopt)
        self.btn_setinform.clicked.connect(self._ssh_inform)

        act.addWidget(self.btn_loc_on)
        act.addWidget(self.btn_loc_off)
        act.addSpacing(16)
        act.addWidget(self.btn_alias)
        act.addSpacing(16)
        act.addWidget(self.btn_adopt)
        act.addWidget(self.btn_setinform)
        act.addStretch(1)

        lay = QtWidgets.QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.table)
        lay.addLayout(act)

        # Timer for auto refresh
        self.timer = QtCore.QTimer(self)
        self.timer.setInterval(10000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()

    def set_site(self, site_key: str):
        self.site_key = site_key or "default"
        self.refresh()

    def _rows(self):
        for r in range(self.table.rowCount()):
            yield r

    def _selected_macs(self):
        sel = set([idx.row() for idx in self.table.selectedIndexes()])
        macs = []
        for r in sel:
            item = self.table.item(r, 3)  # MAC is still in column 3
            if item:
                macs.append(item.text())
        return macs

    def refresh(self):
        self.table.setRowCount(0)
        try:
            devices = self.ctrl.get_devices(self.site_key)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Devices", f"Failed to load devices:\n{e}")
            return

        filt = (self.ed_filter.text() or "").strip().lower()
        for d in devices:
            name = d.get("name") or d.get("hostname") or ""
            model = d.get("model") or ""
            dtype = d.get("type") or d.get("device_type") or ""
            mac = d.get("mac") or ""
            online = bool(d.get("state") == 1 or d.get("connected"))
            state = "online" if online else "offline"
            upl = d.get("uplink") or {}
            link = upl.get("speed") or upl.get("link_speed") or upl.get("uplink_speed") or ""
            maxcap = _max_cap_from_tables(d)
            ip = d.get("ip") or ""
            adopted = "yes" if d.get("adopted") else "no"
            update_available = _check_update_available(d)
            locating = "ON" if d.get("locating") else "OFF"

            text = " ".join([name, model, dtype, mac, state, str(link), str(maxcap or ""), update_available, locating]).lower()
            if filt and filt not in text:
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)
            
            # Format uplink speed with visual indicator if below threshold
            uplink_display = _fmt_speed(link) if link else ""
            is_low_speed = False
            try:
                if link and maxcap:
                    link_speed = float(link)
                    max_speed = float(maxcap)
                    device_type = (d.get("type") or d.get("device_type") or "").lower()
                    model = d.get("model", "unknown")
                    name = d.get("name", "unknown")
                    
                    # Different thresholds for different device types
                    if "switch" in device_type or "usw" in device_type:
                        # For switches, only warn if less than 1 Gbps
                        threshold = 1000  # 1 Gbps threshold for switches
                        self.log(f"Switch {name} ({model}): Link={link_speed}Mbps, Switch threshold=1000Mbps")
                    else:
                        # For APs and other devices, use 80% of max capability
                        threshold = max_speed * 0.8
                        self.log(f"Device {name} ({model}): Link={link_speed}Mbps, Max={max_speed}Mbps, Threshold={threshold}Mbps")
                    
                    if link_speed < threshold:
                        is_low_speed = True
                        warning_symbol = "!"  # Simple exclamation mark
                        uplink_display = f"{warning_symbol} {uplink_display}"
                        self.log(f"LOW SPEED WARNING: {name} ({model}) - {link_speed}Mbps < {threshold}Mbps")
                        self.log(f"Uplink display will be: '{uplink_display}'")
                elif link and not maxcap:
                    # Debug when we have link speed but no max capability
                    model = d.get("model", "unknown")
                    name = d.get("name", "unknown")
                    self.log(f"Device {name} ({model}): Link={link}Mbps but no max capability detected")
            except Exception as e:
                self.log(f"Error checking speed threshold: {e}")
                pass
            
            vals = [name, model, dtype, mac, state, uplink_display, ip, adopted, update_available, locating]
            for c, v in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(str(v))
                if c == 4 and not online:  # State column
                    item.setForeground(QtCore.Qt.red)
                elif c == 5:  # Uplink column
                    if is_low_speed:
                        item.setForeground(QtCore.Qt.darkRed)  # Dark red text for better contrast
                        item.setBackground(QtGui.QColor(255, 248, 220))  # Light yellow background
                        item.setFont(QtGui.QFont("Arial", 9, QtGui.QFont.Bold))  # Bold font for emphasis
                        self.log(f"Applied low speed styling to {name}: text='{v}', is_low_speed={is_low_speed}")
                    elif not link:
                        item.setForeground(QtCore.Qt.gray)
                elif c == 8:  # Update column
                    if update_available == "Yes":
                        item.setForeground(QtCore.Qt.blue)
                        item.setFont(QtGui.QFont("Arial", 9, QtGui.QFont.Bold))
                        item.setBackground(QtGui.QColor(240, 248, 255))  # Light blue background
                    elif update_available == "Unknown":
                        item.setForeground(QtCore.Qt.gray)
                    else:
                        item.setForeground(QtCore.Qt.darkGreen)
                elif c == 9:  # Locate column (now column 9)
                    if locating == "ON":
                        item.setForeground(QtCore.Qt.green)
                        item.setFont(QtGui.QFont("Arial", 9, QtGui.QFont.Bold))
                    else:
                        item.setForeground(QtCore.Qt.gray)
                self.table.setItem(row, c, item)

    def _locate(self, on: bool):
        macs = self._selected_macs()
        if not macs:
            QtWidgets.QMessageBox.information(self, "Locate", "Select at least one device row.")
            return
        ok = 0
        for m in macs:
            if self.ctrl.set_locate(self.site_key, m, on):
                ok += 1
        QtWidgets.QMessageBox.information(self, "Locate", f"{'Enabled' if on else 'Disabled'} locate on {ok}/{len(macs)} devices.")
        self.refresh()  # Refresh to show updated locate status

    def debug_speed_info(self):
        """Debug method to show speed information for all devices"""
        try:
            devices = self.ctrl.get_devices(self.site_key)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Debug", f"Failed to load devices:\n{e}")
            return
        
        debug_info = []
        for d in devices:
            name = d.get("name") or d.get("hostname") or "Unknown"
            model = d.get("model") or "Unknown"
            device_type = d.get("type") or d.get("device_type") or "Unknown"
            
            # Get uplink info
            upl = d.get("uplink") or {}
            link = upl.get("speed") or upl.get("link_speed") or upl.get("uplink_speed") or ""
            
            # Get max capability
            maxcap = _max_cap_from_tables(d)
            
            # Get port/ethernet table info
            ethernet_table = d.get("ethernet_table", [])
            port_table = d.get("port_table", [])
            
            debug_info.append(f"Device: {name}")
            debug_info.append(f"  Model: {model}")
            debug_info.append(f"  Type: {device_type}")
            debug_info.append(f"  Link Speed: {link} Mbps")
            debug_info.append(f"  Max Capability: {maxcap} Mbps")
            debug_info.append(f"  Ethernet Table: {len(ethernet_table)} ports")
            debug_info.append(f"  Port Table: {len(port_table)} ports")
            
            # Show port details
            for i, port in enumerate(ethernet_table):
                speed_caps = port.get("speed_caps", [])
                port_idx = port.get("port_idx", i)
                debug_info.append(f"    Port {port_idx}: speed_caps = {speed_caps}")
            
            for i, port in enumerate(port_table):
                speed_caps = port.get("speed_caps", [])
                port_idx = port.get("port_idx", i)
                debug_info.append(f"    Port {port_idx}: speed_caps = {speed_caps}")
            
            debug_info.append("")  # Empty line between devices
        
        # Show debug info in a dialog
        dialog = QtWidgets.QDialog(self)
        dialog.setWindowTitle("Debug Speed Information")
        dialog.setModal(True)
        dialog.resize(800, 600)
        
        layout = QtWidgets.QVBoxLayout(dialog)
        
        text_edit = QtWidgets.QTextEdit()
        text_edit.setPlainText("\n".join(debug_info))
        text_edit.setReadOnly(True)
        text_edit.setFont(QtGui.QFont("Courier New", 9))
        
        layout.addWidget(text_edit)
        
        button_box = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Ok)
        button_box.accepted.connect(dialog.accept)
        layout.addWidget(button_box)
        
        dialog.exec_()

    def test_ssh_launch(self):
        """Test SSH launch functionality"""
        ip, ok = QtWidgets.QInputDialog.getText(self, "Test SSH Launch", "Enter IP address to test SSH:")
        if not ok or not ip.strip():
            return
        
        self.log(f"Testing SSH launch to {ip}")
        self._launch_ssh_terminal(ip, "Test Device", False, self.site_key)

    def toggle_update_filter(self):
        """Toggle filter to show only devices with updates available"""
        if self.btn_filter_updates.isChecked():
            self.btn_filter_updates.setText("Show All")
            self.ed_filter.setText("yes")
            self.refresh()
        else:
            self.btn_filter_updates.setText("Show Updates Only")
            self.ed_filter.clear()
            self.refresh()

    def _on_device_double_clicked(self, item):
        """Handle double-click on device in devices table"""
        if not item:
            return
        
        row = item.row()
        ip_item = self.table.item(row, 6)  # IP column (index 6)
        if not ip_item:
            return
        
        ip = ip_item.text()
        if not ip:
            return
        
        # Get device info
        name_item = self.table.item(row, 0)  # Name column
        adopted_item = self.table.item(row, 7)  # Adopted column
        
        device_name = name_item.text() if name_item else "Unknown"
        is_adopted = adopted_item and "yes" in adopted_item.text().lower()
        
        self._launch_ssh_terminal(ip, device_name, is_adopted, self.site_key)

    def _launch_ssh_terminal(self, ip: str, device_name: str, is_adopted: bool, site_key: str):
        """Launch SSH terminal for device"""
        try:
            import subprocess
            import sys
            import shutil
            
            # Determine SSH credentials
            if is_adopted and site_key:
                # Try to get site-specific credentials
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
            
            self.log(f"Launching SSH to {device_name} ({ip}) with user: {username}")
            
            success = False
            error_msg = ""
            
            # Try different SSH clients based on platform
            if sys.platform.startswith("win"):
                # Windows - try multiple SSH clients
                ssh_commands = [
                    # Try Windows 10+ built-in SSH
                    ["ssh", f"{username}@{ip}"],
                    # Try PuTTY
                    ["putty", "-ssh", f"{username}@{ip}"],
                    # Try cmd with SSH
                    ["cmd", "/c", "start", "ssh", f"{username}@{ip}"],
                    # Try PowerShell
                    ["powershell", "-Command", f"ssh {username}@{ip}"]
                ]
                
                for cmd in ssh_commands:
                    try:
                        self.log(f"Trying: {' '.join(cmd)}")
                        result = subprocess.Popen(cmd, shell=True, creationflags=subprocess.CREATE_NEW_CONSOLE if "cmd" in cmd else 0)
                        success = True
                        break
                    except Exception as e:
                        error_msg = str(e)
                        continue
                        
            else:
                # Unix-like systems (macOS, Linux)
                ssh_commands = []
                
                # Check if ssh command exists
                if shutil.which("ssh"):
                    ssh_commands.append(["ssh", f"{username}@{ip}"])
                
                # Platform-specific terminal commands
                if sys.platform == "darwin":  # macOS
                    ssh_commands.extend([
                        ["osascript", "-e", f'tell app "Terminal" to do script "ssh {username}@{ip}"'],
                        ["open", "-a", "Terminal", "--args", "ssh", f"{username}@{ip}"]
                    ])
                else:  # Linux
                    ssh_commands.extend([
                        ["xterm", "-e", f"ssh {username}@{ip}"],
                        ["gnome-terminal", "--", "ssh", f"{username}@{ip}"],
                        ["konsole", "-e", "ssh", f"{username}@{ip}"]
                    ])
                
                for cmd in ssh_commands:
                    try:
                        self.log(f"Trying: {' '.join(cmd)}")
                        result = subprocess.Popen(cmd)
                        success = True
                        break
                    except Exception as e:
                        error_msg = str(e)
                        continue
            
            if success:
                self.log(f"SSH terminal launched for {device_name} ({ip})")
            else:
                # If all methods failed, show a dialog with manual instructions
                manual_cmd = f"ssh {username}@{ip}"
                self.log(f"Failed to launch SSH automatically. Manual command: {manual_cmd}")
                
                msg = QtWidgets.QMessageBox(self)
                msg.setWindowTitle("SSH Launch Failed")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setText(f"Could not automatically launch SSH terminal for {device_name} ({ip})")
                msg.setDetailedText(f"Manual SSH command:\n{manual_cmd}\n\nError: {error_msg}")
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
            
        except Exception as e:
            self.log(f"Failed to launch SSH terminal: {e}")
            QtWidgets.QMessageBox.warning(self, "SSH Launch", f"Failed to launch SSH terminal:\n{e}")

    def _alias(self):
        macs = self._selected_macs()
        if not macs:
            QtWidgets.QMessageBox.information(self, "Alias", "Select a device first.")
            return
        mac = macs[0]
        name, ok = QtWidgets.QInputDialog.getText(self, "Set Alias", f"Alias for {mac}:")
        if not ok or not name.strip():
            return
        if self.ctrl.set_alias(self.site_key, mac, name.strip()):
            self.refresh()
        else:
            QtWidgets.QMessageBox.warning(self, "Alias", "Controller did not accept alias update.")

    def _adopt(self):
        macs = self._selected_macs()
        if not macs:
            QtWidgets.QMessageBox.information(self, "Adopt", "Select an unadopted device first.")
            return
        done = 0
        for m in macs:
            if self.ctrl.adopt_device(self.site_key, m):
                done += 1
        self.refresh()
        QtWidgets.QMessageBox.information(self, "Adopt", f"Adopt requested for {done}/{len(macs)} devices.")

    def upgrade_selected(self):
        macs = self._selected_macs()
        if not macs:
            QtWidgets.QMessageBox.information(self, "Upgrade", "Select at least one device row.")
            return
        done = 0
        for m in macs:
            if self.ctrl.upgrade_device(self.site_key, m):
                done += 1
        QtWidgets.QMessageBox.information(self, "Upgrade", f"Upgrade requested for {done}/{len(macs)} devices.")

    def upgrade_all(self):
        # naive: attempt upgrade on all devices that report upgradable==True
        try:
            devices = self.ctrl.get_devices(self.site_key)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Upgrade", f"Failed to load devices: {e}")
            return
        done = 0
        targets = [d for d in devices if d.get("upgradable")]
        for d in targets:
            if self.ctrl.upgrade_device(self.site_key, d.get("mac")):
                done += 1
        QtWidgets.QMessageBox.information(self, "Upgrade", f"Upgrade requested for {done}/{len(targets)} devices.")

    def _ssh_inform(self):
        macs = self._selected_macs()
        if not macs:
            QtWidgets.QMessageBox.information(self, "set‑inform", "Select a device row (with an IP).")
            return
        done = 0
        for m in macs:
            # find IP from table
            items = self.table.findItems(m, QtCore.Qt.MatchExactly)
            ip = ""
            for it in items:
                if it.column() == 3:
                    row = it.row()
                    ip = self.table.item(row, 7).text() if self.table.item(row, 7) else ""
            if not ip:
                continue
            if self.ctrl.ssh_set_inform(ip):
                done += 1
        QtWidgets.QMessageBox.information(self, "set‑inform", f"set‑inform attempted on {done}/{len(macs)} with an IP.")
