r"""Spike 12a (throwaway): can JobLens' UI be a web page in a native window?

Measures, then closes itself and writes results.json:
  - startup time (process start -> window ready, and -> agent imported)
  - JS -> Python round trip and Python -> JS event latency (the bridge)
  - three.js FPS, and which GPU WebView2 draws on
  - qwen3:8b speed (tokens/s) with the 3D scene on vs paused: does 3D slow the LLM?
  - GPU use (nvidia-smi) and memory of the app + its WebView2 processes

Run from source:   python spike.py [--out results.json]
Run frozen:        dist\JobLensSpike\JobLensSpike.exe --out results.json
"""

import time
T0 = time.perf_counter()  # before the heavy imports: startup includes them

import json
import statistics
import subprocess
import sys
import threading
from pathlib import Path

import requests
import webview

if getattr(sys, "frozen", False):
    WEB = Path(sys._MEIPASS) / "web"
else:
    WEB = Path(__file__).parent / "web"
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))  # repo root -> job_agent

OUT = Path(sys.argv[sys.argv.index("--out") + 1]) if "--out" in sys.argv else Path("results.json")
OLLAMA = "http://localhost:11434"
results: dict = {"frozen": getattr(sys, "frozen", False)}
ready = threading.Event()
agent_imported = threading.Event()


def since_start() -> float:
    return round(time.perf_counter() - T0, 2)


def import_agent() -> None:
    """The real app imports the agent in the background, after the window shows."""
    t = time.perf_counter()
    import job_agent.graph  # noqa: F401  (pulls in langchain, langgraph, ...)
    from job_agent import tracker
    results["agent_import_s"] = round(time.perf_counter() - t, 2)
    results["agent_ready_after_start_s"] = since_start()
    try:
        results["tracker_jobs"] = len(tracker.list_jobs())
    except Exception as e:  # no data folder in a frozen temp run
        results["tracker_jobs"] = f"n/a ({e.__class__.__name__})"
    agent_imported.set()


class Api:
    """Everything JS may call: window.pywebview.api.<name>(...)."""

    def echo(self, x):
        return x

    def ready(self, info):
        results["window_ready_after_start_s"] = since_start()
        rt = info.pop("round_trips_ms")
        results["js_to_python_round_trip_ms"] = {"median": round(statistics.median(rt), 2),
                                                 "max": round(max(rt), 2)}
        results["webview"] = info
        ready.set()


def js(code: str):
    return window.evaluate_js(code)


def emit(kind: str, text: str = "") -> None:
    """Python -> JS, the way agent_worker's signals will travel."""
    ev = {"type": kind, "text": text, "sent_ms": time.time() * 1000}
    js(f"window.onAgentEvent({json.dumps(ev)})")


def gpu_sample() -> dict:
    out = subprocess.run(["nvidia-smi", "--query-gpu=utilization.gpu,memory.used",
                          "--format=csv,noheader,nounits"], capture_output=True, text=True,
                         creationflags=subprocess.CREATE_NO_WINDOW).stdout.strip()
    util, mem = (int(v) for v in out.split(","))
    return {"util": util, "mem_mb": mem}


def generate(tokens: int = 256) -> dict:
    """One qwen3:8b generation; tokens/s from Ollama's own timings."""
    samples, stop = [], threading.Event()

    def sampler():
        while not stop.is_set():
            samples.append(gpu_sample())
            time.sleep(0.5)

    th = threading.Thread(target=sampler, daemon=True)
    th.start()
    r = requests.post(f"{OLLAMA}/api/generate", timeout=600, json={
        "model": "qwen3:8b", "stream": False, "think": False,
        "prompt": "Explain in detail how a job applicant should research a company before an interview.",
        "options": {"num_predict": tokens, "num_ctx": 16384, "temperature": 0.2, "seed": 1}}).json()
    stop.set()
    th.join()
    return {"tokens_per_s": round(r["eval_count"] / (r["eval_duration"] / 1e9), 1),
            "tokens": r["eval_count"],
            "gpu_util_avg": round(statistics.mean(s["util"] for s in samples), 1) if samples else None}


