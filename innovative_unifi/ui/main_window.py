from PyQt5 import QtWidgets, QtCore
from ..core.settings_store import SettingsStore
from ..core.controller import ControllerClient
from ..core.logger_bus import LogBus
from .devices_view import DevicesView
from .wifi_view import WiFiView
from .wizard_page import WizardPage
from .settings_dialog import SettingsDialog

class MainWindow(QtWidgets.QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Innovative Solutions — UniFi AP Field Tool (GUI)")
        self.store = SettingsStore()
        self.log_bus = LogBus()
        self.ctrl = ControllerClient(self.store, self.log_bus)

        # Menus
        bar = self.menuBar()
        m_file = bar.addMenu("File")
        act_settings = m_file.addAction("Settings…")
        act_settings.triggered.connect(self.open_settings)
        m_file.addSeparator()
        act_quit = m_file.addAction("Quit")
        act_quit.triggered.connect(self.close)
        
        # View menu
        m_view = bar.addMenu("View")
        act_toggle_log = m_view.addAction("Toggle Log")
        act_toggle_log.setShortcut("Ctrl+L")
        act_toggle_log.triggered.connect(self.toggle_log)

        # Sites toolbar with searchable combo
        tb = QtWidgets.QToolBar("Sites")
        self.addToolBar(tb)
        self.btn_login = QtWidgets.QPushButton("Login")
        self.btn_login.clicked.connect(self.login)
        tb.addWidget(self.btn_login)

        self.cmb_sites = QtWidgets.QComboBox()
        self.cmb_sites.setEditable(True)
        self.cmb_sites.setMinimumWidth(280)
        self.cmb_sites.completer().setFilterMode(QtCore.Qt.MatchContains)
        self.cmb_sites.completer().setCaseSensitivity(QtCore.Qt.CaseInsensitive)
        self.cmb_sites.currentIndexChanged.connect(self._site_changed)
        tb.addWidget(QtWidgets.QLabel("  Site: "))
        tb.addWidget(self.cmb_sites)
        self.btn_sites_reload = QtWidgets.QPushButton("Reload Sites")
        self.btn_sites_reload.clicked.connect(self.load_sites)
        tb.addWidget(self.btn_sites_reload)
        
        # Log toggle button
        self.btn_toggle_log = QtWidgets.QPushButton("Show Log")
        self.btn_toggle_log.setCheckable(True)
        self.btn_toggle_log.setChecked(False)
        self.btn_toggle_log.setToolTip("Toggle log visibility (Ctrl+L)")
        self.btn_toggle_log.clicked.connect(self.toggle_log)
        tb.addWidget(self.btn_toggle_log)
        
        # Add keyboard shortcut for log toggle
        self.toggle_log_shortcut = QtWidgets.QShortcut(QtCore.Qt.CTRL + QtCore.Qt.Key_L, self)
        self.toggle_log_shortcut.activated.connect(self.toggle_log)

        # Central tabs
        self.tabs = QtWidgets.QTabWidget()
        self.devices = DevicesView(self.ctrl, self.log_bus)
        self.wifi = WiFiView(self.ctrl, self.store)
        self.wizard = WizardPage(self.ctrl, self.devices, self.wifi)

        self.tabs.addTab(self.devices, "Devices")
        self.tabs.addTab(self.wifi, "Wi‑Fi")
        self.tabs.addTab(self.wizard, "New Network Setup")
        self.setCentralWidget(self.tabs)
        
        # Connect tab change signal to trigger auto-discovery
        self.tabs.currentChanged.connect(self._on_tab_changed)

        # Log dock (hidden by default)
        self.log_dock = QtWidgets.QDockWidget("Log", self)
        self.log_view = QtWidgets.QTextEdit()
        self.log_view.setReadOnly(True)
        self.log_view.setMaximumHeight(200)  # Limit height when visible
        self.log_dock.setWidget(self.log_view)
        self.addDockWidget(QtCore.Qt.BottomDockWidgetArea, self.log_dock)
        self.log_dock.hide()  # Hide by default
        self.log_bus.message.connect(self._append_log)

        self.status = self.statusBar()
        self.load_sites()

    def _append_log(self, text: str):
        self.log_view.append(text)

    def toggle_log(self):
        """Toggle the log dock visibility"""
        if self.log_dock.isVisible():
            self.log_dock.hide()
            self.btn_toggle_log.setText("Show Log")
            self.btn_toggle_log.setChecked(False)
        else:
            self.log_dock.show()
            self.btn_toggle_log.setText("Hide Log")
            self.btn_toggle_log.setChecked(True)

    # ----- actions -----
    def open_settings(self):
        dlg = SettingsDialog(self.store, self)
        if dlg.exec_() == QtWidgets.QDialog.Accepted:
            # Rebuild controller with new settings
            self.ctrl = ControllerClient(self.store, self.log_bus)
            self.devices.ctrl = self.ctrl
            self.wifi.ctrl = self.ctrl
            self.wizard.ctrl = self.ctrl
            self.load_sites()

    def login(self):
        ok = self.ctrl.login()
        self.status.showMessage("Login OK" if ok else "Login failed", 5000)
        if ok:
            self.load_sites()

    def load_sites(self):
        self.cmb_sites.blockSignals(True)
        self.cmb_sites.clear()
        # Try login implicitly for convenience
        self.ctrl.login()
        sites = self.ctrl.get_sites() or []
        active_key = self.store.get_value("site_key", "default")
        idx_to_select = 0
        for i, s in enumerate(sites):
            name = s.get("desc") or s.get("name") or s.get("site_name") or "default"
            key = s.get("name") or s.get("site_name") or "default"
            self.cmb_sites.addItem(f"{name} ({key})", key)
            if key == active_key:
                idx_to_select = i
        if self.cmb_sites.count() == 0:
            self.cmb_sites.addItem("default (default)", "default")
        self.cmb_sites.setCurrentIndex(idx_to_select)
        self.cmb_sites.blockSignals(False)
        # propagate to views
        key = self.cmb_sites.currentData()
        self.site_selected(key)

    def _site_changed(self, _idx):
        key = self.cmb_sites.currentData()
        self.site_selected(key)

    def site_selected(self, key: str):
        key = key or "default"
        self.store.set_value("site_key", key)
        self.devices.set_site(key)
        self.wifi.set_site(key)
        self.status.showMessage(f"Active site: {key}", 4000)

    def _on_tab_changed(self, index: int):
        """Called when the active tab changes. Triggers auto-discovery for wizard tab."""
        if index == 2:  # Wizard tab is at index 2
            self.wizard.on_tab_visible()
