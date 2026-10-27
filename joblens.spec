# PyInstaller recipe for JobLens.exe (Phase 9f).
#
# Build (venv activated, from the repo root):
#     pyinstaller joblens.spec --noconfirm
# Result:
#     dist\JobLens\JobLens.exe     (+ dist\JobLens\_internal\ with Python, Qt, libraries)
# Check the build without opening a window:
#     dist\JobLens\JobLens.exe --self-test selftest.txt
#
# How PyInstaller works: it starts from desktop_app.py, follows every
# `import` to find the modules the app needs, and copies them - plus a
# Python interpreter - into one folder. "Freezing" = bundling, not compiling.

from PyInstaller.utils.hooks import copy_metadata

# Files the app opens at runtime (read via paths.resource_path()).
datas = [("assets/joblens.png", "assets"), ("assets/joblens.ico", "assets")]

# Some libraries look up their own version at import time
# (importlib.metadata.version("langsmith") ...). That information lives in
# the package's *.dist-info folder, which PyInstaller doesn't copy unless asked.
for package in ["langchain", "langchain-core", "langgraph", "langgraph-checkpoint",
                "langgraph-checkpoint-sqlite", "langsmith", "langchain-ollama", "ollama",
                "langchain-anthropic", "anthropic", "ddgs", "pydantic", "langfuse"]:
    try:
        datas += copy_metadata(package)
    except Exception as e:  # not installed -> skip, but say so in the build log
        print(f"[joblens.spec] no metadata for {package}: {e}")

a = Analysis(
    ["desktop_app.py"],
    pathex=["."],
    datas=datas,
    # Imported inside functions (only when that provider is chosen), so be explicit.
    hiddenimports=["langchain_ollama", "langchain_anthropic"],
    # The desktop app never uses these; leaving them out saves hundreds of MB.
    excludes=["streamlit", "altair", "pydeck", "pyarrow", "pytest", "_pytest",
              "IPython", "jupyter", "notebook", "tkinter", "PySide6.QtWebEngineCore"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # "one folder" build: starts fast, easy to inspect
    name="JobLens",
    icon="assets/joblens.ico",
    console=False,           # a windowed app: no black console window behind it
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="JobLens", upx=False)
