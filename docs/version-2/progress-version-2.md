# Progress Log — JobLens version 2

What was built in each version-2 step, what went wrong, and what it
teaches. Plan: [plan-version-2.md](plan-version-2.md) · Decisions:
[decisions-version-2.md](decisions-version-2.md)

| Step | Status | Result |
|---|---|---|
| 12a Spike | ✅ | pywebview + WebView2 + three.js works; 134 MB build; 3D capped/paused ([results](spike-12a-results-version-2.md)) |
| 12b Bridge | ✅ | `desktop_web/` runner + API, 20 tests, real agent driven end to end |
| 12c Scaffold + shell | ✅ | React + TS + Vite in `frontend/`, design tokens (dark + light, all AA), sidebar shell in the real window |
| 12d Analyze | ✅ | steps timeline, live log, review / rewrite / reject, paste fallback, ratings; a real qwen3:8b run approved from the new UI |
| 12e Tracker | ✅ | board with drag + undo, sortable list, details sheet (evidence, research, copy note); status changes saved to `jobs.db` |

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

---

## 12d — Analyze screen ✅ (30 Oct 2026)

### Goal
Paste a job link, watch the agent work step by step, then approve, rewrite
or reject the cover note, all in the new window. Done when a full real run
is approved from the new UI.

### What was done
- **Progress as events (D15).** `runner.py` reads the agent's printed
  lines once and sends structured events. The page never parses log text.

  | Event | When |
  |---|---|
  | `started` | a run begins (`run_id`, `url`) |
  | `step` | `[n/5] ...` lines; step 5 from `[draft] writing draft #n` |
  | `step_detail` | `-> ...`, `! ...` and `- scoring ...` lines; step 2 shows `best: cv · fit 86` |
  | `reused` | the job was already tracked, so steps 1-4 are skipped |

  Every event except `log`/`busy` carries `at` (time), for step durations.
- **Replay after a reload (D16).** The runner keeps the run's events;
  `run_state()` returns them and the page replays them through the same
  `reduce()` that handles live events.
- **`frontend/src/analyze/`:**
  - `runStore.ts`: the run outside React (survives page switches); one pure
    `reduce(view, event)` function
  - `Steps.tsx`: the five steps with status, live timer and detail
  - `LiveLog.tsx`: raw log; follows new lines unless you scrolled up
  - `ReviewPanel.tsx`: warnings about unverified numbers, "Why fit 86"
    (proven requirements with resume quotes, gaps), editable draft, word
    count, rewrite notes, approve, reject with a second confirm
  - `PastePanel.tsx`: the paste-the-text fallback (200+ characters)
  - `ResultPanel.tsx`: saved / rejected, then "How did JobLens do?" with the
    cover-note rating pre-filled (Phase 11c)
- **Shared controls** (`styles/controls.css`): buttons, inputs, segmented
  radios, notices, badges, used by the next screens too.
- **Sidebar:** "Agent working" / "Waiting for you", plus a dot on the
  Analyze item when you're on another page.
- **Dev mock:** a scripted fake run, so `npm run dev` in a browser shows
  every state (a link with "linkedin" shows the paste flow). Still absent
  from the production build.
