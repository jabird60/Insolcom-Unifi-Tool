from PyQt5 import QtCore

class LogBus(QtCore.QObject):
    message = QtCore.pyqtSignal(str)

    def log(self, text: str):
        self.message.emit(text)
