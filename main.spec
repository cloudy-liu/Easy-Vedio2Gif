# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path

block_cipher = None

# 获取当前脚本目录
base_dir = Path(os.path.abspath("."))

# 定义需要添加的数据文件
added_files = [
    # 添加ffmpeg和ffprobe工具
    (str(base_dir / 'lib' / 'windows'), 'lib/windows'),
    (str(base_dir / 'lib' / 'mac'), 'lib/mac'),
    # 添加res目录下的图标
    (str(base_dir / 'res' / 'icons'), 'res/icons'),
]

a = Analysis(
    ['main.py'],
    pathex=[str(base_dir)],
    binaries=[],
    datas=added_files,
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

# 第一部分：主执行文件
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,  # 关键修改：排除二进制文件
    name='Video2Gif',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(base_dir / 'res' / 'icons' / 'app.ico'),
)

# 第二部分：收集所有文件到一个目录中
coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='Video2Gif',
) 