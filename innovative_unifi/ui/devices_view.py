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

def _max_cap_from_tables(dev: dict):
    # Try ethernet/port tables to infer maximum capability (prefer uplink port)
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
    return best or None

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

        top.addWidget(self.ed_filter, 1)
        top.addWidget(self.btn_refresh)
        top.addSpacing(16)
        top.addWidget(self.btn_upgrade_sel)
        top.addWidget(self.btn_upgrade_all)

        # Table
        self.table = QtWidgets.QTableWidget(0, 10)
        self.table.setHorizontalHeaderLabels(["Name","Model","Type","MAC","State","Uplink","Max Cap","IP","Adopted","Locate"])
        self.table.horizontalHeader().setStretchLastSection(True)
        self.table.setSelectionBehavior(QtWidgets.QTableWidget.SelectRows)
        self.table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)

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
            item = self.table.item(r, 3)
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
            locating = "ON" if d.get("locating") else "OFF"

            text = " ".join([name, model, dtype, mac, state, str(link), str(maxcap or ""), locating]).lower()
            if filt and filt not in text:
                continue

            row = self.table.rowCount()
            self.table.insertRow(row)
            vals = [name, model, dtype, mac, state, _fmt_speed(link) if link else "", _fmt_speed(maxcap) if maxcap else "unknown", ip, adopted, locating]
            for c, v in enumerate(vals):
                item = QtWidgets.QTableWidgetItem(str(v))
                if c == 4 and not online:
                    item.setForeground(QtCore.Qt.red)
                elif c == 9:  # Locate column
                    if locating == "ON":
                        item.setForeground(QtCore.Qt.green)
                        item.setFont(QtGui.QFont("Arial", 9, QtGui.QFont.Bold))
                    else:
                        item.setForeground(QtCore.Qt.gray)
                self.table.setItem(row, c, item)

            # Alert if link below max
            try:
                if link and maxcap and float(link) < float(maxcap)*0.8:  # highlight low link
                    self.table.item(row, 5).setForeground(QtCore.Qt.darkYellow)
                    self.table.item(row, 6).setForeground(QtCore.Qt.darkYellow)
            except Exception:
                pass

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
