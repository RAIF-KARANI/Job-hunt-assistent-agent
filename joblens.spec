# PyInstaller recipe for JobLens.exe (Phase 9f; web UI since 12h).
#
# Build (venv activated, from the repo root) - normally via
#     python scripts/build_installer.py
# which builds the front end first (frontend -> desktop_web/web) and then:
#     pyinstaller joblens.spec --noconfirm
# Result:
#     dist\JobLens\JobLens.exe     (+ dist\JobLens\_internal\ with Python and libraries)
# Check the build:
#     dist\JobLens\JobLens.exe --self-test selftest.txt     (no window)
#     dist\JobLens\JobLens.exe --smoke smoke.json           (opens the window)
#
# How PyInstaller works: it starts from the entry script, follows every
# `import` to find the modules the app needs, and copies them - plus a
# Python interpreter - into one folder. "Freezing" = bundling, not compiling.

from pathlib import Path

from PyInstaller.utils.hooks import copy_metadata

if not Path("desktop_web/web/index.html").exists():
    raise SystemExit("The UI isn't built: run `npm ci && npm run build` in frontend/ first "
                     "(scripts/build_installer.py does it for you).")

# Files the app opens at runtime (read via paths.resource_path()).
datas = [("desktop_web/web", "desktop_web/web"),   # the built React UI (12h)
         ("assets/joblens.png", "assets"), ("assets/joblens.ico", "assets"),
         ("LICENSE", "."), ("THIRD_PARTY_NOTICES.md", ".")]

# Some libraries look up their own version at import time
# (importlib.metadata.version("langsmith") ...). That information lives in
# the package's *.dist-info folder, which PyInstaller doesn't copy unless asked.
for package in ["langchain", "langchain-core", "langgraph", "langgraph-checkpoint",
                "langgraph-checkpoint-sqlite", "langsmith", "langchain-ollama", "ollama",
                "langchain-anthropic", "anthropic", "ddgs", "pydantic", "langfuse", "pywebview"]:
    try:
        datas += copy_metadata(package)
    except Exception as e:  # not installed -> skip, but say so in the build log
        print(f"[joblens.spec] no metadata for {package}: {e}")

a = Analysis(
    ["desktop_web/__main__.py"],
    pathex=["."],
    datas=datas,
    # Imported inside functions (only when that provider / screen is used), so be explicit.
    hiddenimports=["langchain_ollama", "langchain_anthropic", "desktop_web.selftest",
                   "job_agent.monitoring", "job_agent.system_check", "job_agent.ollama_setup"],
    # The web app never uses these. The old Qt UI (PySide6, matplotlib) is
    # left out of the build since 12h and deleted from the repo in 12i.
    # PIL is only for the developer screenshot helper.
    excludes=["PySide6", "shiboken6", "matplotlib", "PIL", "streamlit", "altair", "pydeck",
              "pyarrow", "pytest", "_pytest", "IPython", "jupyter", "notebook", "tkinter"],
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
