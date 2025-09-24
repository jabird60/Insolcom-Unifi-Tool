#!/usr/bin/env python3
"""
Setup script to create the app icon
"""
import sys
import os

def create_icon():
    """Create the app icon"""
    try:
        from PyQt5 import QtGui, QtCore
        from PyQt5.QtWidgets import QApplication
        
        # Create a QApplication instance (required for QPixmap)
        app = QApplication(sys.argv)
        
        # Create a 64x64 icon with the UniFi device design
        pixmap = QtGui.QPixmap(64, 64)
        pixmap.fill(QtCore.Qt.transparent)
        
        # Create a QPainter to draw the icon
        painter = QtGui.QPainter(pixmap)
        painter.setRenderHint(QtGui.QPainter.Antialiasing)
        
        # Draw the white circular device
        device_rect = QtCore.QRect(8, 8, 48, 48)
        painter.setBrush(QtGui.QBrush(QtCore.Qt.white))
        painter.setPen(QtGui.QPen(QtCore.Qt.lightGray, 1))
        painter.drawEllipse(device_rect)
        
        # Draw the blue light ring (inner circle)
        inner_rect = QtCore.QRect(16, 16, 32, 32)
        painter.setBrush(QtGui.QBrush(QtCore.Qt.transparent))
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 120, 255), 3))  # Bright blue
        painter.drawEllipse(inner_rect)
        
        # Draw the 'U' logo in the center
        painter.setPen(QtGui.QPen(QtCore.Qt.lightGray, 2))
        painter.setFont(QtGui.QFont("Arial", 12, QtGui.QFont.Bold))
        painter.drawText(inner_rect, QtCore.Qt.AlignCenter, "U")
        
        # Draw the gear/wrench icon in bottom-right
        gear_rect = QtCore.QRect(40, 40, 20, 20)
        painter.setBrush(QtGui.QBrush(QtGui.QColor(0, 120, 255)))  # Blue
        painter.setPen(QtGui.QPen(QtGui.QColor(0, 120, 255)))
        
        # Draw gear (simplified as a circle with notches)
        painter.drawEllipse(gear_rect)
        
        # Draw wrench inside gear (simplified as lines)
        painter.setPen(QtGui.QPen(QtCore.Qt.white, 2))
        center_x = gear_rect.center().x()
        center_y = gear_rect.center().y()
        
        # Draw wrench handle
        painter.drawLine(center_x - 4, center_y - 2, center_x + 4, center_y + 2)
        # Draw wrench head
        painter.drawLine(center_x - 2, center_y - 4, center_x + 2, center_y + 4)
        
        painter.end()
        
        # Save as ICO file for Windows
        pixmap.save("app_icon.ico", "ICO")
        
        # Also save as PNG for other platforms
        pixmap.save("app_icon.png", "PNG")
        
        print("✓ Icon created successfully!")
        print("  - app_icon.ico (Windows)")
        print("  - app_icon.png (Other platforms)")
        
        return True
        
    except ImportError:
        print("✗ PyQt5 not available. Cannot create icon.")
        print("  Install PyQt5 first: pip install PyQt5")
        return False
    except Exception as e:
        print(f"✗ Error creating icon: {e}")
        return False

if __name__ == "__main__":
    print("Creating UniFi GUI App Icon...")
    success = create_icon()
    
    if success:
        print("\n✓ Icon setup complete!")
        print("  The app will now use this icon when launched.")
    else:
        print("\n✗ Icon setup failed.")
        print("  The app will still work but without a custom icon.")
