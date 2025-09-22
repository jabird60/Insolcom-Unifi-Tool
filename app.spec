# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['app.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[
        'PyQt5.QtCore',
        'PyQt5.QtWidgets', 
        'PyQt5.QtGui',
        'psutil',
        'paramiko',
        'requests',
        'cryptography',
        'innovative_unifi.core.controller',
        'innovative_unifi.core.discovery',
        'innovative_unifi.core.settings_store',
        'innovative_unifi.core.logger_bus',
        'innovative_unifi.ui.main_window',
        'innovative_unifi.ui.devices_view',
        'innovative_unifi.ui.wifi_view',
        'innovative_unifi.ui.wizard_page',
        'innovative_unifi.ui.settings_dialog'
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='app',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=True,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='app',
)
