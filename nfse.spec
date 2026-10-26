# -*- mode: python ; coding: utf-8 -*-
"""Configuracao do PyInstaller para gerar o executavel (ondir).

Uso:
    pip install -r requirements-build.txt
    pyinstaller nfse.spec --noconfirm
"""

import os
import sys

block_cipher = None
RAIZ = os.path.abspath(os.getcwd())


def _dados_config() -> list:
    """Nada sensivel e embutido: o config.json fica ao lado do .exe.

    O instalador copia config.json.exemplo; o usuario preenche os dados.
    Embutir o config.json levaria senha/certificado para dentro do executavel.
    """
    return []


a = Analysis(
    [os.path.join("src", "main.py")],
    pathex=[os.path.join(RAIZ, "src")],
    binaries=[],
    datas=_dados_config(),
    hiddenimports=[
        "cryptography.hazmat.backends.openssl",
        "cryptography.hazmat.primitives.asymmetric.padding",
        "signxml",
        "lxml.etree",
        "lxml._elementpath",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "matplotlib", "numpy", "pandas", "pytest"],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="nfse-santana",
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
    icon=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="nfse-santana",
)
