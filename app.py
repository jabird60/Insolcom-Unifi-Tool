import sys
import os
from PyQt5 import QtWidgets, QtGui, QtCore
from innovative_unifi.ui.main_window import MainWindow

def main():
    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName("Innovative Solutions — UniFi AP Field Tool")
    
    # Set application icon
    try:
        # Try to load icon from file
        icon_path = os.path.join(os.path.dirname(__file__), "app_icon.ico")
        if os.path.exists(icon_path):
            app.setWindowIcon(QtGui.QIcon(icon_path))
        else:
            # Create a simple icon programmatically if file doesn't exist
            create_simple_icon(app)
    except Exception:
        # Fallback to simple icon creation
        create_simple_icon(app)
    
    w = MainWindow()
    w.resize(1200, 800)
    w.show()
    sys.exit(app.exec_())

def create_simple_icon(app):
    """Create a simple UniFi-style icon programmatically"""
    try:
        # Create a 64x64 pixmap
        pixmap = QtGui.QPixmap(64, 64)
        pixmap.fill(QtCore.Qt.transparent)
        
        # Create a QPainter
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Draw white circular device
        device_rect = QtCore.QRect(8, 8, 48, 48)
        painter.setBrush(QtGui.QBrush(QtCore.Qt.white))
        painter.setPen(QtGui.QPen(QtCore.Qt.lightGray, 1))
        painter.drawEllipse(device_rect)
        
        # Draw blue light ring
        inner_rect = QtCore.QRect(16, 16, 32, 32)
        painter.setBrush(QtGui.QBrush(QtCore.Qt.transparent))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 120, 255), 3))
        painter.drawEllipse(inner_rect)
        
        # Draw 'U' logo
        painter.setPen(QtGui.QPen(QtCore.Qt.lightGray, 2))
        painter.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
        painter.drawText(inner_rect, QtCore.Qt.AlignCenter, "U")
        
        painter.end()
        
        # Set as application icon
        icon = QtGui.QIcon(pixmap)
        app.setWindowIcon(icon)
    except Exception:
        pass  # If icon creation fails, continue without icon

if __name__ == "__main__":
    main()
