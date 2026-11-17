"""Phase 18b: today's window vs the Tauri spike, on time and memory.

Both are started the same way and measured from outside. Both use the same
Python (the repo's .venv, from source) and do the same start-up work, so
only the window differs.

    .venv/Scripts/python spikes/18_tauri/measure.py [runs]

Time to ready: from launching the process until the page has its first
answer from Python (app_info), i.e. when the screens can show your data.
  - today:  `python -m desktop_web --smoke OUT` writes OUT once the page
            says it is ready (it checks every 0.25 s, so it can be up to
            0.25 s late; about 0.12 s on average)
  - spike:  JOBLENS_SPIKE_MEASURE=1 writes timing.json at its first answer

Memory: everything the app started (its WebView2 processes, the Python
side), added up, sampled every 0.1 s: the peak, and the last reading before
one second after the page was ready.
  - today's timing runs close at once, so memory comes from separate runs
    with --screenshot, which keeps the window open 1.5 s after ready.
"""

import json
import os
import statistics
import subprocess
import sys
import threading
import time
from pathlib import Path

import psutil

ROOT = Path(__file__).resolve().parents[2]
PYTHON = ROOT / ".venv" / "Scripts" / "python.exe"
SPIKE = ROOT / "spikes" / "18_tauri"
TAURI_EXE = SPIKE / "src-tauri" / "target" / "release" / "joblens-spike.exe"
TMP = Path(os.environ.get("TEMP", "."))
MB = 1024 * 1024


class TreeMemory:
    def __init__(self, pid: int):
        self.root = psutil.Process(pid)
        self.peak = 0
        self.last = 0
        self.started = time.perf_counter()
        self.samples: list[tuple[float, int]] = []  # (seconds since launch, bytes)
        threading.Thread(target=self._sample, daemon=True).start()

    def _total(self) -> int:
        try:
            procs = [self.root, *self.root.children(recursive=True)]
        except psutil.Error:
            return 0
        total = 0
        for p in procs:
            try:
                total += p.memory_info().rss
            except psutil.Error:
                pass
        return total

    def _sample(self) -> None:
        while True:
            try:
                if not self.root.is_running() or self.root.status() == psutil.STATUS_ZOMBIE:
                    return
            except psutil.Error:
                return
            now = self._total()
            if now:
                self.last = now
                self.peak = max(self.peak, now)
                self.samples.append((time.perf_counter() - self.started, now))
            time.sleep(0.1)


    def at(self, seconds: float) -> int:
        """The reading closest to `seconds` after launch."""
        if not self.samples:
            return 0
        return min(self.samples, key=lambda s: abs(s[0] - seconds))[1]


def wait_for(path: Path, started: float, limit: float = 60) -> float | None:
    while time.perf_counter() - started < limit:
        if path.exists() and path.stat().st_size > 0:
            return time.perf_counter() - started
        time.sleep(0.02)
    return None


def today_time() -> float | None:
    out = TMP / "joblens_measure_smoke.json"
    out.unlink(missing_ok=True)
    started = time.perf_counter()
    proc = subprocess.Popen([str(PYTHON), "-m", "desktop_web", "--smoke", str(out)], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    took = wait_for(out, started)
    proc.wait(timeout=60)
    return took


def today_memory(ready_s: float) -> tuple[int, int]:
    out = TMP / "joblens_measure_mem.json"
    shot = TMP / "joblens_measure_mem.png"
    out.unlink(missing_ok=True)
    proc = subprocess.Popen([str(PYTHON), "-m", "desktop_web", "--smoke", str(out), "--screenshot", str(shot)], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    mem = TreeMemory(proc.pid)
    proc.wait(timeout=60)
    time.sleep(0.2)
    # one second after ready (ready time from the timing runs: the same start)
    return mem.at(ready_s + 1.0), mem.peak


def tauri_run() -> tuple[float | None, dict, int, int]:
    out = SPIKE / "timing.json"
    out.unlink(missing_ok=True)
    started = time.perf_counter()
    proc = subprocess.Popen([str(TAURI_EXE)], cwd=ROOT, env={**os.environ, "JOBLENS_SPIKE_MEASURE": "1"},
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    mem = TreeMemory(proc.pid)
    took = wait_for(out, started)
    inside = json.loads(out.read_text()) if took else {}
    proc.wait(timeout=60)
    time.sleep(0.2)
    return took, inside, mem.at((took or 0) + 1.0), mem.peak


def main() -> int:
    runs = int(sys.argv[1]) if len(sys.argv) > 1 else 3
    if not TAURI_EXE.exists():
        print("Build the spike first: cd spikes/18_tauri && npx tauri build")
        return 1
    # one warm-up of each: the first start after a build reads everything from disk
    today_time()
    tauri_run()
    t_today, t_tauri, inside, m_today, m_tauri = [], [], [], [], []
    for _ in range(runs):  # alternate, so a busy moment hits both alike
        t_today.append(today_time())
        took, t, last, peak = tauri_run()
        t_tauri.append(took)
        inside.append(t)
        m_tauri.append((last, peak))
        m_today.append(today_memory(t_today[-1] or 2.0))
    ok = lambda xs: [x for x in xs if x is not None]
    med = lambda xs: round(statistics.median(ok(xs)), 2) if ok(xs) else None
    mb = lambda pairs, i: round(statistics.median(p[i] for p in pairs) / MB)
    print(json.dumps({
        "runs": runs,
        "ready_s": {"today": [round(x, 2) for x in ok(t_today)], "tauri": [round(x, 2) for x in ok(t_tauri)]},
        "ready_median_s": {"today": med(t_today), "tauri": med(t_tauri)},
        "memory_median_mb": {
            "today": {"after_ready": mb(m_today, 0), "peak": mb(m_today, 1)},
            "tauri": {"after_ready": mb(m_tauri, 0), "peak": mb(m_tauri, 1)},
        },
        "tauri_inside_ms": inside,
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