def memory_mb() -> dict:
    """Working set of this process + WebView2 helpers (msedgewebview2.exe children)."""
    try:
        import psutil
    except ImportError:
        return {"note": "psutil not installed"}
    me = psutil.Process()
    procs = [me] + me.children(recursive=True)
    total = sum(p.memory_info().rss for p in procs if p.is_running())
    return {"python_mb": round(me.memory_info().rss / 2**20), "total_mb": round(total / 2**20),
            "processes": len(procs)}


def js_await(expr: str, timeout: float = 30):
    """evaluate_js doesn't wait for promises: park the result in a global and poll."""
    js(f"window.__r = undefined; Promise.resolve({expr}).then(v => window.__r = v)")
    end = time.time() + timeout
    while time.time() < end:
        v = js("window.__r")
        if v is not None:
            return v
        time.sleep(0.1)
    raise TimeoutError(expr)


def log(msg: str) -> None:
    print(f"[{since_start():7.2f}s] {msg}", flush=True)


def measure() -> None:
    try:
        _measure()
    except Exception as e:  # a spike must never hang: record, close
        results["error"] = repr(e)
        OUT.write_text(json.dumps(results, indent=2))
        log(f"ERROR {e!r}")
        window.destroy()


def _measure() -> None:
    if not ready.wait(60):
        raise TimeoutError("JS never called api.ready()")
    log("window ready")
    emit("step", "importing the agent")
    if not agent_imported.wait(120):
        raise TimeoutError("agent import took > 120 s")
    log("agent imported")

    log("measuring event latency")
    emit("step", "event latency")
    js("window.takeEventLatencies()")
    for i in range(200):
        emit("log", f"[fit] fake log line {i}")
    time.sleep(1)
    lat = js("window.takeEventLatencies()") or [0]
    results["python_to_js_event_ms"] = {"median": statistics.median(lat), "max": max(lat), "n": len(lat)}

    log("measuring FPS")
    emit("step", "FPS")
    results["fps_idle_gpu"] = round(js_await("window.measureFps(5000)"), 1)
    results["gpu_scene_on_idle"] = gpu_sample()
    js("window.setScene(false)")
    time.sleep(2)
    results["gpu_scene_paused_idle"] = gpu_sample()
    results["memory"] = memory_mb()

    try:
        emit("step", "LLM warm-up")
        generate(32)
        # (scene on?, FPS cap) - interleaved 3x so background noise hits all equally
        conditions = {"paused": (False, 0), "on_uncapped": (True, 0), "on_30fps": (True, 30)}
        runs = []
        for rnd in range(int(__import__("os").environ.get("SPIKE_ROUNDS", "3"))):
            for name, (on, cap) in conditions.items():
                js(f"window.setFpsCap({cap}); window.setScene({'true' if on else 'false'})")
                time.sleep(1)
                log(f"LLM round {rnd + 1}: {name}")
                emit("step", f"LLM round {rnd + 1}: {name}")
                f0, t0 = js("window.frameCount()"), time.perf_counter()
                g = generate()
                g["scene"] = name
                if on:  # frames drawn WHILE the LLM was generating
                    g["fps_during"] = round((js("window.frameCount()") - f0) / (time.perf_counter() - t0), 1)
                runs.append(g)
        results["llm_runs"] = runs
        med = {n: statistics.median(r["tokens_per_s"] for r in runs if r["scene"] == n) for n in conditions}
        results["llm_median_tokens_per_s"] = med
        results["llm_slowdown_pct"] = {n: round((1 - med[n] / med["paused"]) * 100, 1)
                                       for n in ("on_uncapped", "on_30fps")}
    except requests.RequestException as e:
        results["llm_runs"] = f"Ollama not reachable: {e}"

    OUT.write_text(json.dumps(results, indent=2))
    emit("finished", f"results written to {OUT}")
    time.sleep(1)
    window.destroy()


if __name__ == "__main__":
    window = webview.create_window("JobLens spike 12a", str(WEB / "index.html"), js_api=Api(),
                                   width=1280, height=800, background_color="#0A0F1C")
    threading.Thread(target=import_agent, daemon=True).start()
    webview.start(measure, gui="edgechromium")
    print(json.dumps(results, indent=2))
