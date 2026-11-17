# Phase 18 spike: JobLens's window in Rust (Tauri 2)

The question (decision E2): would moving JobLens's *window* from Python
(pywebview) to Rust (Tauri) make the app clearly smaller or faster? The
agent stays Python either way. Results: `docs/version-3/progress-version-3.md`, 18a/18b.

## What is here

| File | What it does |
|---|---|
| `src-tauri/src/main.rs` | The Rust program: opens the window with the built UI, starts the Python side, passes the page's calls to it and its events back |
| `sidecar.py` | The Python side: today's `desktop_web.bridge.Api`, unchanged, behind a pipe (one JSON object per line) |
| `src-tauri/tauri.conf.json` | Window size, the UI folder (`desktop_web/web`), the installer |
| `measure.py` | Time until your data shows, and memory: today's window vs this one |
| `size.py` | How big a Tauri JobLens would be, compressed, vs v1.2.0 |
| `frontend/src/bridge/bridge.ts` (in the app) | 18a: inside Tauri, the page talks to `call(...)` instead of pywebview. Nothing changes in the normal app |

Not in the spike (they belong to the window, so they would be rewritten in
Rust if adopted, step 18d): the tray, the global shortcut, the updater,
native file dialogs (Add PDFs...), Start with Windows, one copy at a time.

## Build and run

Needs Rust (`rustup`, installed in `%USERPROFILE%\.cargo\bin`, not on PATH),
the Visual Studio C++ build tools, Node, and a built UI (`cd frontend; npm run build`).

```bash
cd spikes/18_tauri
npm ci                                   # the Tauri command-line tool
export PATH="$USERPROFILE/.cargo/bin:$PATH" CARGO_BUILD_JOBS=2
npx tauri build                          # first time: ~10 min, 2-3 GB of memory
src-tauri/target/release/joblens-spike.exe

# measurements (from the repo root)
.venv/Scripts/python spikes/18_tauri/measure.py 5
.venv/Scripts/python spikes/18_tauri/size.py
```

`CARGO_BUILD_JOBS=2` keeps the build's memory down on a 16 GB PC.
