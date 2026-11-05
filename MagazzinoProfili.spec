# -*- mode: python ; coding: utf-8 -*-
from PyInstaller.utils.hooks import collect_all, collect_data_files
from pathlib import Path
import os

# Il file di configurazione (con le credenziali) NON è incorporato: resta accanto all'eseguibile.
datas = [('migrations', 'migrations'), ('icona.ico', '.'),
         ('magazzino_profili/web/templates', 'magazzino_profili/web/templates'),
         ('magazzino_profili/web/static', 'magazzino_profili/web/static')]
datas += [('magazzino_profili/services/ocr_commessa.ps1', 'magazzino_profili/services')]
datas += [(str(p), 'catalogo_immagini') for p in Path('catalogo_immagini').glob('*')
          if p.suffix.lower() in ('.png', '.csv')]
datas += collect_data_files('barcode')
binaries = []
hiddenimports = ['psycopg', 'qrcode', 'magazzino_profili.web.app',
                 'uvicorn.logging', 'uvicorn.loops.auto', 'uvicorn.protocols.http.auto',
                 'uvicorn.protocols.websockets.auto', 'uvicorn.lifespan.on']
tmp_ret = collect_all('reportlab')
datas += tmp_ret[0]; binaries += tmp_ret[1]; hiddenimports += tmp_ret[2]


a = Analysis(
    ['MagazzinoApp.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=['pytest', 'PySide6.QtTest', 'PySide6.QtWebEngineCore',
              'PySide6.QtWebEngineWidgets', 'PySide6.QtWebEngineQuick', 'numpy', 'tkinter'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MagazzinoProfili',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    version=os.environ.get('MAGAZZINO_VERSION_INFO'),
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='icona.ico',
)

# Distribuzione in cartella: nessuna estrazione dei DLL a ogni avvio.
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name='MagazzinoProfili')
