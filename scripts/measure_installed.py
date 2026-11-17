"""
18d8: measure the INSTALLED app, old window against new, the same way.

    python scripts/measure_installed.py [runs]        # default 5 runs each

Installs each Test Build silently into a temp folder (its own AppId, so a
real JobLens is never touched), with LOCALAPPDATA pointed at a temp folder
(a fresh, empty data folder), measures, and uninstalls it again:

    old: dist/JobLens-TestBuild-Setup-1.2.1.exe   1.2.0's app (pywebview), built before that release
    new: dist/JobLens-TestBuild-Setup-2.0.0.exe   version 3 (the Rust window + engine\\)

Both are started normally, as you would (no smoke mode: in 1.2.0 that
skipped the tray, the quick box and the shortcut, and with --screenshot it
reported 1.5 s late; the first attempt at 18d8 was fooled by that), with
WebView2's debug port open so this script can watch the page.

Time to data: from launching JobLens.exe until the page has its first answer
from Python (app_info), when the screens can show your data: the page sets
window.__joblens_ready then (both versions). Checked every 0.05 s.
The first run of each is a warm-up and is not counted.

Memory: everything JobLens.exe started (WebView2's processes, Python),
added up, sampled every 0.1 s: one second after the page was ready, and the
peak over the first three seconds after ready. Then the app is closed.

Also: installer size, app folder size.
"""

import json
import os
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import psutil

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build_installer import REAL_APP_ID, ROOT, TEST_APP_ID, uninstall_entry  # noqa: E402

DIST = ROOT / "dist"
MB = 1024 * 1024
BUILDS = {"1.2.0 (pywebview)": DIST / "JobLens-TestBuild-Setup-1.2.1.exe",
          "version 3 (Rust)": DIST / "JobLens-TestBuild-Setup-2.0.0.exe"}


class TreeMemory:
    """The memory of a process and everything it started, every 0.1 s."""

    def __init__(self, pid: int):
        self.root = psutil.Process(pid)
        self.started = time.perf_counter()
        self.samples: list[tuple[float, int]] = []
        threading.Thread(target=self._sample, daemon=True).start()

    def _sample(self) -> None:
        while True:
            try:
                procs = [self.root, *self.root.children(recursive=True)]
            except psutil.Error:
                return
            total = 0
            for p in procs:
                try:
                    total += p.memory_info().rss
                except psutil.Error:
                    pass
            self.samples.append((time.perf_counter() - self.started, total))
            time.sleep(0.1)

    def at(self, seconds: float) -> int:
        """The last reading before `seconds` after launch."""
        before = [m for t, m in self.samples if t <= seconds]
        return before[-1] if before else 0

    @property
    def peak(self) -> int:
        return max((m for _, m in self.samples), default=0)


def folder_mb(folder: Path) -> float:
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file()) / MB


CDP_PORT = 9348


def page_ready() -> bool:
    """True once the main page (not the quick box) has set __joblens_ready."""
    import asyncio
    import urllib.request

    import websockets

    with urllib.request.urlopen(f"http://127.0.0.1:{CDP_PORT}/json", timeout=1) as response:
        pages = [p for p in json.load(response) if p.get("type") == "page" and "#/quick" not in p.get("url", "")]
    if not pages:
        return False

    async def ask():
        async with websockets.connect(pages[0]["webSocketDebuggerUrl"], max_size=None) as ws:
            await ws.send(json.dumps({"id": 1, "method": "Runtime.evaluate",
                                      "params": {"expression": "!!window.__joblens_ready", "returnByValue": True}}))
            while True:
                message = json.loads(await asyncio.wait_for(ws.recv(), 2))
                if message.get("id") == 1:
                    return bool(message.get("result", {}).get("result", {}).get("value"))
    return asyncio.run(ask())


def close_cleanly(exe: Path, pid: int) -> None:
    """Close JobLens the way an installer does (Windows' Restart Manager), so
    the next start isn't slowed by recovering from a killed app; kill only
    what is still there after 20 s."""
    import ctypes
    from ctypes import wintypes

    rm = ctypes.windll.rstrtmgr
    session, key = wintypes.DWORD(), ctypes.create_unicode_buffer(64)
    if rm.RmStartSession(ctypes.byref(session), 0, key) == 0:
        try:
            files = (wintypes.LPCWSTR * 1)(str(exe))
            if rm.RmRegisterResources(session, 1, files, 0, None, 0, None) == 0:
                rm.RmShutdown(session, 0, None)
        finally:
            rm.RmEndSession(session)
    try:
        root = psutil.Process(pid)
        procs = [root, *root.children(recursive=True)]
    except psutil.Error:
        procs = []
    _, alive = psutil.wait_procs(procs, timeout=20)
    for p in alive:
        try:
            p.kill()
        except psutil.Error:
            pass
    if alive:
        print(f"  ! {len(alive)} process(es) didn't close by themselves: killed", flush=True)


