# JobLens's window, in Rust (Tauri 2)

Version 3 (decisions E2, E6): **Rust shows, Python decides.** This program
opens the window with the built UI and starts JobLens's engine beside it
(`desktop_web/engine.py`: the agent and the same `Api` the old pywebview
window used). They talk over one pipe; the protocol is described at the top
of `desktop_web/engine.py`.

| | Where |
|---|---|
| The window, the pipe, requests from the engine | `src/main.rs` |
| Window size, the UI folder, the icon | `tauri.conf.json` |
| The engine (Python) | `desktop_web/engine.py`, tests in `tests/test_engine.py` |
| Start-up work shared with the old window | `desktop_web/startup.py` |
| The page's side of the bridge | `frontend/src/bridge/bridge.ts` (`tauriApi`) |

Moving step by step (plan, Phase 18d): 18d1 the window and the engine;
18d2 file dialogs; 18d3 the tray; 18d4 the quick-analyze box; 18d5 one copy
at a time, Start with Windows, Windows shutdown; 18d6 packaging; 18d7 the
real update test. Until 18d6 the installed JobLens is still the pywebview one.

## Build and run from source

Needs Rust (`%USERPROFILE%\.cargo\bin`), the Visual Studio C++ build tools,
Node, and a built UI (`cd frontend; npm run build`).

```bash
cd desktop_tauri
npm ci                                            # the Tauri command-line tool
export PATH="$USERPROFILE/.cargo/bin:$PATH" CARGO_BUILD_JOBS=2
npx tauri build                                   # target/release/joblens.exe
./target/release/joblens.exe                      # runs the engine with ../.venv's Python

# smoke test: the page answers, a report (and a picture) is written, the window closes
JOBLENS_SMOKE=smoke.json JOBLENS_SMOKE_SHOT=shot.png ./target/release/joblens.exe
```

`CARGO_BUILD_JOBS=2` keeps the build's memory down (2-3 GB the first time).
From source the program finds the engine through the repo it was built in;
`JOBLENS_PYTHON` picks another Python.
