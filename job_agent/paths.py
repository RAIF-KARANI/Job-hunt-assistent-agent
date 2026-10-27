"""
Phase 9a: where the app keeps its files - the ONE place that decides.

Two modes:
    Developer mode (running from the repo, e.g. `python main.py`):
        settings   <repo>/.env
        user data  <repo>/data/            (resumes, jobs.db, cover notes...)
    Installed mode (the packaged Windows app, Phase 9f):
        settings   %LOCALAPPDATA%\\JobLens\\.env
        user data  %LOCALAPPDATA%\\JobLens\\data\\

Why: an installed app's code lives in a folder the user may not be allowed
to write to (e.g. Program Files), and it can be started from anywhere, so
"the current folder" means nothing. %LOCALAPPDATA% is Windows' standard
per-user, writable place for app data (it's not synced to other PCs, which
is right for private resumes and databases).

Override for testing or a second profile:  set JOB_HUNT_HOME=C:\\some\\folder
"""

import os
import sys
from pathlib import Path

APP_NAME = "JobLens"
REPO_DIR = Path(__file__).resolve().parent.parent

# PyInstaller sets sys.frozen = True inside the packaged .exe.
IS_INSTALLED = bool(getattr(sys, "frozen", False))


def _app_home() -> Path:
    if os.getenv("JOB_HUNT_HOME"):
        return Path(os.environ["JOB_HUNT_HOME"])
    if IS_INSTALLED:
        return Path(os.getenv("LOCALAPPDATA", Path.home() / "AppData" / "Local")) / APP_NAME
    return REPO_DIR


APP_HOME = _app_home()
ENV_FILE = APP_HOME / ".env"          # settings (model, API key, tracing...)
DATA_DIR = APP_HOME / "data"          # resumes (*.pdf) + everything below
DB_PATH = DATA_DIR / "jobs.db"        # the tracker
CHECKPOINT_DB = DATA_DIR / "checkpoints.db"  # paused runs (web UI + desktop app)
NOTES_DIR = DATA_DIR / "cover_notes"  # approved cover notes as .md files


def resource_path(relative: str) -> Path:
    """A file SHIPPED with the app (e.g. assets/joblens.png), in both modes.

    Bundled files are read-only and live next to the code: in the repo during
    development, and in PyInstaller's unpack folder (sys._MEIPASS) inside the
    packaged app. User data never goes here - that's DATA_DIR.
    """
    base = Path(getattr(sys, "_MEIPASS", REPO_DIR))
    return base / relative


def ensure_dirs() -> None:
    """Create the data folder on first use."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
