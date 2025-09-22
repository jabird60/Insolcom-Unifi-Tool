from PyQt5 import QtWidgets, QtCore
from ..core.settings_store import SettingsStore

class SettingsDialog(QtWidgets.QDialog):
    def __init__(self, store: SettingsStore, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Settings")
        self.store = store

        self.ed_url = QtWidgets.QLineEdit(self.store.get_value("controller_url",""))
        self.ed_inform = QtWidgets.QLineEdit(self.store.get_value("inform_url",""))
        self.ed_user = QtWidgets.QLineEdit(self.store.get_value("controller_user",""))
        self.ed_pass = QtWidgets.QLineEdit(self.store.get_value("controller_pass",""))
        self.ed_pass.setEchoMode(QtWidgets.QLineEdit.Password)
        self.cb_verify = QtWidgets.QCheckBox("Verify SSL certificates (uncheck for self-signed)")
        self.cb_verify.setChecked(bool(self.store.get_value("verify_ssl", False)))

        self.ed_ssh_user = QtWidgets.QLineEdit(self.store.get_value("ssh_user","ubnt"))
        self.ed_ssh_pass = QtWidgets.QLineEdit(self.store.get_value("ssh_pass","ubnt"))
        self.ed_ssh_pass.setEchoMode(QtWidgets.QLineEdit.Password)

        form = QtWidgets.QFormLayout()
        form.addRow("Controller URL:", self.ed_url)
        form.addRow("Inform URL (for set-inform):", self.ed_inform)
        form.addRow("Username:", self.ed_user)
        form.addRow("Password:", self.ed_pass)
        form.addRow("", self.cb_verify)
        form.addRow(QtWidgets.QLabel("<b>SSH defaults for APs</b>"))
        form.addRow("SSH User:", self.ed_ssh_user)
        form.addRow("SSH Pass:", self.ed_ssh_pass)

        btns = QtWidgets.QDialogButtonBox(QtWidgets.QDialogButtonBox.Save | QtWidgets.QDialogButtonBox.Cancel)
        btns.accepted.connect(self.accept)
        btns.rejected.connect(self.reject)

        lay = QtWidgets.QVBoxLayout(self)
        lay.addLayout(form)
        lay.addWidget(btns)

    def accept(self):
        self.store.set_value("controller_url", self.ed_url.text().strip())
        self.store.set_value("inform_url", self.ed_inform.text().strip())
        self.store.set_value("controller_user", self.ed_user.text().strip())
        self.store.set_value("controller_pass", self.ed_pass.text())
        self.store.set_value("verify_ssl", bool(self.cb_verify.isChecked()))
        self.store.set_value("ssh_user", self.ed_ssh_user.text().strip())
        self.store.set_value("ssh_pass", self.ed_ssh_pass.text())
        super().accept()