- Tests: 3 new bridge tests (progress events, "the parsed lines still exist
  in the agent", replay). **117 tests in total**; typecheck clean.

### Checked in the real window
A driver script clicked through the real pywebview window on a
temporary profile (your data untouched):
- **Stand-in agent** (same prints, seconds long): run → review → rewrite
  (draft 2, warning gone) → switch to Tracker and back (review still
  there) → edit → approve → rating saved; then the paste flow, **reloaded
  mid-pause** (paste panel came back), paste → review → reject (confirm) →
  "not usable" pre-filled; light theme; narrow window.
- **Real agent, qwen3:8b, a Hugging Face posting saved as a text file:**
  review after **163 s** (read 22 s, resumes 1m 14s, research 52 s with 6
  verified sources), fit 81 with evidence quotes, 161-word draft. Approved
  with an edit → cover note file saved, suggested rating "needed edits",
  rating saved.

### Problems hit
1. **Step 2 showed a paragraph.** The agent prints the verdict as an
   `->` line after `-> best:`, so it overwrote the best-resume detail.
   Fixed: step 2 shows `best: <resume> · fit <score>`; the verdict stays in
   the log (found only by the real run).
2. **The step connector crossed the circles** on pending steps: it was
   sized from the circle, not from the row. Now drawn on the row.
3. **Status buttons faded out.** "Running · 2m 41s" was a disabled primary
   button at 55 % opacity: the live timer was hard to read. Status states
   now use a readable secondary style.

### Concepts learned
- **Event sourcing in small:** the view is `events.reduce(reduce, IDLE)`,
  so live updates and replay can't disagree.
- **State outside the component tree** (`useSyncExternalStore`) for things
  that outlive a page.
- **Contract tests across a boundary:** a test that the agent still prints
  the lines the UI depends on.

---

## 12e — Tracker screen ✅ (30 Oct 2026)

### Goal
Every analyzed job as a board (drag = status change) and as a list, with
the details. Done when status changes are saved to `jobs.db`.

### What was done
- **`frontend/src/tracker/`:**
  - `Board.tsx`: six columns (D18), cards with company, role, fit chip, fit
    bar and a "when" line; HTML drag and drop; empty columns stay narrow
  - `JobList.tsx`: table sorted by fit; click a header to sort by
    company, role, fit, status or date; the status dropdown in each row
  - `JobSheet.tsx`: details in a side sheet (native `<dialog>`: focus stays
    inside, Esc closes): status, open posting, "draft a cover note", fit
    with breakdown and verdict, proven requirements with resume quotes,
    gaps, the latest approved cover note with **Copy**, the company
    research with its checked sources
  - `useJobs.ts`: loads the jobs, reloads when a run finishes; status
    changes are **optimistic** (the card moves at once and moves back if
    saving fails)
  - search across company, role, resume and status; Board/List choice
    remembered on this PC
  - **Undo** for 8 s after any status change
- **Bridge:** `open_link(url)` opens http(s) links in your browser and
  refuses anything else; the page routes **every** web link through it.
- **Tracker:** `list_jobs()` also returns `created_at`.
- **Tokens:** fit chip colors with text colors checked by calculation
  (5.4:1 to 13.3:1), and one color per status in both themes.
- Tests: `open_link` refuses `file:`, `javascript:`, a Windows path,
  `ms-settings:` and an empty host (6 cases) and opens a real link; the job
  list carries `created_at`. **123 tests in total**; typecheck clean.

### Checked in the real window
A driver script on a temporary profile with a **copy** of your `jobs.db`
(the real file's checksum was the same before and after):
- 7 cards for 7 jobs
- dragged Intel from Researched to Applied → saved as `applied` in the DB;
  Undo → back to `researched`
- details of the best job (ByteDance, 90): Copy put exactly the saved note
  on the clipboard (your clipboard was restored after); "Open posting"
  went to the browser while the window stayed on JobLens
- status changed in the sheet → DB updated and the card moved column
- search "Byte" → "1 of 7 jobs"; list sorted by fit, then by company;
  status changed in a row → DB updated; Undo worked
- "Draft another cover note" → Analyze, with the posting's link filled in
- light theme, narrow window

### Problems hit
1. **Six equal columns didn't fit** at 1440 px ("Rejected" was cut off).
   Empty columns are now narrow, and columns with jobs never shrink below
   220 px (the board scrolls sideways in a narrow window instead).
2. **"Analyzed today" after a drag and undo.** The card used the last
   status change. Now it uses when the job was added.
3. **The copy check failed, but the copy was right.** The test read the
   clipboard through PowerShell in the old Windows encoding, which turned
   the note's curly apostrophe (’) into another character. The test (and
   restoring your clipboard) now uses UTF-8.

### Notes
- `pytest` printed "1 warning" twice today and never again in 27 repeat
  runs. **Found in 12f:** a `SyntaxWarning` for `"C:\jobs\posting.txt"` in
  this step's own test (`\j` isn't a valid escape). Python only warns when
  it recompiles the file, which is why it came and went. Fixed with a raw
  string.

