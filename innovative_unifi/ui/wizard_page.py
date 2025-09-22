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
        self.btn_loc_on = QtWidgets.QPushButton("Locate ON")
        self.btn_loc_off = QtWidgets.QPushButton("Locate OFF")
        self.btn_refresh_devices = QtWidgets.QPushButton("Refresh From Controller")

        top2 = QtWidgets.QHBoxLayout()
        top2.addWidget(self.lbl_cidr)
        top2.addStretch(1)
        top2.addWidget(self.btn_discover)
        top2.addSpacing(20)
        top2.addWidget(self.btn_setinform)
        top2.addSpacing(10)
        top2.addWidget(self.btn_loc_on)
        top2.addWidget(self.btn_loc_off)
        top2.addSpacing(10)
        top2.addWidget(self.btn_refresh_devices)

        self.table = QtWidgets.QTableWidget(0, 5)
        self.table.setHorizontalHeaderLabels(["IP", "Ping", "SSH 22", "Adopted", "MAC"])
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)

        # Progress log
        self.lbl_progress = QtWidgets.QLabel("Ready to begin network setup...")
        self.lbl_progress.setStyleSheet("QLabel { background-color: #000000; color: #ffffff; padding: 8px; border: 1px solid #333333; border-radius: 4px; font-family: 'Courier New', monospace; }")
        self.lbl_progress.setWordWrap(True)
        self.lbl_progress.setMinimumHeight(60)

        lay_disc = QtWidgets.QVBoxLayout(self.grp_disc)
        lay_disc.addLayout(top2)
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
        self.btn_loc_on.clicked.connect(lambda: self._locate(True))
        self.btn_loc_off.clicked.connect(lambda: self._locate(False))
        self.btn_refresh_devices.clicked.connect(self._refresh_from_controller)

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
        
        self._update_progress("Site configuration complete. Starting device discovery...", "success")
        self._auto_discover_and_adopt()

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
            # add row
            row = self.table.rowCount()
            self.table.insertRow(row)
            self.table.setItem(row, 0, QtWidgets.QTableWidgetItem(ip))
            self.table.setItem(row, 1, QtWidgets.QTableWidgetItem("yes"))
            self.table.setItem(row, 2, QtWidgets.QTableWidgetItem("open/unknown"))
            self.table.setItem(row, 3, QtWidgets.QTableWidgetItem(""))  # adopted (filled via controller refresh)
            self.table.setItem(row, 4, QtWidgets.QTableWidgetItem(mac))
        # Map to controller
        self._refresh_from_controller()

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
            row = {"ip": ip, "ping": alive, "ssh": ssh, "adopted": "", "mac": ""}
            self.discovered.append(row)
            r = self.table.rowCount()
            self.table.insertRow(r)
            self.table.setItem(r, 0, QtWidgets.QTableWidgetItem(ip))
            self.table.setItem(r, 1, QtWidgets.QTableWidgetItem("yes" if alive else "no"))
            self.table.setItem(r, 2, QtWidgets.QTableWidgetItem("open" if ssh else "closed"))
            self.table.setItem(r, 3, QtWidgets.QTableWidgetItem(""))
            self.table.setItem(r, 4, QtWidgets.QTableWidgetItem(""))
        progress.setValue(len(hosts))
        # Try to map any already-known devices by IP
        self._refresh_from_controller()

    def _selected_ips(self):
        selrows = set(idx.row() for idx in self.table.selectedIndexes())
        ips = []
        for r in selrows:
            it = self.table.item(r, 0)
            if it:
                ips.append(it.text())
        return ips

    def _refresh_from_controller(self):
        try:
            devices = self.ctrl.get_devices(self.site_key)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Controller", f"Failed to fetch devices:\n{e}")
            return
        by_ip = {}
        for d in devices:
            ip = d.get("ip") or ""
            if ip:
                by_ip[ip] = d
        # update rows
        for r in range(self.table.rowCount()):
            ip = self.table.item(r, 0).text()
            d = by_ip.get(ip)
            adopted = ""
            mac = ""
            if d:
                mac = d.get("mac") or ""
                adopted = "yes" if d.get("adopted") else "no"
            self.table.item(r, 3).setText(adopted)
            self.table.item(r, 4).setText(mac)

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
            _ = self.ctrl.ssh_set_inform(ip)

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
