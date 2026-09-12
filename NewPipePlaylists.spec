# PyInstaller spec file for NewPipe Playlist Browser.
#
# Usage (run on Windows, in the same folder as this file and the .py script):
#   pip install pyinstaller
#   pyinstaller NewPipePlaylists.spec
#
# Output: dist\NewPipePlaylists.exe  (single portable file, no console window)
#
# If you have an app.ico, drop it in this same folder before building —
# it's already wired in below. If it's missing, PyInstaller just uses the
# default icon; nothing breaks.

# -*- mode: python ; coding: utf-8 -*-

block_cipher = None

a = Analysis(
    ['newpipe_playlist_browser.py'],
    pathex=[],
    binaries=[],
    datas=[],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name='NewPipePlaylists',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no terminal window behind the GUI
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='app.ico' if __import__('os').path.exists('app.ico') else None,
)