### Concepts learned
- **Optimistic updates** with rollback.
- **HTML drag and drop:** `dragover` must call `preventDefault()` or a drop
  is never allowed.
- **Native `<dialog>`** with `showModal()`: focus trap, Esc and backdrop.
- **Trust boundaries again:** a desktop web view must decide where links go.

---

## 12f — Dashboard ✅ (30 Oct 2026)

### Goal
Key numbers, the job galaxy at the three 3D levels (D14), and 2D cards from
the run log. Done when the numbers match the old Dashboard and every level
shows the same data.

### What was done
- **Bridge:** `dashboard(days)` returns the run-log numbers (KPIs,
  decisions, time per step, safety nets, evidence pass rate) for 7 days, 30
  days or all time, from the same `monitoring.py` functions as the Qt
  Dashboard.
- **`frontend/src/dashboard/`:**
  - `Dashboard.tsx`:
    - 4 tiles: jobs tracked, median full run, evidence verified, cover notes approved
    - the time range (remembered on this PC) and a "New analysis" button
    - reloads when a run finishes
  - `galaxy/layout.ts`: one placement for all levels (distance = fit, angle
    from the job id, so a job doesn't move when others are added)
  - `galaxy/scene.ts`: the three.js scene (D19):
    - stars, the fit rings, "You" in the middle, one glowing dot per job, a selection ring
    - at most 30 FPS
    - "still" draws only when something changes
    - colors follow the theme
    - frees the GPU when you leave the page
  - `galaxy/Galaxy3D.tsx`: loaded on demand; the job labels are buttons
    that follow the dots
  - `galaxy/OrbitMap.tsx`: the flat map for level "off" (SVG)
  - `galaxy/Galaxy.tsx`: picks the level:
    - reduce motion (Windows setting): animated acts as still
    - an agent run pauses the spin
    - WebGL failure: the flat map
  - `SelectedJob.tsx`: the picked job: fit, proven skills, gaps, what the
    company does; "Open details" (the Tracker's sheet) and "Draft a cover note"
  - `Charts.tsx`: time per step, safety nets (links to Evals), where your
    applications are; every bar has its value written beside it
- **`monitoring.py`:** time per step uses `draft` instead of `cover_note` (D19).
- three.js 0.186.1 (exact version). The page bundle is unchanged in size;
  three.js is its own 568 kB file.
- Tests: the bridge numbers are equal to `monitoring.py`'s, the time
  range, an empty run log, bad ranges refused (0, −5, `True`), and
  `draft` (not `cover_note`) in time per step. **129 tests**, no warnings.

### Checked in the real window
A driver script on a temporary profile with a **copy** of your `jobs.db`
(the real file's checksum was the same before and after):
- 7 jobs in the galaxy for 7 in the DB; tiles = Python's numbers (5 runs,
  median 2m 54s, 62% evidence verified, 3 approved of 4)
- **animated: 30.0 FPS; 0 FPS while the agent runs**, 30 again after
- still: 0 frames when idle, redraws on zoom
- off: **no canvas, three.js never loaded**, the same 7 jobs on the flat map
- WebGL made to fail → notice + flat map with all 7 jobs
- 20 switches between Dashboard and Tracker → still exactly one canvas,
  no fallback (GPU contexts are released)
- picked Intel (fit 33) → panel and `aria-pressed` updated; "Open
  details" opened the sheet
- the time ranges; Tab starts at the best fit (ByteDance, 90)
- dark and light theme, narrow window

### Problems hit
1. **"Cover note: <1 s"** with real data. The real drafting time is
   recorded under `draft` (16 s on average). Fixed in `monitoring.py` (D19).
2. **21 FPS instead of 30.** The 30 FPS limit waited for the next screen
   refresh after every frame. My first fix let some frames through
   immediately (36 FPS right after a run). Now it uses a fixed 33.3 ms
   schedule: exactly 30.0, never more.
3. **Good jobs crowded in the middle** and their labels overlapped: the
   camera was too far back and the scale used 0–100. The camera is now
   closer and higher, and fit 100 → 20 fills the radius.
4. **Real requirements are sentences**, so six chips made the panel very
   tall. Now 4 chips, 2 lines each, with the full text on hover and in the
   details sheet.
5. Solved the "1 warning" from 12e (see the 12e notes).

### Concepts learned
- **Render on demand** vs a frame loop; a frame-rate cap with a fixed
  schedule.
- **Projecting 3D points to the screen** (`Vector3.project`) to put HTML
  labels on a WebGL scene.
- **Code splitting** with `React.lazy`: a heavy library loads only when
  a feature needs it.
- **GPU resources are manual:** dispose geometries, materials and textures,
  and release the WebGL context.

---

## 12f2 — Evals screen ✅ (30 Oct 2026)

### Goal
How well the agent did (D9), from the run log, with Langfuse/LangSmith
status and trace links. Done when the numbers match run-log queries in
tests.

### What was done
- **`monitoring.py`:** `build_evals()` (pure) + `local_evals(model)`:
  - the key numbers
  - the pass rate run by run
  - your ratings
  - the 7 safety-net checks
  - time and output tokens per step
  - correlations
  - every model compared
  - recent runs with job names

  The research agent's own LLM calls (logged as `agent`) count toward "Research company".
- **Run log:** new `runs.tracing` column (which tracer was on for that
  run); old databases get it automatically.
- **Bridge:** `evals(model)` and `tracing_status()` (D20).
- **`frontend/src/evals/`:**
  - `Evals.tsx`:
    - model filter
    - tracer status chips
    - 5 tiles: evidence pass rate with its trend, notes approved, agent time, tokens, tool failures
    - tables: safety nets, where the time goes, models compared, recent runs (with trace links)
  - `PassRateChart.tsx`: line chart drawn at the real width (text stays
    12 px), hover tooltip, a hidden table for screen readers
  - `Ratings.tsx`: one stacked bar per question; the legend names every part
- **Tokens:** three rating colors, checked with the dataviz palette
  validator in both themes (D20).
- Tests:
  - every number equals a direct SQL query on a seeded run log (two models)
  - the model filter; recent runs (order, results, trace)
  - an empty run log; the trend math
  - tracing status: off, Langfuse running or unreachable, LangSmith without a key
  - the recorder stores the tracer; old databases get the column

  **138 tests**, no warnings.

### Checked in the real window
On a **copy** of your `jobs.db`, plus one made-up API run (traced in
Langfuse) added to the copy; the real file's checksum was unchanged:
- tiles = Python's numbers (69% evidence, 4 of 5 approved, 2m 26s,
  18.4k tokens, 1 of 9 searches failed)
- model list: qwen3:8b (local), claude-haiku-5-5 (API); choosing the API
  model changed every number to that run's, and "Models compared" still
  listed both with the chosen one highlighted
- trend points, check rows, step rows and recent rows all match Python
- hovering the last point → "90% of claims held up" with the date
- the Langfuse link opened `…/project/demo-project/sessions/api-demo` in
  the browser; the window stayed on Evals
- light theme; narrow window with no sideways scrolling

### Problems hit
1. **Blank page with real data.** Runs from before this step have no
   `tracing` value; pandas makes that `NaN`, and `NaN or "off"` is still
   `NaN` (NaN counts as true). Python's JSON writes `NaN`, which JavaScript
   can't parse, so the answer never arrived. Fixed. The tests now reject
   NaN like the page does (`allow_nan=False`); I confirmed the old code
   fails them.
2. **No bars in "Where the time goes"**: an inline span has no width in a
   table cell.
3. **Sideways scrolling in a narrow window**: the chart's svg kept its old
   pixel width, so the card couldn't shrink. Fixed with
   `contain: inline-size` (not `overflow: hidden`, which would have cut
   off the tooltip).
4. A card alone in the page column took its flex size as a height (empty
   space under "Models compared").
5. The concept's blue and violet rating colors failed the palette check.

### Concepts learned
- **NaN is truthy** in Python and is not valid JSON: check
  `allow_nan=False` at the boundary.
- **Correlation** as a quick explanation of where time goes.
- **CSS containment** (`contain: inline-size`) to break a
  content-sizes-container loop.

---

## 12g — Settings and Setup wizard ✅ (30 Oct 2026)

### Goal
Port Settings and the first-run wizard, and add the "Look and feel" step
plus Settings → Appearance (3D level, D14). Done when the first-run flow
works on a clean profile and the recommendation rule is unit-tested.

### What was done
- **`system_check.recommend_3d()`**: the D14 rule, pure (D21).
- **Bridge:**
  - resumes: `list_resumes`, `add_resumes` (native file dialog, copies),
    `remove_resume` (file name only), `open_data_folder`
  - setup: `system_check`, `ollama_status` (starts Ollama if it's stopped),
    `install_ollama` and `pull_model` (stream `setup_progress` events, one
    at a time), `test_api_key` (saves nothing)
  - `app_info().setup_needed`
- **Run log store:** unknown event types are ignored. They used to make it
  return nothing, which would have broken Analyze on the first download event.
- **`frontend/src/settings/`:**
  - `Settings.tsx`:
    - AI model (provider, model with the installed ones suggested, API key, check)
    - resumes
    - appearance (theme, 3D level with the recommendation)
    - options (evidence double-check, tracing)
  - shared with the wizard:
    - `ResumeList`
    - `LevelPicker` (also checks WebGL)
    - `LocalModelSetup` (PC check, model choice, Ollama install, download progress)
    - `useSetupProgress`
- **`frontend/src/setup/SetupWizard.tsx`:** 6 steps:
  - a step list
  - focus moves to each step's title
  - Next stays locked until the step is complete, with a line saying why
- The Placeholder screen is gone: every page is real now.
- Tests:
  - the 3D level for 8 kinds of PC
  - resumes: copy / list / remove; Cancel adds nothing; 7 bad names refused
  - when setup is needed
  - download progress, a failed download, one download at a time
  - no winget → the download page
  - the key test (wrong, right, nothing saved)
  - the PC check's 3D advice

  **162 tests**.

### Checked in the real window
- **Wizard, on an empty profile** (the real PC check and Ollama; the
  download, the Claude call and the file dialog were stand-ins):
  - opened by itself
  - the API path: a wrong key gave "401 … invalid x-api-key", a right key passed
  - back to local: "16 GB RAM · RTX 4060 (8 GB). Recommended: qwen3:8b";
    models already on this PC were marked so; "Ollama is installed and
    running. Nothing to install."
  - picked qwen3:4b → download progress (30 %, "0.78 GB of 2.60 GB") →
    "qwen3:4b downloaded." and Next unlocked
  - resumes: Next locked until one was added
  - Look and feel: "still" pre-selected, with the reason
  - Finish → Analyze; the profile's `.env` got exactly `LLM_PROVIDER`,
    `LLM_MODEL`, `UI_3D=still`, `SETUP_DONE=true`
- **Settings, on copies of your database and resumes:**
  - no wizard for an existing user
  - your 2 resumes listed; add (copied, original kept) and remove (with the confirm)
  - local check: "Ollama is running and 'qwen3:8b' is installed"
  - Claude with a wrong key: "✕ 401 … invalid x-api-key", and the key
    never appears in the page
  - 3D "off" → the Dashboard showed the flat map at once; "animated" → 3D again
  - evidence check and tracing saved
  - light theme; narrow window
- Your real `jobs.db`, `.env` and resumes were unchanged.

### Problems hit
1. **A wrong Claude key passed "Check connection"**: the quick check only
   looks for a key. Settings now makes a real 5-token call (D21).
2. **"isn't downloaded yet" flashed after a finished download**, and
   "5.2 GB download" showed for installed models before Ollama answered.
   The page now refreshes before leaving the busy state, and shows sizes
   only once it knows.
3. **The run store had no `default` case**, so any new event type would
   have broken the Analyze screen.
4. A backslash in a docstring example (`..\x.pdf`) was an invalid escape:
   the same bug as in 12e.

### Concepts learned
- **Long-running bridge calls with progress events**: pywebview runs each
  call on its own thread, so a blocking call can stream events while the
  page's promise waits.
- **Native dialogs from a web UI** (`create_file_dialog`).
- **Path traversal**: accept a file name, not a path.

---

## 12h — Packaging ✅ (30 Oct 2026)

### Goal
Ship the web app:
- the front-end build inside `build_installer.py`
- the WebView2 check in the installer
- the self-test ported

Done when `build_installer.py` passes and a real install and uninstall work.

### What was done
- **`scripts/build_installer.py`:**
  1. `npm ci` + `npm run build`
  2. WebView2 bootstrapper: downloaded once, signature checked
  3. PyInstaller
  4. self-test + window test of the frozen app, on a temp AppData
  5. Inno Setup

  `--test-install` adds the safe install test (D22).
- **`joblens.spec`:** starts from `desktop_web`, bundles the built UI,
  leaves out PySide6, matplotlib and PIL.
- **`desktop_web/selftest.py`** (`JobLens.exe --self-test report.txt`), ported from Qt:
  - the built UI and the separate 3D file are bundled
  - imports
  - `print()` without a console
  - the workflow builds
  - the bridge calls each screen makes return valid JSON
  - the model status
  - one real web search and one real structured LLM call
- **`desktop_web/app.py`:** `--self-test`; a WebView2 check with a Windows
  message and the download link instead of a crash.
- **`installer/joblens.iss`:** installs WebView2 if missing (same registry
  check as the app); `/DTestBuild` for the separate test build.
- **`THIRD_PARTY_NOTICES.md`:** web UI components and fonts added; Qt,
  Matplotlib and Pillow removed (not in the build any more).
- **Bug fixed before it shipped:** a windowed `.exe` has
  `sys.stdout = None`. The run-log router wrapped it, so any `print()`
  outside a run (a tracing warning, "run log not saved") would have crashed
  the app. It now discards those. There's a new test for it. **163 tests.**

### Checked
`python scripts/build_installer.py --test-install`, end to end:
- front end built; bootstrapper signed by Microsoft
- frozen app: self-test PASS (real Ollama call: "Paris"; real web search:
  5 results), window test OK
- **installer 54 MB** (Qt version: 81 MB), app folder 126 MB (Qt: 230 MB)
- silent install of the test build: registered, WebView2 found (nothing
  to install), and the **installed copy** passed the self-test and the
  window test
- silent uninstall: no files, no registry entry left
- the real JobLens 0.3.0 on this PC: same `JobLens.exe` checksum, same
  registry entry, only its own Start-menu shortcut
- the real installer (without `/DTestBuild`) builds too (not installed: see Notes)

### Problems hit
1. **`print()` in the windowed app would crash** (see above). The source
   runs never showed it, because there is always a console there.
2. **The uninstall check failed the first time, but the uninstall was
   fine.** Inno's uninstaller deletes `unins000.exe` from a temp copy of
   itself after it exits, which took more than 30 s. The check now waits
   up to 90 s; afterwards nothing was left.
3. **Twice I wrote Windows paths through a shell script and Python ate the
   backslashes** (`..\build` became a backspace character). Fixed with the
   file tools. Rule for this project: edit files with Windows paths
   directly, never through a shell heredoc.
4. Running the **source** self-test once added the new `tracing` column
   (the 12f2 migration) to the developer `data/jobs.db`. Your 5 runs and 7
   jobs are unchanged; the new app does the same on its first start.

### Notes
- **Your installed JobLens is still 0.3.0 (Qt).** The new installer would
  upgrade it in place (same AppId). That's a release decision, made after
  12i and Phase 13; the test build keeps tests away from it until then.
- The window test of a fresh profile shows the Setup wizard, so it reports
  0 sidebar links; it checks that the page and the bridge start.
- PyInstaller warns about `pycparser.lextab`/`yacctab`: harmless (pycparser
  builds those tables at runtime when needed).

### Concepts learned
- **Code signing as a supply-chain check**: verify an installer you
  download and redistribute (`Get-AuthenticodeSignature`).
- **Inno Setup preprocessor** (`#ifdef`) for two builds from one script.
- **Testing installers without harming the machine**: a separate AppId,
  a silent install into a temp folder, and before/after checks.

---

## 12i — Remove the Qt UI ✅ (30 Oct 2026)

### Goal
Delete the Qt UI and PySide6, and update the tests and docs. Done when
`pytest` is green and the license notice is updated.

### What was done
- **Deleted:** `desktop/` (the Qt tabs, wizard, worker thread),
  `desktop_app.py`, and the four Qt-only test files (31 tests of Qt widgets).
- **Kept by moving:**
  - the KPI tests and the recorded-run test → `test_monitoring.py`
  - `get_cover_notes` newest-first → `test_tracker_and_guardrails.py`

  They test logic the new UI still uses. Everything else they covered is
  now covered by the bridge tests and the real-window drivers.
- **`requirements.txt`:** PySide6-Essentials and matplotlib removed;
  langchain-anthropic and pillow (developer tools only) listed plainly;
  a note that Node is for building only. PySide6, shiboken6 and matplotlib
  were uninstalled from the venv, so a hidden import would fail now.
- **README:** the desktop app section is rewritten for version 2:
  - the five screens
  - the 3D levels and the "Look and feel" step
  - running from source (`python -m desktop_web`, `--dev`)
  - building with Node, `--test-install`

  Also updated: the tests, the project layout, `UI_3D` / `UI_THEME` in the
  settings table, the license line, and links to these version-2 docs.
- **Notices:** already updated in 12h (no Qt / LGPL any more).
- Comments that pointed at deleted files reworded.

### Checked
- **136 tests** pass with PySide6 and matplotlib uninstalled. 163 − 31 Qt
  tests + 4 moved ones.
- The CLI (`main.py`), the Streamlit UI (`app.py`) and the monitoring
  dashboard (`monitor.py`) still import.
- `python scripts/build_installer.py --test-install` without Qt installed:
  - self-test and window test PASS for the build and for the installed copy
  - clean uninstall
  - no Qt, matplotlib or Pillow files in the app folder
  - your real JobLens 0.3.0 and `jobs.db` unchanged
- The source app's window check on your real profile: 5 sidebar links, page ready.

---

## Phase 12 summary — the new desktop UI ✅

**What it is now:** a React + TypeScript UI in an Edge WebView2 window,
talking to the unchanged Python agent through a small bridge:
- 5 screens: Dashboard with the 3D job galaxy, Analyze, Tracker, Evals, Settings
- a Setup wizard

**Numbers** (12a spike → finished app):
- installer 81 → **54 MB**
- app folder 230 → **126 MB**
- window ready in under 3 s
- 3D capped at 30 FPS and paused while the agent works (0 FPS then)

**Decisions:** D13–D22.

**Tests:** 136 automated tests (agent, run log, bridge); every screen
checked in the real window with driver scripts on copies of the real data.

**What I'd do differently:** write files with Windows paths using the file
tools from the start (three escaping bugs came from shell heredocs). Add a
JSON `allow_nan=False` check at the bridge from day one.

**Next:** Phase 13, tray icon and auto-update. Then the v1.0.0 release:
that's when your installed 0.3.0 gets upgraded.

---

## 12j — Fixes from the first real use ✅ (30 Oct 2026)

### Goal
You installed the app and analyzed a LinkedIn job (Revolut, UAE) with 4
resumes. Step 2 ran past 8 minutes and the only way out was closing the
app, which left no trace. Done when a run can be stopped mid-step, a
closed run appears in Evals as interrupted, and each fix has tests.

### What I found first (measured, not guessed)
- **Nothing was broken: it was slow.** Each resume comparison wrote
  ~1,150 tokens at ~10 tokens/s (the 12a spike measured 18–37): 4 resumes
  × ~110 s = 7.5 min for step 2. The GPU was shared with ~30 other
  programs (Wallpaper Engine, Chrome, Steam, Docker Desktop...). Your second
  run took 26 s / 3m 25s / 59 s / 0 s.
- My first guess, a model stuck repeating itself, was **wrong for that run**:
  every answer ended normally. But nothing would have stopped one that did:
  no answer-length limit, and Claude's client default was 128,000 tokens.
- Step 5's "3m 49s" was mostly you reading the draft (writing it takes ~16 s).

### What was done
- **Answer-length cap** (`job_agent/llm.py`, D23): 4,096 tokens per call for
  Ollama, Claude, OpenAI and Gemini (`LLM_MAX_OUTPUT_TOKENS`). A cut-off
  answer raises `AnswerTooLong` with a clear message and is not retried.
  The retry helper is our own `with_retries()`, because LangChain's
  `.with_retry()` can't exclude exception types.
- **Stop** (`desktop_web/runner.py`): `StopSignal` callback, `stop_run()`
  bridge call, `stopping` / `stopped` events; the Analyze screen gets a
  Stop button (asks once), a "Stopped" panel and a neutral ✕ on the step.
- **Unfinished runs** (`job_agent/runlog.py`):
  - a run row from the start, touched after each step
  - `mark_interrupted()` when the app starts
  - "stopped" instead of an error after Stop
  - Evals: result labels, the time for interrupted runs, and an
    "Unfinished runs" tile
- **Estimates:** `step_estimates()` (average per step on this PC) →
  "A run usually takes about 5m 5s on this PC" and "usually about 3m 25s
  here" under the running step.
- **Step 5 timer:** "16s · 3m 53s waiting for you" (writing vs waiting).
- Docs: D23; Phase 14 got three candidates, each with its question;
  `LLM_MAX_OUTPUT_TOKENS` in the README settings table.
- Tests: **155** (+13 for the cap and retry rules, +6 for Stop, the
  running row, interrupted runs and estimates).

### Checked in the real window, with the real agent
On copies of your installed app's data (4 resumes, run log):
- the estimates showed "about 5m 5s" for a run and "3m 25s" for step 2
- **Stop during step 2: the run ended 0.3 s after the click**; step 2 shows
  stopped, nothing was saved to the tracker, and the run log says
  `stopped` with no error
- **Ollama is free at once after Stop:** a quick call took 2.2 s, the same
  as idle. (A first measurement said 9–11 s; that was my test call using a
  different context size, which makes Ollama reload the model.)
- **closing the window mid-step**, then starting again: the run was marked
  interrupted and shown in Evals, in Recent runs and in the new tile
- the real model and a forced 8-token cap: one attempt, 2.9 s, clear message
- the step-5 split, fed timed events: one draft "16s · 3m 53s waiting for
  you"; with a rewrite "36s · 3m 33s waiting for you"

### Problems hit
1. A first design put a desktop-app import inside `job_agent` (to stop
   retries after Stop). Wrong direction: the agent must not know any UI.
   The fix: `RunStopped` is defined in `job_agent/llm.py`, and the UI raises it.
2. The "Ollama still busy after Stop" measurement was misleading (the
   context-size reload above). Varying the wait before the call exposed it:
   the extra time didn't shrink, so it wasn't leftover work.

### Concepts learned
- **Cooperative cancellation**: a thread can't be killed, so the work checks
  a flag at its own callback points. Streaming makes those points frequent.
- **Per-call output limits** (`num_predict`, `max_tokens`) as a safety net,
  and why a token cap beats a time limit across PCs of different speed.
- **Measure the measurement**: change one thing (the wait) and see whether
  the effect follows.
