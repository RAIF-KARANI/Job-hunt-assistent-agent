# Progress Log — JobLens version 2

What was built in each version-2 step, what went wrong, and what it
teaches. Plan: [plan-version-2.md](plan-version-2.md) · Decisions:
[decisions-version-2.md](decisions-version-2.md)

| Step | Status | Result |
|---|---|---|
| 12a Spike | ✅ | pywebview + WebView2 + three.js works; 134 MB build; 3D capped/paused ([results](spike-12a-results-version-2.md)) |
| 12b Bridge | ✅ | `desktop_web/` runner + API, 20 tests, real agent driven end to end |
| 12c Scaffold + shell | ✅ | React + TS + Vite in `frontend/`, design tokens (dark + light, all AA), sidebar shell in the real window |

---

## 12b — Bridge between the page and the agent ✅ (30 Oct 2026)

### Goal
The Python side of the new UI, before any React exists: everything the
page will call, and every event it will receive. Testable with no window
and no LLM.

### What was done
- **`desktop_web/runner.py` — `AgentRunner`**: the Qt-free version of
  `desktop/agent_worker.py`.
  - Runs the graph on a background thread and reports **events** (plain
    JSON dicts):

    | Event | Fields |
    |---|---|
    | `busy` | `busy` |
    | `log` | `text` |
    | `paused` | `kind` (`review` / `paste_posting`), `payload`, `summary` |
    | `finished` | `saved_path`, `job_id`, `decision`, `suggested_rating` |
    | `failed` | `error` |

  - **One run at a time**, guarded by a lock: two quick clicks can't start
    two runs.
  - **Answers are checked before resuming.** The decision must be
    approve / edit / reject; an approved note can't be empty; an edit needs
    feedback; pasted text only when the agent asked for it.
  - `last_pause` lets a reloaded page show the waiting review again.
  - The suggested cover-note rating (Phase 11c) comes with `finished`.
- **`desktop_web/bridge.py` — `Api`**: what the page calls through
  `window.pywebview.api`:

  | Area | Calls |
  |---|---|
  | App | `app_info`, `llm_status` |
  | Agent run | `start_run`, `resume`, `paste_text`, `run_state` |
  | Feedback | `save_feedback`, `feedback_options` |
  | Tracker | `list_jobs`, `get_job`, `set_status`, `statuses` |
  | Settings | `get_settings`, `save_settings`, `set_api_key` |

  - Everything returns JSON (Pydantic → dict).
  - Errors become rejected JS promises.
- **Security:**
  - The API key is **write-only**: the page only learns *whether* one is set.
  - Settings writes go through an **allow-list** (`UI_3D` from D14 is on it).
  - The Ollama URL can't be changed from the page.
- `requirements.txt`: `pywebview>=6.0`.
- `tests/test_bridge.py`: **20 tests** with a tiny real LangGraph graph that
  pauses exactly like the agent: review → approve / edit / reject, the
  paste flow, bad answers, busy guard, crash → `failed`, run log row,
  tracker JSON, API key never leaked, settings allow-list, feedback
  validation. **112 tests in total.**

### Problems hit
1. **Thread id vs. context.** The first version routed print() → log by
   thread id. LangGraph runs parallel work on pool threads that copy the
   caller's *context*, so a `ContextVar` follows the run, where a thread id
   would lose those lines. A test proves a pool thread's print still arrives.
2. **Endless loop, found only by the real-agent run.** If anything prints
   *while an event is being delivered* (a logger, pywebview, or the test's
   own sink), that print became a new log event, which was delivered,
   printed again, and so on: a `RecursionError` in the agent thread. Fix:
   `emit()` delivers with log capture off. A regression test now prints
   from inside the sink.

### Real check (no window)
The real agent (`job_agent.graph`) was driven through `Api` on an already
tracked job:
- it reused the saved analysis and streamed the log
- it paused for review after **25 s** (revision 1, 135 words, full summary)
- reject → `finished` with nothing saved, suggested rating "not usable",
  clean run state

### Concepts learned
- **Events vs. calls:** the page *asks* (calls that return), Python
  *tells* (one-way events). Never the other way round (spike lesson).
