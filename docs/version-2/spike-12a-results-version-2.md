# Spike 12a results — pywebview + WebView2 + three.js

**Date:** 29 Oct 2026 · **Code:** `spikes/12a_webview/` (throwaway) ·
**PC:** RTX 4060 Laptop 8 GB, qwen3:8b in Ollama, WebView2 156
**Question:** can JobLens' UI be a web page (with three.js) in a native
window, without hurting size, speed or the local LLM?
**Answer: yes.** D7 is confirmed, with one new rule for 3D (D12).

## What the spike does
`spike.py` opens a pywebview window (Edge WebView2) showing a three.js
"job galaxy". It imports the real agent (`job_agent.graph`, `tracker`) in a
background thread, measures itself, writes `results_*.json` and closes. It
was run from source and as a PyInstaller build, with Qt and matplotlib
excluded and everything else the same as `joblens.spec`.

## Results

| Measurement | Source run | Frozen build | Today's Qt app (v0.3.0) |
|---|---|---|---|
| App folder | — | **134 MB** | 230 MB |
| Zip (≈ installer size) | — | **69 MB** | 111 MB zip / 81 MB installer |
| Window ready after start | 1.9 s | 2.7 s | not measured |
| Agent loaded after start (background) | 2.9 s | 2.3 s | — |
| JS → Python call, round trip | 1.15 ms median | 1.5 ms (max 10) | — |
| Python → JS event (agent log line) | < 1 ms (max 3) | < 1 ms (max 15), 200/200 arrived | — |
| three.js FPS (GPU otherwise idle) | 143 | 144 | — |
| GPU used by WebView2 | NVIDIA RTX 4060 (ANGLE / D3D11) | same | — |
| Memory, app + WebView2 (7 processes) | 505 MB | 510 MB | not measured |

### Does the 3D scene slow the local LLM? Yes, unless it is capped or paused
qwen3:8b, 256 tokens per run, 3 interleaved rounds per setting, median tokens/s:

| 3D scene | Source run | Frozen build | Slowdown |
|---|---|---|---|
| Paused | 18.6 | 24.2 | — |
| On, uncapped (~144 FPS) | 12.0 | 18.1 | **−25 to −35 %** |
| On, capped at 30 FPS | 17.3 | 22.9 | **−5 to −7 %** |

Absolute speeds vary between sessions (37 → 18 tokens/s) because other apps
keep the GPU busy: Wallpaper Engine, Chrome, Docker Desktop, the NVIDIA
overlay, and others, 34–98 % GPU use with JobLens idle. The interleaved
order makes the comparison fair anyway, and both runs agree.

## Problems hit (and fixes for the real build)
1. **`pywebviewready` fired before the page listened for it**, so the page
   never told Python it was ready and the first run hung. Fix: check whether
   `window.pywebview.api` already exists, and only otherwise wait for the
   event. The real bridge must do this too.
2. **`evaluate_js` doesn't wait for JS promises** (it returns a stub). Fix:
   the page stores the result and Python polls for it. In the real app,
   prefer JS calling Python, which returns properly.
3. A run with the window covered drew **0 FPS**: WebView2 stops drawing a
   hidden window. That's good: the scene pauses itself when nobody can see it.
4. Leftover dependencies still in the bundle: pandas + numpy (~40 MB, only
   for `monitoring.py`) and PIL (13 MB). Removing them is a size win for later.

## Conclusions
- **D7 confirmed:** pywebview + WebView2 works frozen, is about 40 % smaller
  than the Qt build, starts in under 3 s, and the bridge is far faster
  than a UI needs.
- **New rule D12:** the 3D scene is **capped at 30 FPS** and **paused
  while the agent runs** (and whenever the window is hidden).
- The agent loads in the background while the window paints, so startup
  feels fast. Keep it that way.
- **New dependencies for 12b:** `pywebview` (with `pythonnet`), `psutil`
  (optional); `three` shipped as a local file, no CDN (the app must work offline).
