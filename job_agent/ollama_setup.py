"""
Phase 10b: get Ollama and a model ready - without the user opening a terminal.

    is_installed()   find ollama.exe (PATH, or the default per-user folder)
    is_running()     is the Ollama server answering on localhost:11434?
    start()          start the server if it's installed but not running
    installed_models()
    install_command()     the winget command that installs Ollama
    pull(name, progress)  download a model, reporting progress

Downloads use Ollama's HTTP API (/api/pull with stream=true): the server
sends one JSON line per update, e.g.
    {"status": "pulling 8eeb52dfb3bb", "completed": 1234567, "total": 5200000000}
parse_pull_line() turns each line into (message, fraction) for a progress
bar; it's pure, so it's unit-tested.
"""

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import requests

DEFAULT_URL = "http://localhost:11434"
WINGET_ID = "Ollama.Ollama"
DOWNLOAD_PAGE = "https://ollama.com/download/windows"


def base_url() -> str:
    return os.getenv("OLLAMA_BASE_URL", DEFAULT_URL).rstrip("/")


def find_ollama() -> Path | None:
    """ollama.exe on PATH, or where the Windows installer puts it per user."""
    on_path = shutil.which("ollama")
    if on_path:
        return Path(on_path)
    default = Path(os.getenv("LOCALAPPDATA", "")) / "Programs" / "Ollama" / "ollama.exe"
    return default if default.exists() else None


def is_installed() -> bool:
    return find_ollama() is not None


def is_running() -> bool:
    try:
        return requests.get(f"{base_url()}/api/version", timeout=2).ok
    except requests.RequestException:
        return False


def start(wait_seconds: float = 20) -> bool:
    """Start `ollama serve` in the background (no console window) and wait for it."""
    if is_running():
        return True
    exe = find_ollama()
    if not exe:
        return False
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0) | getattr(subprocess, "DETACHED_PROCESS", 0)
    subprocess.Popen([str(exe), "serve"], creationflags=flags,
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    end = time.time() + wait_seconds
    while time.time() < end:
        if is_running():
            return True
        time.sleep(0.5)
    return False


def installed_models() -> list[str]:
    try:
        tags = requests.get(f"{base_url()}/api/tags", timeout=5).json()
        return sorted(m["name"] for m in tags.get("models", []))
    except requests.RequestException:
        return []


def winget_available() -> bool:
    return shutil.which("winget") is not None


def install_command() -> list[str]:
    """Per-user install, no admin prompt, no interactive questions."""
    return ["winget", "install", "--id", WINGET_ID, "-e", "--scope", "user",
            "--accept-package-agreements", "--accept-source-agreements",
            "--disable-interactivity"]


def _size(n: float) -> str:
    """Bytes -> '5.23 GB' / '488 MB' / '12 KB' (small layers aren't '0.00 GB')."""
    for unit, scale in (("GB", 1e9), ("MB", 1e6), ("KB", 1e3)):
        if n >= scale:
            return f"{n / scale:.2f} {unit}" if unit == "GB" else f"{n / scale:.0f} {unit}"
    return f"{n:.0f} B"


def parse_pull_line(line: str) -> tuple[str, float | None]:
    """One streamed /api/pull line -> (message, fraction 0..1 or None)."""
    try:
        data = json.loads(line)
    except json.JSONDecodeError:
        return line.strip(), None
    if data.get("error"):
        raise RuntimeError(data["error"])
    status = data.get("status", "")
    total, done = data.get("total"), data.get("completed")
    if total and done is not None:
        fraction = min(done / total, 1.0)
        return f"{status.split(' ')[0]}: {_size(done)} of {_size(total)}", fraction
    return status, None


def pull(model: str, on_progress=None) -> None:
    """Download a model. on_progress(message, fraction) is called for each update.

    Blocking (minutes for a 5 GB model): call it from a background thread.
    """
    with requests.post(f"{base_url()}/api/pull", json={"model": model, "stream": True},
                       stream=True, timeout=(10, 600)) as r:
        r.raise_for_status()
        for raw in r.iter_lines():
            if not raw:
                continue
            message, fraction = parse_pull_line(raw.decode("utf-8", errors="replace"))
            if on_progress:
                on_progress(message, fraction)