- **ContextVar:** "thread-local" that also follows async tasks and
  context-copying thread pools.
- **Re-entrancy:** an output hook must never trigger itself.
- **Trust boundaries:** treat the page as less trusted than Python. It
  renders text from the web, so it gets the minimum: no secrets, and only
  allow-listed writes.

---

## 12c — Front-end scaffold and app shell ✅ (30 Oct 2026)

### Goal
The React app running inside the pywebview window, talking to the real
bridge, with the design system and the frame every screen sits in.

### What was done
- **`frontend/`: React 19.3 + TypeScript 5.9 + Vite 8.3** (D13). Versions
  are pinned and at least two weeks old. Two TS settings that matter here:
  `strict` and `noUnused*`.
  - `npm run build` type-checks, then writes static files to
    `desktop_web/web/`. That folder is git-ignored; it gets built before
    packaging.
  - `base: "./"` keeps every path relative, so the same build works from
    pywebview's local server and from the installed app.
- **Fonts are bundled** with `@fontsource`: Sora, IBM Plex Sans, IBM Plex
  Mono, only the weights in use. The app needs no internet for its look.
- **Design tokens** (`src/styles/tokens.css`):
  - type, a 4 px spacing grid, radii, motion, colors
  - **dark** (the approved concept) and **light**, chosen by
    `<html data-theme>`
  - every text color was **computed** to pass WCAG AA in both themes
    (5.2:1 to 11:1)
- **Typed bridge** (`src/bridge/`):
  - `types.ts` mirrors `bridge.py`: every API method and every event, as TypeScript types.
  - `getApi()` handles the spike-12a race: check for the API first, then
    wait for `pywebviewready`.
  - `onEvent()` subscribes to Python's events.
  - In `npm run dev` in a normal browser it falls back to **mock data**, so
    screens can be built without Python. The mock is provably absent from
    the production bundle.
- **App shell:**
  - sidebar with the 5 pages from the concept
  - the model status card shows the real `llm_status()`, and "Agent working"
    while a run is busy
  - theme switch (Match Windows / Dark / Light), saved as `UI_THEME` (added
    to the bridge allow-list)
  - skip link, `aria-current`, focus rings, reduced motion
  - narrow windows turn the sidebar into a top bar
  - pages live in the URL hash (`#/tracker`), so F5 keeps you on the same
    page; no router library needed
  - the Dashboard placeholder already shows **real tracker numbers** through the bridge
- **`desktop_web/app.py`** (`python -m desktop_web`):
  - opens the window; `--dev` loads the Vite dev server for live editing
    (F12 opens dev tools)
  - the native window starts in the theme's background color, so there's
    no white flash
  - **`--smoke out.json [--screenshot x.png]`**: opens the window, waits for
    the page to report `window.__joblens_ready`, records the bridge,
    version, theme and nav items, optionally screenshots the window, and
    closes. It seeds the packaged self-test in 12h.
- Tests: 2 for the entry point, plus `UI_THEME` in the allow-list test.
  **114 tests in total**; `npm run typecheck` is clean.

### Checked in the real window
- Smoke run with your profile: `bridge: pywebview`, dark theme, 5 nav
  items, the Dashboard shows your 7 tracked jobs and best fit 90.
- Smoke run with a temporary profile set to `UI_THEME=light`: the light
  theme renders correctly. Your settings were not touched.

### Notes
- The model card says "Checking the model..." for about 2 s, because
  `llm_status()` really takes about 2.1 s (measured). It isn't stuck.
- The title bar still shows the Python icon when run from source; the
  packaged `.exe` has the JobLens icon (12h).
- Build size: JS 227 kB (71 kB gzipped), CSS 16 kB, fonts ~0.5 MB.

### Concepts learned
- **Design tokens:** themes are data, not code.
- **Type-checked contracts across languages:** TS types mirror the Python API.
- **Dev/prod split:** mock data only in development, removed from the
  production build by dead-code elimination.
- **Smoke tests:** the cheapest test that the whole stack is wired together.
