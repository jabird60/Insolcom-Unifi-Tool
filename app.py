import sys
from PyQt5 import QtWidgets
from innovative_unifi.ui.main_window import MainWindow

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Innovative Solutions — UniFi AP Field Tool")
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