def one_run(exe: Path, appdata: Path) -> tuple[float | None, int, int]:
    """(seconds to data, bytes one second after, peak bytes over three seconds after)."""
    env = {**os.environ, "LOCALAPPDATA": str(appdata),
           "WEBVIEW2_ADDITIONAL_BROWSER_ARGUMENTS": f"--remote-debugging-port={CDP_PORT}"}
    started = time.perf_counter()
    process = subprocess.Popen([str(exe)], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    memory = TreeMemory(process.pid)
    memory.started = started
    ready = None
    try:
        while time.perf_counter() - started < 60 and process.poll() is None:
            try:
                if page_ready():
                    ready = time.perf_counter() - started
                    break
            except Exception:  # not up yet
                pass
            time.sleep(0.05)
        if ready is None:
            return None, 0, 0
        time.sleep(3.2)
        after = memory.at(ready + 1.0)
        peak = max((m for t, m in memory.samples if t <= ready + 3.0), default=0)
        return ready, after, peak
    finally:
        close_cleanly(exe, process.pid)


def measure(name: str, setup: Path, runs: int) -> dict:
    print(f"\n=== {name}: {setup.name} ===", flush=True)
    if uninstall_entry(TEST_APP_ID):
        sys.exit("A JobLens Test Build is still installed: uninstall it first.")
    tmp = Path(tempfile.mkdtemp(prefix="joblens-measure-"))
    folder, appdata = tmp / "JobLens Test Build", tmp / "appdata"
    (appdata / "JobLens" / "data").mkdir(parents=True)
    (appdata / "JobLens" / ".env").write_text("SETUP_DONE=true\nUPDATE_CHECK=false\nQUICK_KEY=Ctrl+Alt+F9\nTRACING=off\n",
                                              encoding="utf-8")
    try:
        subprocess.run([str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART", f"/DIR={folder}"], check=True)
        exe = folder / "JobLens.exe"
        result = {"installer_mb": setup.stat().st_size / MB, "folder_mb": folder_mb(folder), "times": [], "after": [], "peaks": []}
        for i in range(runs + 1):
            ready, after, peak = one_run(exe, appdata)
            label = "warm-up" if i == 0 else f"run {i}"
            print(f"  {label}: " + (f"{ready:.2f} s to data, {after / MB:.0f} MB after 1 s, peak {peak / MB:.0f} MB"
                                    if ready else "no report"), flush=True)
            if i and ready:
                result["times"].append(ready)
                result["after"].append(after / MB)
                result["peaks"].append(peak / MB)
            time.sleep(2)
        return result
    finally:
        uninstaller = folder / "unins000.exe"
        if uninstaller.exists():
            subprocess.run([str(uninstaller), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART"])
        for _ in range(90):
            if not uninstall_entry(TEST_APP_ID) and not (folder / "JobLens.exe").exists():
                break
            time.sleep(1)
        shutil.rmtree(tmp, ignore_errors=True)


def main() -> int:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 5
    for setup in BUILDS.values():
        if not setup.exists():
            sys.exit(f"{setup.name} is missing from dist/ (see scripts/check_real_update.py).")
    real = uninstall_entry(REAL_APP_ID)
    results = {name: measure(name, setup, runs) for name, setup in BUILDS.items()}
    if uninstall_entry(REAL_APP_ID) != real:
        sys.exit("The REAL JobLens install changed - this must never happen.")

    print("\n| | " + " | ".join(results) + " |\n|---|" + "---|" * len(results))
    rows = [("Installer", lambda r: f"{r['installer_mb']:.1f} MB"),
            ("App folder", lambda r: f"{r['folder_mb']:.0f} MB"),
            ("Time to data (median)", lambda r: f"{statistics.median(r['times']):.2f} s" if r["times"] else "-"),
            ("Memory 1 s after (median)", lambda r: f"{statistics.median(r['after']):.0f} MB" if r["after"] else "-"),
            ("Peak, first 3 s after (median)", lambda r: f"{statistics.median(r['peaks']):.0f} MB" if r["peaks"] else "-")]
    for label, show in rows:
        print(f"| {label} | " + " | ".join(show(r) for r in results.values()) + " |")
    (ROOT / "build").mkdir(exist_ok=True)
    (ROOT / "build" / "measure_installed.json").write_text(json.dumps(results, indent=1), encoding="utf-8")
    print(f"\nYour JobLens ({(real or {}).get('DisplayVersion', 'not installed')}) was not touched.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
