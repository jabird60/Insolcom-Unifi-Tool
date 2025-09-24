from PyQt5 import QtWidgets, QtCore, QtGui
import ipaddress, sys, subprocess, time, socket
import psutil
from ..core.controller import ControllerClient
from ..core.discovery import ubnt_discover

def _is_windows():
    return sys.platform.startswith("win")

def ping_host(ip: str, timeout_ms: int = 800) -> bool:
    try:
        if _is_windows():
            cmd = ["ping", "-n", "1", "-w", str(timeout_ms), ip]
        else:
            tsec = max(1, int(round(timeout_ms/1000)))
            cmd = ["ping", "-c", "1", "-W", str(tsec), ip]
        proc = subprocess.run(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return proc.returncode == 0
    except Exception:
        return False

def tcp_check(ip: str, port: int = 22, timeout_s: float = 2.0) -> bool:
    try:
        with socket.create_connection((ip, port), timeout=timeout_s):
            return True
    except Exception:
        return False

def detect_local_cidr():
    """Return (iface_name, cidr) for the first active non-loopback IPv4 interface, else (None, None)."""
    try:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        candidates = []
        for ifname, ifaddrs in addrs.items():
            st = stats.get(ifname)
            if not st or not st.isup:
                continue
            for a in ifaddrs:
                if a.family == socket.AF_INET:
                    ip = a.address or ""
                    mask = a.netmask or ""
                    if not ip or ip.startswith("127.") or ip.startswith("169.254."):
                        continue
                    try:
                        ipaddress.IPv4Address(ip)
                    except Exception:
                        continue
                    if not mask:
                        continue
                    try:
                        net = ipaddress.IPv4Network(f"{ip}/{mask}", strict=False)
                    except Exception:
                        continue
                    candidates.append((ifname, str(net)))
        if not candidates:
            return None, None
        def score(entry):
            ifn, cidr = entry
            pref = int(cidr.split("/")[1])
            s = 0
            s -= abs(24 - pref)  # prefer around /24
            lname = ifn.lower()
            if any(k in lname for k in ("en0", "wlan", "wifi", "wi-fi", "eth0", "ethernet")):
                s += 1
            return s
        candidates.sort(key=score, reverse=True)
        return candidates[0]
    except Exception:
        return None, None

class WizardPage(QtWidgets.QWidget):
    '''
    Two-step wizard:
      1) Choose Existing Site or Create New
      2) Discover APs on the LOCAL connected network, Set-Inform + Adopt + Name
    '''
    def __init__(self, ctrl: ControllerClient, devices_view, wifi_view, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.devices_view = devices_view
        self.wifi_view = wifi_view
        self.site_key = "default"
        self.discovered = []  # {'ip','ping','ssh','mac','adopted'}
        self.iface_name, self.current_cidr = detect_local_cidr()
        self.auto_discovery_done = False  # Track if auto-discovery has been performed

        # --- Page 1: Site selection ---
        self.grp_mode = QtWidgets.QGroupBox("Step 1 — Site")
        self.rb_existing = QtWidgets.QRadioButton("Use existing site")
        self.rb_new = QtWidgets.QRadioButton("Create new site")
        self.rb_existing.setChecked(True)
        self.cmb_sites = QtWidgets.QComboBox()
        self.cmb_sites.setEditable(True)
        self.cmb_sites.setMinimumWidth(320)
        self.cmb_sites.completer().setFilterMode(QtCore.Qt.MatchContains)
        self.cmb_sites.completer().setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.ed_new_site = QtWidgets.QLineEdit()
        self.ed_new_site.setPlaceholderText("New site name")
        self.btn_load_sites = QtWidgets.QPushButton("Load Sites")
        self.btn_proceed = QtWidgets.QPushButton("Proceed ▶")

        lay_site = QtWidgets.QGridLayout(self.grp_mode)
        lay_site.addWidget(self.rb_existing, 0, 0, 1, 2)
        lay_site.addWidget(self.cmb_sites, 1, 0, 1, 2)
        lay_site.addWidget(self.btn_load_sites, 1, 2, 1, 1)
        lay_site.addWidget(self.rb_new, 2, 0, 1, 2)
        lay_site.addWidget(self.ed_new_site, 3, 0, 1, 2)
        lay_site.addWidget(self.btn_proceed, 4, 0, 1, 3)

        # --- Page 2: Discovery & Adoption ---
        self.grp_disc = QtWidgets.QGroupBox("Step 2 — Discover & Adopt APs")
        self.lbl_cidr = QtWidgets.QLabel("Local network: (detecting…)")
        self.btn_discover = QtWidgets.QPushButton("Discover on Local Network")
        self.btn_setinform = QtWidgets.QPushButton("Set‑Inform + Adopt Selected")
        self.btn_test_inform = QtWidgets.QPushButton("Test Set-Inform")
        self.btn_loc_on = QtWidgets.QPushButton("Locate ON")
        self.btn_loc_off = QtWidgets.QPushButton("Locate OFF")
        self.btn_refresh_devices = QtWidgets.QPushButton("Refresh From Controller")
        
        # Active site indicator
        self.lbl_active_site = QtWidgets.QLabel(f"Active Site: {self.site_key}")
        self.lbl_active_site.setStyleSheet("font-weight: bold; color: #0066cc;")

        top2 = QtWidgets.QHBoxLayout()
        top2.addWidget(self.lbl_cidr)
        top2.addStretch(1)
        top2.addWidget(self.btn_discover)
        top2.addSpacing(20)
        top2.addWidget(self.btn_setinform)
        top2.addWidget(self.btn_test_inform)
        top2.addSpacing(10)
        top2.addWidget(self.btn_loc_on)
        top2.addWidget(self.btn_loc_off)
        top2.addSpacing(10)
        top2.addWidget(self.btn_refresh_devices)

        # Add active site indicator
        site_layout = QtWidgets.QHBoxLayout()
        site_layout.addWidget(self.lbl_active_site)
        site_layout.addStretch(1)

        self.table = QtWidgets.QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels(["IP", "Name", "Ping", "SSH 22", "Adopted", "Site", "MAC"])
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        
        # Connect double-click event for SSH
        self.table.itemDoubleClicked.connect(self._on_device_double_clicked)
        
        # Set column widths for better display
        self.table.setColumnWidth(0, 120)  # IP
        self.table.setColumnWidth(1, 150)  # Name
        self.table.setColumnWidth(2, 60)   # Ping
        self.table.setColumnWidth(3, 80)   # SSH
        self.table.setColumnWidth(4, 80)   # Adopted
        self.table.setColumnWidth(5, 150)  # Site
        self.table.setColumnWidth(6, 140)  # MAC

        # Progress log
        self.lbl_progress = QtWidgets.QLabel("Ready to begin network setup...")
        self.lbl_progress.setStyleSheet("QLabel { background-color: #000000; color: #ffffff; padding: 8px; border: 1px solid #333333; border-radius: 4px; font-family: 'Courier New', monospace; }")
        self.lbl_progress.setWordWrap(True)
        self.lbl_progress.setMinimumHeight(60)

        lay_disc = QtWidgets.QVBoxLayout(self.grp_disc)
        lay_disc.addLayout(top2)
        lay_disc.addLayout(site_layout)
        lay_disc.addWidget(self.lbl_progress)
        lay_disc.addWidget(self.table)

        # Overall layout
        lay = QtWidgets.QVBoxLayout(self)
        self.btn_login = QtWidgets.QPushButton("Login to Controller")
        lay.addWidget(self.btn_login, 0, QtCore.Qt.AlignRight)
        lay.addWidget(self.grp_mode)
        lay.addWidget(self.grp_disc)
        lay.addStretch(1)

        # Wiring
        self.btn_login.clicked.connect(self._login)
        self.btn_load_sites.clicked.connect(self._load_sites)
        self.btn_proceed.clicked.connect(self._proceed_site)
        self.btn_discover.clicked.connect(self._discover_local)
        self.btn_setinform.clicked.connect(self._setinform_and_adopt)
        self.btn_test_inform.clicked.connect(self.test_set_inform)
        self.btn_loc_on.clicked.connect(lambda: self._locate(True))
        self.btn_loc_off.clicked.connect(lambda: self._locate(False))
        self.btn_refresh_devices.clicked.connect(self._refresh_from_controller)
        
        # Connect site selection change
        self.cmb_sites.currentIndexChanged.connect(self._on_site_changed)

        self._load_sites()
        self._update_cidr_label()

    def on_tab_visible(self):
        """Called when the wizard tab becomes visible. Triggers automatic discovery if not done yet."""
        if not self.auto_discovery_done:
            self.auto_discovery_done = True
            # Run discovery in the background to avoid blocking the UI
            QtCore.QTimer.singleShot(500, self._auto_discover_on_show)

    def _auto_discover_on_show(self):
        """Perform automatic discovery when the tab is first shown."""
        try:
            # Update the CIDR label first
            self._update_cidr_label()
            # Run discovery
            self._discover_local()
            # Update progress log instead of showing popup
            if self.table.rowCount() > 0:
                self._update_progress(f"Auto-discovery found {self.table.rowCount()} device(s) on the local network.", "success")
            else:
                self._update_progress("No devices found on the local network. You can try manual discovery.", "warning")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Auto Discovery", f"Discovery failed: {e}")

    def _update_progress(self, message: str, status: str = "info"):
        """Update the progress log with a new message."""
        timestamp = QtCore.QTime.currentTime().toString("hh:mm:ss")
        
        # Color coding based on status
        if status == "success":
            color = "#2e7d32"  # Green
            icon = "✓"
        elif status == "error":
            color = "#d32f2f"  # Red
            icon = "✗"
        elif status == "warning":
            color = "#f57c00"  # Orange
            icon = "⚠"
        else:  # info
            color = "#1976d2"  # Blue
            icon = "ℹ"
        
        # Update the label with formatted message
        formatted_message = f"[{timestamp}] {icon} {message}"
        self.lbl_progress.setText(formatted_message)
        
        # Force UI update
        QtWidgets.QApplication.processEvents()

    # --- Step 1: Site selection ---
    def _login(self):
        ok = self.ctrl.login()
        QtWidgets.QMessageBox.information(self, "Login", "Success." if ok else "Failed.")

    def _load_sites(self):
        # attempt login implicitly
        self.ctrl.login()
        self.cmb_sites.clear()
        sites = self.ctrl.get_sites() or []
        for s in sites:
            name = s.get("desc") or s.get("name") or s.get("site_name") or "default"
            key = s.get("name") or s.get("site_name") or "default"
            self.cmb_sites.addItem(f"{name} ({key})", key)
        if self.cmb_sites.count() == 0:
            self.cmb_sites.addItem("default (default)", "default")
        self.cmb_sites.setCurrentIndex(0)

    def _proceed_site(self):
        self._update_progress("Starting network setup process...", "info")
        
        # If creating a new site, create and resolve site key accurately
        if self.rb_new.isChecked():
            newname = (self.ed_new_site.text() or "").strip()
            if not newname:
                self._update_progress("Error: Please enter a new site name.", "error")
                return
            
            self._update_progress(f"Creating new site: {newname}...", "info")
            try:
                new_key = self.ctrl.create_site_and_get_key(newname)
                if new_key:
                    self._update_progress(f"Successfully created site: {newname}", "success")
                else:
                    self._update_progress("Site created but could not resolve key. Please open UniFi UI once and retry.", "warning")
                    return
            except Exception as e:
                self._update_progress(f"Failed to create site: {str(e)}", "error")
                return
            
            # Reload sites and select by the returned key
            self._update_progress("Reloading site list...", "info")
            self._load_sites()
            pick = 0
            for i in range(self.cmb_sites.count()):
                if (self.cmb_sites.itemData(i) or "") == new_key:
                    pick = i
                    break
            self.cmb_sites.setCurrentIndex(pick)
            self.site_key = new_key
        else:
            key = self.cmb_sites.currentData()
            self.site_key = key or "default"
            self._update_progress(f"Using existing site: {self.site_key}", "info")

        # propagate to other views
        self._update_progress("Updating device and WiFi views...", "info")
        self.devices_view.set_site(self.site_key)
        self.wifi_view.set_site(self.site_key)
        
        # Update active site label
        if hasattr(self, 'lbl_active_site'):
            self.lbl_active_site.setText(f"Active Site: {self.site_key}")
        
        self._update_progress(f"Site configuration complete. Active site: {self.site_key}. Starting device discovery...", "success")
        self._auto_discover_and_adopt()

    def _on_site_changed(self):
        """Handle site selection change"""
        if not self.rb_existing.isChecked():
            return  # Only update when existing site is selected
        
        key = self.cmb_sites.currentData()
        if key:
            self.site_key = key
            # Update active site label
            if hasattr(self, 'lbl_active_site'):
                self.lbl_active_site.setText(f"Active Site: {self.site_key}")
            self._update_progress(f"Active site changed to: {self.site_key}", "info")

    # --- Local network helpers ---
    def _update_cidr_label(self):
        if self.current_cidr:
            iface = self.iface_name or "(unknown iface)"
            self.lbl_cidr.setText(f"Local network: {self.current_cidr}  on interface: {iface}")
            self.btn_discover.setEnabled(True)
        else:
            self.lbl_cidr.setText("Local network: not detected. Connect to a network and try discovery.")
            self.btn_discover.setEnabled(False)


    # --- Step 2: Discovery & adoption ---
    def _discover_local(self):
        # UBNT discovery first
        self._discover_ubnt()
        # If nothing is found, fall back to scanning the detected local CIDR (if any)
        if self.table.rowCount() == 0 and self.current_cidr:
            self._discover_cidr(self.current_cidr)

    def _discover_ubnt(self):
        self.table.setRowCount(0)
        self.discovered = []
        results = []
        try:
            results = ubnt_discover(timeout=2.5)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "UBNT Discovery", f"Discovery error:\n{e}")
            results = []
        for r in results:
            ip = r.get("ip","")
            mac = r.get("mac","")
            name = r.get("name", "") or r.get("hostname", "") or r.get("alias", "")
            # add row
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(ip))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem(name))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem("yes"))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem("open/unknown"))
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(""))  # adopted (filled via controller refresh)
            self.table.setItem(row, 5, QtWidgets.QTableWidgetItem(""))  # site (filled via controller refresh)
            self.table.setItem(row, 6, QtWidgets.QTableWidgetItem(mac))
        # Map to controller and show adoption status
        self._refresh_from_controller()
        self._update_progress(f"Discovery complete. Found {self.table.rowCount()} device(s). Checking adoption status...", "info")

    def _discover_cidr(self, cidr: str):
        try:
            net = ipaddress.ip_network(cidr, strict=False)
        except Exception:
            QtWidgets.QMessageBox.warning(self, "Discover", f"Invalid CIDR detected: {cidr}")
            return
        hosts = [str(ip) for ip in net.hosts()]
        self.table.setRowCount(0)
        self.discovered = []

        progress = QtWidgets.QProgressDialog("Scanning local network…", "Cancel", 0, len(hosts), self)
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)

        for i, ip in enumerate(hosts, 1):
            QtWidgets.QApplication.processEvents()
            if progress.wasCanceled():
                break
            progress.setValue(i)
            alive = ping_host(ip, 700)
            if not alive:
                continue
            ssh = tcp_check(ip, 22, 1.5)
            row = {"ip": ip, "ping": alive, "ssh": ssh, "adopted": "", "site": "", "mac": "", "name": ""}
            self.discovered.append(row)
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(ip))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem(""))  # name (filled via controller refresh)
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem("yes" if alive else "no"))
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem("open" if ssh else "closed"))
            self.table.setItem(r, 4, QtWidgets.QTableWidgetItem(""))
            self.table.setItem(r, 5, QtWidgets.QTableWidgetItem(""))
            self.table.setItem(r, 6, QtWidgets.QTableWidgetItem(""))
        progress.setValue(len(hosts))
        # Try to map any already-known devices by IP and show adoption status
        self._refresh_from_controller()
        self._update_progress(f"Network scan complete. Found {self.table.rowCount()} device(s). Checking adoption status...", "info")

    def _selected_ips(self):
        selrows = set(idx.row() for idx in self.table.selectedIndexes())
        ips = []
        for r in selrows:
            it = self.table.item(r, 0)  # IP is still in column 0
            if it:
                ips.append(it.text())
        return ips

    def _refresh_from_controller(self):
        # Get all sites to map device sites
        try:
            sites = self.ctrl.get_sites() or []
            site_map = {}
            for site in sites:
                site_key = site.get("name") or site.get("site_name") or "default"
                site_name = site.get("desc") or site.get("name") or site.get("site_name") or "default"
                site_map[site_key] = site_name
        except Exception:
            site_map = {self.site_key: "Current Site"}
        
        # Check all sites for adopted devices
        all_devices = {}
        site_device_map = {}
        
        for site_key in site_map.keys():
            try:
                devices = self.ctrl.get_devices(site_key)
                for d in devices:
                    ip = d.get("ip") or ""
                    if ip:
                        all_devices[ip] = d
                        site_device_map[ip] = site_key
            except Exception:
                continue
        
        by_ip = all_devices
        
        # Track adopted devices for site selection
        adopted_devices = []
        
        # update rows
        for r in range(self.table.rowCount()):
            ip = self.table.item(r, 0).text()
            d = by_ip.get(ip)
            adopted = ""
            site_name = ""
            mac = ""
            device_name = ""
            
            if d:
                mac = d.get("mac") or ""
                device_name = d.get("name") or d.get("alias") or d.get("hostname") or ""
                is_adopted = d.get("adopted", False)
                adopted = "✓ Yes" if is_adopted else "✗ No"
                
                if is_adopted:
                    # Get the site name for this device
                    device_site = site_device_map.get(ip, self.site_key)
                    site_name = site_map.get(device_site, device_site)
                    adopted_devices.append((ip, device_site, site_name))
                
                # Set visual styling for adoption status
                adopted_item = self.table.item(r, 4)
                if adopted_item:
                    if is_adopted:
                        adopted_item.setForeground(QtGui.QColor(0, 150, 0))  # Green
                        adopted_item.setBackground(QtGui.QColor(240, 255, 240))  # Light green
                    else:
                        adopted_item.setForeground(QtGui.QColor(150, 0, 0))  # Red
                        adopted_item.setBackground(QtGui.QColor(255, 240, 240))  # Light red
                
                # Set site styling
                site_item = self.table.item(r, 5)
                if site_item:
                    if is_adopted:
                        site_item.setForeground(QtGui.QColor(0, 100, 200))  # Blue
                        site_item.setBackground(QtGui.QColor(240, 248, 255))  # Light blue
                    else:
                        site_item.setForeground(QtGui.QColor(100, 100, 100))  # Gray
                        site_item.setBackground(QtGui.QColor(248, 248, 248))  # Light gray
                
                # Set device name styling
                name_item = self.table.item(r, 1)
                if name_item:
                    if is_adopted:
                        name_item.setForeground(QtGui.QColor(0, 100, 200))  # Blue
                        name_item.setBackground(QtGui.QColor(240, 248, 255))  # Light blue
                    else:
                        name_item.setForeground(QtGui.QColor(50, 50, 50))  # Dark gray
                        name_item.setBackground(QtGui.QColor(248, 248, 248))  # Light gray
            
            self.table.item(r, 1).setText(device_name)
            self.table.item(r, 4).setText(adopted)
            self.table.item(r, 5).setText(site_name)
            self.table.item(r, 6).setText(mac)
        
        # Auto-select site if adopted devices are found
        if adopted_devices:
            self._auto_select_site_for_adopted_devices(adopted_devices)

    def _auto_select_site_for_adopted_devices(self, adopted_devices):
        """Automatically select the site for adopted devices"""
        if not adopted_devices:
            return
        
        # Count devices by site
        site_counts = {}
        for ip, site_key, site_name in adopted_devices:
            site_counts[site_key] = site_counts.get(site_key, 0) + 1
        
        # Find the site with the most adopted devices
        most_common_site = max(site_counts.items(), key=lambda x: x[1])
        site_key, device_count = most_common_site
        
        # Update progress log
        site_name = next((name for ip, sk, name in adopted_devices if sk == site_key), site_key)
        self._update_progress(f"Found {device_count} adopted device(s) in site '{site_name}' - auto-selecting this site", "success")
        
        # Update the site selection
        self.site_key = site_key
        
        # Update the site combo box if it exists
        if hasattr(self, 'cmb_sites'):
            for i in range(self.cmb_sites.count()):
                if self.cmb_sites.itemData(i) == site_key:
                    self.cmb_sites.setCurrentIndex(i)
                    self._update_progress(f"Automatically selected site: {site_name}", "success")
                    break
        
        # Update other views
        if hasattr(self, 'devices_view'):
            self.devices_view.set_site(site_key)
        if hasattr(self, 'wifi_view'):
            self.wifi_view.set_site(site_key)

    def _on_device_double_clicked(self, item):
        """Handle double-click on device in discovery table"""
        if not item:
            return
        
        row = item.row()
        ip_item = self.table.item(row, 0)  # IP column
        if not ip_item:
            return
        
        ip = ip_item.text()
        if not ip:
            return
        
        # Get device info
        name_item = self.table.item(row, 1)  # Name column
        adopted_item = self.table.item(row, 4)  # Adopted column
        site_item = self.table.item(row, 5)  # Site column
        
        device_name = name_item.text() if name_item else "Unknown"
        is_adopted = adopted_item and "Yes" in adopted_item.text()
        
        # Use active site for single device operations
        device_site = self.site_key  # Always use the currently active site
        
        self._launch_ssh_terminal(ip, device_name, is_adopted, device_site)

    def _launch_ssh_terminal(self, ip: str, device_name: str, is_adopted: bool, site_key: str):
        """Launch SSH terminal for device"""
        try:
            import subprocess
            import sys
            import os
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
            
            self._update_progress(f"Launching SSH to {device_name} ({ip}) with user: {username}...", "info")
            
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
                        self._update_progress(f"Trying: {' '.join(cmd)}", "info")
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
                        self._update_progress(f"Trying: {' '.join(cmd)}", "info")
                        result = subprocess.Popen(cmd)
                        success = True
                        break
                    except Exception as e:
                        error_msg = str(e)
                        continue
            
            if success:
                self._update_progress(f"SSH terminal launched for {device_name} ({ip})", "success")
            else:
                # If all methods failed, show a dialog with manual instructions
                manual_cmd = f"ssh {username}@{ip}"
                self._update_progress(f"Failed to launch SSH automatically. Manual command: {manual_cmd}", "error")
                
                msg = QtWidgets.QMessageBox(self)
                msg.setWindowTitle("SSH Launch Failed")
                msg.setIcon(QtWidgets.QMessageBox.Warning)
                msg.setText(f"Could not automatically launch SSH terminal for {device_name} ({ip})")
                msg.setDetailedText(f"Manual SSH command:\n{manual_cmd}\n\nError: {error_msg}")
                msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
                msg.exec_()
            
        except Exception as e:
            self._update_progress(f"Failed to launch SSH terminal: {e}", "error")
            QtWidgets.QMessageBox.warning(self, "SSH Launch", f"Failed to launch SSH terminal:\n{e}")

    def test_set_inform(self):
        """Test set-inform functionality on a specific device"""
        ip, ok = QtWidgets.QInputDialog.getText(self, "Test Set-Inform", f"Enter IP address to test set-inform:\n(Will use active site: {self.site_key})")
        if not ok or not ip.strip():
            return
        
        self._update_progress(f"Testing set-inform on {ip} using active site: {self.site_key}...", "info")
        
        # Test the set-inform command using active site
        success = self.ctrl.ssh_set_inform(ip, site_key=self.site_key)
        
        if success:
            self._update_progress(f"Set-inform test completed for {ip} in site {self.site_key}. Check the log for details.", "success")
        else:
            self._update_progress(f"Set-inform test failed for {ip} in site {self.site_key}. Check the log for details.", "error")

    def _locate(self, enabled: bool):
        ips = self._selected_ips()
        if not ips:
            QtWidgets.QMessageBox.information(self, "Locate", "Select one or more rows first.")
            return
        # Need MACs from controller mapping by IP
        try:
            devices = self.ctrl.get_devices(self.site_key)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Locate", f"Failed to fetch devices:\n{e}")
            return
        by_ip = { (d.get("ip") or ""): d for d in devices }
        cnt = 0
        for ip in ips:
            d = by_ip.get(ip)
            if not d:
                continue
            mac = d.get("mac") or ""
            if mac and self.ctrl.set_locate(self.site_key, mac, enabled):
                cnt += 1
        QtWidgets.QMessageBox.information(self, "Locate", f"{'Enabled' if enabled else 'Disabled'} locate on {cnt} devices.")

    def _setinform_and_adopt(self):
        ips = self._selected_ips()
        if not ips:
            self._update_progress("Error: No devices selected for adoption.", "error")
            return

        self._update_progress(f"Starting adoption process for {len(ips)} device(s)...", "info")

        progress = QtWidgets.QProgressDialog("Setting inform & adopting…", "Cancel", 0, len(ips), self)
        progress.setWindowModality(QtCore.Qt.ApplicationModal)
        progress.setMinimumDuration(0)

        for i, ip in enumerate(ips, 1):
            QtWidgets.QApplication.processEvents()
            if progress.wasCanceled():
                self._update_progress("Adoption process cancelled by user.", "warning")
                break
            
            self._update_progress(f"Processing device {i}/{len(ips)}: {ip}", "info")
            progress.setValue(i)

            # 1) set-inform over SSH
            self._update_progress(f"Setting inform URL for {ip}...", "info")
            _ = self.ctrl.ssh_set_inform(ip, site_key=self.site_key)

            # 2) poll controller for device by IP
            self._update_progress(f"Waiting for {ip} to appear in controller...", "info")
            mac = ""
            found = None
            for attempt in range(12):  # up to ~60s
                try:
                    devices = self.ctrl.get_devices(self.site_key)
                except Exception:
                    devices = []
                match = None
                for d in devices:
                    if (d.get("ip") or "") == ip:
                        match = d
                        break
                if match:
                    found = match
                    mac = match.get("mac") or ""
                    self._update_progress(f"Device {ip} found in controller (MAC: {mac})", "success")
                    break
                QtWidgets.QApplication.processEvents()
                time.sleep(5)

            # 3) adopt if present and unadopted
            if found and not found.get("adopted"):
                self._update_progress(f"Adopting device {ip}...", "info")
                self.ctrl.adopt_device(self.site_key, found.get("mac"))
                self._update_progress(f"Device {ip} adoption initiated", "success")
            elif found and found.get("adopted"):
                self._update_progress(f"Device {ip} is already adopted", "info")

            # 4) prompt alias (LED locate ON while naming)
            if mac:
                self._update_progress(f"Setting up device {ip} (turning on locate LED)...", "info")
                self.ctrl.set_locate(self.site_key, mac, True)
                try:
                    model = found.get("model") or "AP"
                except Exception:
                    model = "AP"
                alias, ok2 = QtWidgets.QInputDialog.getText(self, "Name AP", f"Enter name for {ip} ({model}):", text=model)
                if ok2 and alias.strip():
                    self.ctrl.set_alias(self.site_key, mac, alias.strip())
                    self._update_progress(f"Device {ip} named: {alias.strip()}", "success")
                self.ctrl.set_locate(self.site_key, mac, False)
                self._update_progress(f"Device {ip} setup complete (locate LED off)", "success")

            # Refresh displayed mapping
            self._refresh_from_controller()

        progress.setValue(len(ips))
        self._update_progress("Device adoption process completed! Check the Devices tab for status.", "success")

    def _auto_discover_and_adopt(self):
        self._update_progress("Scanning for UniFi devices on local network...", "info")
        
        # Run UBNT discovery first; fallback to local scan if empty
        try:
            self._discover_ubnt()
            if self.table.rowCount() > 0:
                self._update_progress(f"Found {self.table.rowCount()} device(s) via UBNT discovery", "success")
            else:
                self._update_progress("No devices found via UBNT discovery, trying network scan...", "warning")
        except Exception as e:
            self._update_progress(f"UBNT discovery failed: {str(e)}", "warning")
        
        if self.table.rowCount() == 0 and self.current_cidr:
            self._update_progress(f"Scanning network range: {self.current_cidr}", "info")
            self._discover_cidr(self.current_cidr)
            if self.table.rowCount() > 0:
                self._update_progress(f"Found {self.table.rowCount()} device(s) via network scan", "success")
            else:
                self._update_progress("No devices found on local network", "warning")
        
        if self.table.rowCount() == 0:
            self._update_progress("No devices found. Please check your network connection and try manual discovery.", "error")
            return
        
        # Select all rows and run the same pipeline
        self._update_progress("Selecting all discovered devices...", "info")
        self.table.selectAll()
        
        self._update_progress("Starting device adoption process...", "info")
        self._setinform_and_adopt()
