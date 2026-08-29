from pathlib import Path


project_dir = Path(SPECPATH)


def resource_files(folder):
    root = project_dir / folder
    return [
        (str(path), str(path.parent.relative_to(project_dir)))
        for path in root.rglob("*")
        if path.is_file() and "__pycache__" not in path.parts
    ]


datas = resource_files("templates") + resource_files("static") + resource_files("migrations")
icon_file = project_dir / "app.ico"

a = Analysis(
    [str(project_dir / "desktop.py")],
    pathex=[str(project_dir)],
    binaries=[],
    datas=datas,
    hiddenimports=[
        "logging.config",
        "webview.platforms.edgechromium",
        "webview.platforms.mshtml",
        "webview.platforms.win32",
        "webview.platforms.winforms",
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
    name="TaskFlow",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    icon=str(icon_file) if icon_file.exists() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="TaskFlow",
)

