from pathlib import Path

root = Path(SPECPATH).resolve()
sample_dsl_files = sorted((root / "samples").glob("*.circuit.yaml"))
if not sample_dsl_files:
    raise RuntimeError("No CircuitDSL sample files found")

datas = [
    (str(root / "schemas"), "schemas"),
    *((str(path), "samples") for path in sample_dsl_files),
    (str(root / "docs"), "docs"),
    (str(root / "circuitstudio" / "pcbnew_adapter.py"), "circuitstudio"),
]

a = Analysis(
    [str(root / "app.py")],
    pathex=[str(root)],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="CircuitStudioAI",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=False, name="CircuitStudioAI")
