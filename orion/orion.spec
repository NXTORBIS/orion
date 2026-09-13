# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for bundling ORION as a standalone executable

import os
from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

# Collect all ORION modules and data
orion_modules = collect_submodules('orion')
orion_datas = collect_data_files('orion', includes=['configs/**', 'registry/**'])

# Add PyTorch and related libraries (these are large, so be selective)
torch_datas = collect_data_files('torch')

a = Analysis(
    [os.path.join(os.path.dirname(__file__), 'src', 'orion', '__main__.py')],
    pathex=[os.path.join(os.path.dirname(__file__), 'src')],
    binaries=[],
    datas=orion_datas + torch_datas,
    hiddenimports=orion_modules + [
        'transformers',
        'torch',
        'trl',
        'peft',
        'datasets',
        'accelerate',
        'PIL',
        'numpy',
        'scipy',
        'sympy',
        'pyyaml',
        'safetensors',
        'huggingface_hub',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[
        'matplotlib',
        'pytest',
        'jupyter',
        'ipython',
    ],
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
    name='orion-api-server',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
