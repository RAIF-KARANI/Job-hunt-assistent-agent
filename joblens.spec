# PyInstaller recipe for JobLens's engine (18d6, version 3; the pywebview
# app's recipe before that).
#
# Version 3 (E2, E6): the window is the Rust program (desktop_tauri/,
# JobLens.exe), which starts this engine beside it and talks to it over a
# pipe. So this builds Python and the agent only: no window, no tray library.
#
# Build - normally via
#     python scripts/build_installer.py
# which builds the front end and the Rust window first, then:
#     pyinstaller joblens.spec --noconfirm
# Result:
#     dist\engine\joblens-engine.exe   (+ dist\engine\_internal\ with Python and libraries)
# The installer puts it in {app}\engine\, where JobLens.exe looks for it.
# Check it alone (no window):
#     dist\engine\joblens-engine.exe --self-test selftest.txt
#
# How PyInstaller works: it starts from the entry script, follows every
# `import` to find the modules the app needs, and copies them - plus a
# Python interpreter - into one folder. "Freezing" = bundling, not compiling.

from PyInstaller.utils.hooks import copy_metadata

# Files the engine opens at runtime (read via paths.resource_path()). The UI
# itself is built into JobLens.exe, so it isn't needed here.
datas = [("assets/joblens.png", "assets"), ("assets/joblens.ico", "assets"),
         ("LICENSE", "."), ("THIRD_PARTY_NOTICES.md", ".")]

# Some libraries look up their own version at import time
# (importlib.metadata.version("langsmith") ...). That information lives in
# the package's *.dist-info folder, which PyInstaller doesn't copy unless asked.
for package in ["langchain", "langchain-core", "langgraph", "langgraph-checkpoint",
                "langgraph-checkpoint-sqlite", "langsmith", "langchain-ollama", "ollama",
                "langchain-anthropic", "anthropic", "ddgs", "pydantic", "langfuse",
                # 16c: OpenAI and Gemini can be chosen in Settings since 1.2.0
                "langchain-openai", "openai", "tiktoken", "langchain-google-genai", "google-genai"]:
    try:
        datas += copy_metadata(package)
    except Exception as e:  # not installed -> skip, but say so in the build log
        print(f"[joblens.spec] no metadata for {package}: {e}")

a = Analysis(
    ["desktop_web/engine.py"],
    pathex=["."],
    datas=datas,
    # Imported inside functions (only when that provider / screen is used), so be explicit.
    hiddenimports=["langchain_ollama", "langchain_anthropic", "langchain_openai", "langchain_google_genai",
                   "tiktoken_ext.openai_public", "tiktoken_ext",  # tiktoken finds its encodings by name
                   "desktop_web.selftest", "job_agent.providers",
                   "job_agent.monitoring", "job_agent.system_check", "job_agent.ollama_setup"],
    # Not in the engine: the window and the tray are Rust's now (pywebview,
    # pystray and pythonnet stay for `python -m desktop_web` from source).
    # PySide6 / matplotlib belonged to the Qt UI (removed in 12i).
    excludes=["webview", "pystray", "pythonnet", "clr_loader", "bottle", "proxy_tools",
              "PySide6", "shiboken6", "matplotlib", "streamlit", "altair", "pydeck",
              "pyarrow", "pytest", "_pytest", "IPython", "jupyter", "notebook", "tkinter"],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,   # "one folder" build: starts fast, easy to inspect
    name="joblens-engine",
    icon="assets/joblens.ico",
    # A console program, so its stdin/stdout are the pipe to JobLens.exe.
    # JobLens.exe starts it with CREATE_NO_WINDOW: no console box appears.
    console=True,
    upx=False,
)

coll = COLLECT(exe, a.binaries, a.datas, name="engine", upx=False)
