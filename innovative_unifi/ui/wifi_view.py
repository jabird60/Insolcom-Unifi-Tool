
from PyQt5 import QtWidgets, QtCore
from ..core.controller import ControllerClient

class WiFiView(QtWidgets.QWidget):
    def __init__(self, ctrl: ControllerClient, store, parent=None):
        super().__init__(parent)
        self.ctrl = ctrl
        self.store = store
        self.site_key = "default"

        self.btn_refresh = QtWidgets.QPushButton("Refresh WLANs")
        self.btn_create = QtWidgets.QPushButton("Create New SSID")
        self.btn_enable = QtWidgets.QPushButton("Enable Selected")
        self.btn_disable = QtWidgets.QPushButton("Disable Selected")
        self.btn_verbose = QtWidgets.QPushButton("Toggle Selected (Verbose)")

        self.tbl = QtWidgets.QTableWidget(0, 5)
        self.tbl.setHorizontalHeaderLabels(["Name", "Enabled", "Security", "Bands", "AP Group Mode"])
        self.tbl.horizontalHeader().setStretchLastSection(True)
        self.tbl.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        self.tbl.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)

        top = QtWidgets.QHBoxLayout()
        top.addWidget(self.btn_refresh)
        top.addStretch(1)
        top.addWidget(self.btn_enable)
        top.addWidget(self.btn_disable)
        top.addWidget(self.btn_verbose)
        top.addSpacing(10)
        top.addWidget(self.btn_create)

        lay = QtWidgets.QVBoxLayout(self)
        lay.addLayout(top)
        lay.addWidget(self.tbl)

        self.btn_refresh.clicked.connect(self.refresh)
        self.btn_create.clicked.connect(self.on_create)
        self.btn_enable.clicked.connect(lambda: self._toggle_selected(True))
        self.btn_disable.clicked.connect(lambda: self._toggle_selected(False))
        self.btn_verbose.clicked.connect(self._toggle_selected_verbose)

    def set_site(self, key: str):
        self.site_key = key or "default"
        self.refresh()

    def refresh(self):
        self.ctrl.login()
        wlans = self.ctrl.get_wlans(self.site_key) or []
        self.tbl.setRowCount(0)
        for w in wlans:
            r = self.tbl.rowCount()
            self.tbl.insertRow(r)
            name = w.get("name","")
            enabled = w.get("enabled", True)
            sec = w.get("security","")
            bands = w.get("wlan_band","") or ("5g" if w.get("na_only") else "2g" if w.get("ng_only") else "both")
            agm = w.get("ap_group_mode","")
            wid = w.get("_id","")

            name_item = QtWidgets.QTableWidgetItem(name)
            name_item.setData(QtCore.Qt.UserRole, wid)  # stash WLAN id for toggles
            self.tbl.setItem(r, 0, name_item)
            self.tbl.setItem(r, 1, QtWidgets.QTableWidgetItem("Yes" if enabled else "No"))
            self.tbl.setItem(r, 2, QtWidgets.QTableWidgetItem(sec))
            self.tbl.setItem(r, 3, QtWidgets.QTableWidgetItem(bands))
            self.tbl.setItem(r, 4, QtWidgets.QTableWidgetItem(agm))

    def _selected_wlan_ids(self):
        ids = []
        rows = set(i.row() for i in self.tbl.selectedIndexes())
        for r in rows:
            it = self.tbl.item(r, 0)
            if it:
                wid = it.data(QtCore.Qt.UserRole)
                if wid:
                    ids.append(wid)
        return ids

    def _toggle_selected(self, want_enabled: bool):
        ids = self._selected_wlan_ids()
        if not ids:
            QtWidgets.QMessageBox.information(self, "Wi‑Fi", "Select one or more SSIDs first.")
            return
        self.ctrl.login()
        ok_count = 0
        for wid in ids:
            try:
                if self.ctrl.set_wlan_enabled(self.site_key, wid, want_enabled):
                    ok_count += 1
            except Exception:
                pass
        self.refresh()
        QtWidgets.QMessageBox.information(self, "Wi‑Fi",
            f"{'Enabled' if want_enabled else 'Disabled'} {ok_count} SSID(s).")

    def _toggle_selected_verbose(self):
        ids = self._selected_wlan_ids()
        if not ids:
            QtWidgets.QMessageBox.information(self, "Wi‑Fi", "Select one or more SSIDs first.")
            return
        
        self.ctrl.login()
        success_count = 0
        all_logs = []
        
        for wid in ids:
            try:
                # Get current state of the WLAN to determine what to toggle to
                wlans = self.ctrl.get_wlans(self.site_key) or []
                current_enabled = None
                for w in wlans:
                    if w.get("_id") == wid:
                        current_enabled = w.get("enabled", True)
                        break
                
                if current_enabled is None:
                    all_logs.append(f"WLAN {wid}: Could not determine current state")
                    continue
                
                # Toggle the state
                new_state = not current_enabled
                success, logs = self.ctrl.set_wlan_enabled_verbose(self.site_key, wid, new_state)
                
                if success:
                    success_count += 1
                    all_logs.append(f"WLAN {wid}: Successfully {'enabled' if new_state else 'disabled'}")
                else:
                    all_logs.append(f"WLAN {wid}: Failed to {'enable' if new_state else 'disable'}")
                
                all_logs.append(f"  Details: {logs}")
                
            except Exception as e:
                all_logs.append(f"WLAN {wid}: Exception - {e}")
        
        self.refresh()
        
        # Show results in a detailed dialog
        msg = QtWidgets.QMessageBox(self)
        msg.setWindowTitle("Wi‑Fi Verbose Toggle")
        msg.setText(f"Verbose toggle completed: {success_count}/{len(ids)} SSID(s) processed")
        msg.setDetailedText("\n".join(all_logs))
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok)
        msg.exec_()

    def on_create(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "New SSID", "SSID name:")
        if not ok or not name.strip():
            return
        psk, ok2 = QtWidgets.QInputDialog.getText(self, "New SSID", "WPA2 password (8–255 chars or 64-hex):")
        if not ok2 or not psk:
            return
        try:
            self.ctrl.login()
            wlan = self.ctrl.create_wlan(self.site_key, name.strip(), psk.strip())
            QtWidgets.QMessageBox.information(self, "Wi‑Fi", f"Created SSID: {wlan.get('name', name)}")
            self.refresh()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Wi‑Fi", f"Controller rejected WLAN create:\n{e}")