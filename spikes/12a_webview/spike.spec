# Spike 12a: how big is JobLens without Qt? Same agent, web UI instead.
# Build (from spikes/12a_webview, venv active):  pyinstaller spike.spec --noconfirm

from PyInstaller.utils.hooks import copy_metadata

datas = [("web/index.html", "web"), ("web/three.module.min.js", "web")]
for package in ["langchain", "langchain-core", "langgraph", "langgraph-checkpoint",
                "langgraph-checkpoint-sqlite", "langsmith", "langchain-ollama", "ollama",
                "langchain-anthropic", "anthropic", "ddgs", "pydantic", "langfuse", "pywebview"]:
    try:
        datas += copy_metadata(package)
    except Exception as e:
        print(f"[spike.spec] no metadata for {package}: {e}")

a = Analysis(
    ["spike.py"],
    pathex=["../.."],                      # repo root -> job_agent
    datas=datas,
    hiddenimports=["langchain_ollama", "langchain_anthropic", "job_agent.graph"],
    # Same excludes as joblens.spec, plus the Qt UI stack the web UI replaces.
    excludes=["streamlit", "altair", "pydeck", "pyarrow", "pytest", "_pytest",
              "IPython", "jupyter", "notebook", "tkinter",
              "PySide6", "shiboken6", "matplotlib"],
)
pyz = PYZ(a.pure)
exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="JobLensSpike",
          console=False, icon="../../assets/joblens.ico")
coll = COLLECT(exe, a.binaries, a.datas, name="JobLensSpike")
