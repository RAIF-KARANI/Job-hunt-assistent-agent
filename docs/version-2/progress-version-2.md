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

---

## 13a — Tray icon ✅ (30 Oct 2026)

### Goal
JobLens keeps working while its window is closed, and tells you when it
needs you: open, run in the background, a notification when a cover note
is waiting, quit.

### What was done
- **`desktop_web/tray.py`:** `RunState` follows the same events the page
  gets. The decisions are pure functions:
  - `close_action`: hide while working, quit when idle
  - `status_text`
  - `notification`

  `Tray` wraps pystray: the menu (Open, status, Stop the run, Quit), the
  hover text, one "still working" notification per session, and
  notifications only while the window is hidden.
- **`desktop_web/instance.py`:** one JobLens at a time (local socket +
  random token in `instance.json`).
- **`desktop_web/app.py`:**
  - the single-instance check comes **before** marking interrupted runs, so
    a second start never marks the first one's run
  - the tray is fed every event
  - pywebview's `closing` handler hides or quits
  - the tray and the listener are cleaned up on exit
  - `--smoke` skips both
- **Packaging:** pystray (LGPL-3.0) as plain `.py` files with its license
  texts; Pillow back in the build; the self-test checks the tray parts.
  Installer **58 MB** (was 54: Pillow); app folder 140 MB.
- **Notices:** a pystray LGPL section; Pillow and six.
- Tests: **169** (+14: the tray's decisions from event sequences, hide vs
  quit, notifications only while hidden, no icon → never hide, the
  single-instance handshake, a wrong token, a stale file).

### Checked in the real window, with the real agent
Wired exactly as `app.main()` does it, on copies of your installed app's data:
- during step 1, the tray's hover text said "Working: reading the posting
  (step 1 of 5)"
- **X while working:** the window hid, the run kept going, and one
  notification said "JobLens is still working"
- **a second `python -m desktop_web`:** the window came back in **1.4 s**
  and the second copy exited (code 0)
- **Stop from the tray menu:** the run stopped, the page showed "Stopped",
  and the tray went back to "Idle"
- **X when idle:** the app quit, the tray icon was removed, and
  `instance.json` was deleted
- frozen build + test install: the tray check passes in the build and in
  the installed copy; clean uninstall

### Problems hit
1. **Order matters at start:** marking leftover "running" runs as
   interrupted has to wait until we know this is the only JobLens.
   Otherwise a second start would mark the first one's live run.
2. **pystray's thread isn't a daemon**: without `tray.stop()` in a
   `finally`, the app couldn't exit.
3. **pystray is LGPL**: handled like Qt was (replaceable files + notice)
   instead of writing a Win32 tray by hand (D24).
4. A full-desktop screenshot in the test also captured your other apps. I
   deleted it and removed that capture from the driver: screenshots only
   of the JobLens window from now on. It did show that **Do not disturb**
   is on (the bell with "z"), which hides notification banners; they then
   wait in the notification center.

### Concepts learned
- **Two event loops in one process:** pywebview owns the main thread;
  pystray runs its own Windows message loop on another.
- **Cancelling a window close** from a handler (pywebview's blocking
  `closing` event).
- **Single-instance apps:** a local socket plus a shared secret.
- **LGPL in a frozen app:** keep the library replaceable.

---

## Release v0.3.1 ✅ (30 Oct 2026, D25)
A friend needed the new app before Phase 13 is finished, so the new UI
went out early as **v0.3.1**:
https://github.com/RAIF-KARANI/Job-hunt-assistent-agent/releases/tag/v0.3.1
- Contents: Phase 12 (new UI), 12j (Stop, answer cap, estimates), 13a (tray).
- Files: `JobLens-Setup-0.3.1.exe` (58 MB) and a portable zip (71 MB),
  with SHA-256 checksums in the notes. GitHub's digests of the uploads
  match them.
- Before publishing:
  - the self-test and window test of the build passed
  - no resumes, `.env`, databases, email address or dev preview data in the app
- Tag `v0.3.1` → `b81fe37` on `version-2`; `main` stays at v0.3.0 until v1.0.0.
- Two hiccups:
  1. Claude Code's permission check blocked me from publishing (a public
     page), so you ran `gh release create` yourself.
  2. My first command used a short commit id, which GitHub rejects as a
     target (HTTP 422). The full 40-character id worked. Nothing was
     half-created by the failed try.

---

## 13b — Update check ✅ (30 Oct 2026)

### Goal
On startup, at most once a day, ask GitHub Releases whether there's a
newer JobLens than `__version__`.

### What was done
- **`desktop_web/updates.py`:**
  - pure rules: `parse_version` / `is_newer` (numbers, `X.Y.Z` only);
    `pick_installer` (`JobLens-Setup-<version>.exe` with GitHub's SHA-256);
    `check_due` (once a day; an hour after an error; at once after an update)
  - `UpdateChecker`: fetch, cache in `update_check.json`, never raises
- **Bridge:** `update_status()` (cached, no network), `check_for_updates()`
  (now, for 13c's "Check now"), `_startup_update_check()` (sends an
  `update_available` event to the page).
- **`app.py`:** the check runs on a background thread 5 s after the first
  page load (not again on reloads).
- **Setting** `UPDATE_CHECK` (on by default; when off, no request at all).
- **Sidebar:** "Update available: v…" under the model, linking to the release page.
- Tests: **192** (+23: versions, newer-than, which file is offered,
  once a day / after an error / after an update, the cache, offline,
  no release yet, the setting).

### Checked against the real GitHub API
- as 0.3.1: up to date; pretending to be 0.3.0: v0.3.1 offered, with
  `JobLens-Setup-0.3.1.exe`, 57,793,533 bytes and the published SHA-256
- in the real window (pretending to be 0.3.0): "Update available: v0.3.1"
  appeared 6.3 s after start; clicking it opened the release page in the
  browser (the window stayed on JobLens); a reload used the cache (still
  **one** request to GitHub)
- unauthenticated limit: 60 requests an hour per IP (once a day is far below it)

### Concepts learned
- **Semantic versions compared as numbers**, not text.
- **Being a polite API client:** cache, back off after errors, send nothing
  but what's needed.

---

## 13c — Update settings ✅ (30 Oct 2026)

### What was done
- **Settings → Updates** (`frontend/src/settings/UpdatesCard.tsx`):
  - this version
  - whether a newer one exists, with a link to the release
  - when it last checked
  - the error in plain words ("Couldn't reach GitHub (no internet?)",
    "GitHub asked to wait")
  - the once-a-day switch (`UPDATE_CHECK`, saved at once)
  - **Check now**
- **Check now works even with the switch off** (you asked), and tells the
  sidebar when it finds a newer version.
- Tests: **193** (+1: "Check now" with the switch off, and the sidebar event).

### Checked in the real window, against the real GitHub API
- **pretending to be 0.3.0, switch off:**
  - no request at start (waited past the 5 s delay)
  - turning the switch on wrote `UPDATE_CHECK=true`
  - Check now: "Version 0.3.1 is available (you have 0.3.0). See what's new
    and download", and the sidebar showed "Update available: v0.3.1"
- **as 0.3.1:** "You're up to date: JobLens 0.3.1 is the newest version."
- **offline (simulated):** "Couldn't reach GitHub (no internet?)"; nothing else changed

---

## 13d — Install an update from inside the app ✅ (30 Oct 2026)

### Goal
From "Update available", download the installer, check its size and hash,
run it, and close the app; Inno Setup upgrades in place (same AppId).

### What was done (D27)
- **`desktop_web/updates.py`:**
  - `check_source`: only our GitHub release downloads, only
    `JobLens-Setup-X.Y.Z.exe`, only with a SHA-256; checked before any request
  - `download`: streams with progress; size + SHA-256; a failed file is
    deleted, no `.part` left
  - `launch_installer`: verifies again, then runs it detached and silent
    with `/RELAUNCH=1` and a log
  - `clean_downloads`
- **Bridge:** `download_update()` (`update_progress` / `update_ready`
  events) and `install_update()` (refused during a run; closes the app a
  second later). `app.py` passes the app's close and cleans old downloads at start.
- **Installer:** a `[Run]` entry starts the new JobLens when `/RELAUNCH=1`
  was given; `RestartApplications=no` (one restart, not two).
- **UI:**
  - the sidebar link goes to Settings → Updates
  - "Download and install v… (58 MB)" → progress bar → "✓ Downloaded and
    verified: size and SHA-256 match what GitHub published" → "Install now"
    → "JobLens will open again in a moment"
- Tests: **211** (+18):
  - wrong name / address / repo / no checksum refused before any request
  - tampered bytes and a cut-off file refused and deleted
  - a file swapped on disk caught before running
  - the silent switches
  - the bridge: download → install → close; no install during a run, or before a download
  - old downloads cleaned

### End-to-end test (test build only; your installed JobLens untouched)
Two test installers from one fresh build ("0.3.1" and "0.3.2", the separate
"JobLens Test Build" AppId), a temp AppData folder, and a local web server
standing in for GitHub (trusted by the test process only):
1. installed 0.3.1 silently, started it, put a marker file in its data folder
2. a tampered download: **refused** ("SHA-256 doesn't match"), nothing left
3. the real path: downloaded and verified in 2.8 s → Install now → the
   running 0.3.1 closed → **upgraded in place in 14.3 s** (Windows now shows
   0.3.2, same folder) → **the new version started by itself** → the marker
   file was still there
4. uninstalled: no files, no registry entry; your real JobLens (open at the
   time) had the same checksum and kept running
- The screens in the real window: the sidebar link → Settings → download →
  verified → Install now, and the installer was started with exactly the
  switches above.

### Problems hit
1. **The first end-to-end run hung for 3 minutes:** my test only
   *pretended* the app closes itself, so the installer met a running JobLens.
   With a real close (by process id, never your own window) it took 14 s.
   The installer now writes a log (`install.log`), which is how I could see
   it working.
2. Inno's Restart Manager also "attempted to restart applications": switched
   off, because `/RELAUNCH` already does it.
3. Git Bash turned Inno's `/D…` and `/Q` switches into file paths. Needed
   `MSYS_NO_PATHCONV=1` when calling ISCC by hand.
4. A fresh build overwrote the local `dist\JobLens-Setup-0.3.1.exe` with a
   newer build. The published v0.3.1 on GitHub is unchanged; the local file
   just isn't identical to it any more.

### Concepts learned
- **Supply-chain safety for self-updating apps:** pin the source, verify a
  published hash, check again just before running (time-of-check vs
  time-of-use).
- **Silent upgrades in place** with Inno Setup: same AppId, Restart Manager,
  command-line parameters read by the script (`{param:RELAUNCH}`).
- **End-to-end tests that can't hurt the machine:** a separate AppId, a temp
  AppData folder, a local stand-in for the server, by-process-id actions only.

---

## Phase 13 summary ✅
Tray icon, one JobLens at a time, the once-a-day update check, update
settings, and verified in-app updates. **JobLens can now update itself.**
Next: **v1.0.0**:
- merge `version-2` into `main`
- version 1.0.0
- the release

Everyone on 0.3.x (you, your friend) installs v1.0.0 by hand once; later
versions come by themselves.

---

## Fix: saved settings were ignored after a restart ✅ (31 Oct 2026)

### What you saw
Settings → Check connection, after closing and reopening the app, checked
`qwen3:8b` and gave an error, although another model was chosen.

### What was really wrong (reproduced)
`settings.load_settings()` filled in the **defaults first** and read the
`.env` file second, with `override=False`. Every default was then already
in the environment, so **the file could never override it**. After every
restart:
- `LLM_PROVIDER`, `LLM_MODEL` → ollama / qwen3:8b (a friend on llama3.2, or
  anyone on the Claude API, silently went back to local qwen3:8b)
- `JUDGE_EVIDENCE` → on; `TRACING`, `UPDATE_CHECK`, `OLLAMA_NUM_CTX` → defaults

Settings still *showed* your choice, because it reads the file directly. So
the page and the agent disagreed, and nothing said so. It was in the code
since Phase 9a, and unnoticed because your own settings mostly matched the
defaults and a change does apply until the app is closed.

### Fix
- Read the file first, then fill only the gaps with defaults. A real
  environment variable still beats both.
- 5 regression tests that simulate a fresh start:
  - the saved model and an API choice survive a restart
  - defaults only fill gaps
  - a terminal variable still wins
  - the page and the agent agree on every setting

  4 of them fail without the fix.
- **`tests/conftest.py`:** the tests no longer depend on the developer's
  own `.env`. With the fix, this repo's `.env` really applies, and its
  `TRACING=langfuse` made every agent test wait on a Langfuse server that
  wasn't running (142 s instead of 14 s, 4 timeouts). Tracing is pinned off
  for tests. **216 tests**, 14 s.

### Note
Your settings now really apply. Two of them were being ignored until now:
- **`TRACING=langfuse` in this repo's `.env`**: running from source will
  now trace to Langfuse
- **the installed app's tracing setting**, changed to Langfuse on 30 Oct
  (it takes effect on its next start)

If Langfuse (Docker) isn't running, each run waits a few seconds when it
ends, trying to send its traces. Set Tracing to Off unless you use it.

---

## Release v0.3.2 ✅ (31 Oct 2026, D25)
https://github.com/RAIF-KARANI/Job-hunt-assistent-agent/releases/tag/v0.3.2
- Contents:
  - the settings-after-restart fix (your friend's 0.3.1 went back to qwen3:8b on every start)
  - 13b–13d: the update check, Settings → Updates, verified in-app installs

  **The first version that updates itself**: 0.3.x users install it by
  hand once.
- Checked before publishing:
  - the build's self-test and window test passed
  - the built app started fresh with a saved `llama3.2` used llama3.2 (a
    real call answered)
  - privacy scan clean
- After publishing:
  - marked Latest
  - GitHub's SHA-256 of both uploads matches the notes
  - tag → `2c7f217`
  - JobLens's own updater (as 0.3.1, real API) offers v0.3.2 with the right
    installer and checksum
- You published it with `gh release create` (my permission check blocks
  public pages); the full commit id worked first time.

---

## Merge: `version-2` → `main` ✅ (31 Oct 2026, D3 + D25)
GitHub Actions minutes are used up, so every check ran here (D3) on the
commit that was merged:
1. **Tests:** 216 passed, with SyntaxWarnings as errors.
2. **Front end from a clean `npm ci`:** typecheck clean, production build,
   no dev mock in the bundle.
3. **The app from source, on your real profile:** the page ready, 5 sidebar
   links, the Dashboard looked right (7 jobs, the galaxy, the panel).
4. **Packaging:** `build_installer.py --test-install`:
   - the WebView2 bootstrapper signed by Microsoft
   - the frozen app's self-test PASS (real web search, real Ollama call) and window test OK
   - the test build installed, its installed copy passed both tests, and it uninstalled clean
   - your real JobLens (0.3.2) untouched
5. **Merge safety:**
   - `main` is an ancestor of `version-2` (a fast-forward, no conflicts)
   - in the 118 files that changed, no `.env`, databases, resumes,
     installers, keys or tokens, and no email address
   - no resume file names, job links or Windows user paths in any commit
     (those only ever lived in scratch test scripts)
   - no data folder tracked

---

## Phase 14 plan agreed (31 Oct 2026, D28)
We discussed Phase 14. Its nine steps (14a–14i) are in the plan, your
choices in D28. They all go into v1.0.0 together with the new UI.

## 14a — Quick wins ✅ (31 Oct 2026)

### What was done
- **The model as a dropdown** (`frontend/src/settings/ModelPicker.tsx`):
  - your installed Ollama chat models (embedding models such as
    `qwen3-embedding` left out: they can't chat), or Claude Haiku / Sonnet
    / Opus 5.5, plus "Other…" for typing a name
  - a saved model that isn't installed shows "(not installed)" with a hint,
    instead of hiding the problem (your friend's case)
  - if Ollama doesn't answer, a text box and a hint
  - the setup wizard's Claude step uses the same list
- **Tracker List status filter:**
  - chips with counts, several at once, "All" clears them
  - remembered on this PC
  - "N of M jobs · Cover note ready"
  - "No jobs with this status. Show all"
- **Board:** a column's title is a button → the List, filtered to that status.

### Checked in the real window (copy of your database and resumes)
- **Board → "Cover note ready":** the List opened with the 4 jobs that have
  that status in the database ("4 of 7 jobs · Cover note ready"); adding
  "Researched" → all 7; a status with no jobs → the empty message; the
  filter survived a reload; "All" → 7.
- **The dropdown:**
  - it listed `llama3.2`, `qwen3:14b` and `qwen3:8b` (not `qwen3-embedding`)
  - choosing `qwen3:14b` and saving → saved, and the check said it's installed
  - a saved `qwen3:4b` (not installed) → "qwen3:4b (not installed)" + the hint
  - Claude → its 3 models; "Other…" → a text box
- Your real `jobs.db` unchanged. 216 tests, typecheck clean.

### Problem hit
In the first window run, the "not installed" check read **Claude Haiku**.
Three runs after that were all correct ("qwen3:4b (not installed)" + the
hint). Most likely the test read the page during its reload; I couldn't
make it happen again, so that cause isn't proven.

## 14b — Which resumes to compare ✅ (31 Oct 2026)

### What was done
- **Settings → Your resumes:**
  - a tick box per resume: "compare by default"
  - all ticked is saved as "all", so a resume you add later is included
  - at least one stays ticked
  - new switch **"Ask me which resumes to compare for each job"**
- **Analyze:**
  - switch off: one line, "Comparing with 2 of 4 resumes · change"
  - switch on (or "change"): a chip per resume, pre-ticked with the defaults,
    for this job only
- **Agent:** step 2 scores only the chosen resumes. The log says
  "-> comparing 1 of 4 resumes". If a chosen resume was removed, it says
  so and skips it; if none of them exist any more, it compares all of them.
- **Hardening:** saving a setting now refuses line breaks and other control
  characters, so a value can't add extra lines to the settings file.

### Checked in the real window (copy of your database and resumes, real agent)
- Unticking the two UAE resumes saved the other two; Analyze showed
  "Comparing with 2 of 4 resumes · change", also after a reload.
- "Ask me" saved; the chips came up with the 2 defaults ticked.
- A real run with **1** resume ticked:
  - the log said "comparing 1 of 4 resumes" and scored only that one
  - **step 2 took 30.5 s**, against about 3 min 25 s with all 4 on your PC
  - the step said "best: Raif_Karani_AI_Engineer · fit 75"
  - then I stopped the run
- 222 tests, typecheck clean.

## 14c — Short or detailed fit answer, verdict after the judge ✅ (31 Oct 2026, D29)

### What was done
- **The verdict is written last.**
  - The per-resume AI call now writes only facts: matches with quotes, gaps,
    talking points.
  - After the quote check and the judge, one small call writes the verdict
    for the best resume, from what survived.
  - A verdict under 8 words is replaced by one built in code.
  - Step 2 on the timeline shows "Writing the verdict".
- **Settings → Options → Fit answer: Short (default) / Detailed.**
  - Short: up to 3 talking points.
  - Detailed: up to 5.
  - The matches and the score formula are the same in both.
- Jobs saved before 14c keep their old verdict.

### Measured (2 saved jobs × 2 resumes, judge on, qwen3:8b, 2 runs each)
| | Revolut job | LamdaX job | AI output per job |
|---|---|---|---|
| Before | 100 s, 92 s | 72 s, 71 s | ~3,500 / ~2,500 tokens |
| Short | 73–74 s | 52–54 s | ~2,500 / ~1,700 |
| Detailed | 73–75 s | 65–70 s | ~2,500 / ~2,300 |

- **Before:**
  - A LamdaX verdict called the resume "a strong match… with relevant
    project evidence" right after the judge rejected two claims.
  - A Revolut verdict brought up the location, which isn't among the facts.
- **After:**
  - Every verdict names the proven skills and the main gap, e.g. "Worth a
    try: experience scripting or programming and solid problem-solving skills
    are proven; passion for IT systems and full-time availability are the
    main gaps…".
  - No verdict cited a claim the judge rejected.
- **Fixed along the way:**
  - The first verdict prompt gave one answer of just "apply". The code
    fallback now covers that.
  - My example sentence started with "Apply", so every verdict said
    "Apply", even at fit 41. It now offers "Apply / Worth a try / Not yet".
- **Same as before:** fit scores still vary a little between runs of the
  same job (one run: 63 vs 78).

### Checked in the real window
The Fit answer switch shows "Short" at first. "Detailed" saved and was still
chosen after a reload, and switching back saved "short". 230 tests pass and
the front end builds.

### Found, not fixed (needs your OK)
The resume quote check rejects an exact quote that ends a resume sentence:
"Shipped Docker images" vs "Shipped Docker images." fails, because the full
stop stays on the last word. This can lower fit scores. The fix is small,
but it changes scores, so it should be its own step.

## Quote-check fix (31 Oct 2026, with 14d)
A resume quote that ended a sentence was rejected: "Shipped Docker images"
didn't match "Shipped Docker images.", because the full stop stayed on the
last word. Now a dot at the end of a word is ignored. Dots inside a word
still count ("Node.js", ".NET", "1.2"). None of your 4 saved jobs had been
hit by it. 2 tests added.

## 14d — Continue where you left off ✅ (31 Oct 2026, D30)

### What was done
- **Analyze shows a banner when your last run didn't finish:**
  - "Your last run didn't finish", with the job, the time, and where it
    stopped, e.g. "JobLens was closed during step 3 (Research the company).
    Continue keeps the 2 finished steps."
  - Buttons: **Continue** / **Discard**.
- **The Stopped panel** now has **Continue** next to "Start again".
- **Continue:**
  - picks the run up from its checkpoint; finished steps are not redone
  - the timeline shows them as done again, with their details
  - the live log says "Continuing where you left off: steps 1-2 already done"
- **A cover note left waiting** when the app closed comes back as it was,
  with no AI work. Before this, it was lost after a restart.
- **Discard:** the run isn't offered again, and its checkpoint is deleted.
  Evals is unchanged.

### Checked in the real window (copy of your data, real agent, 1 resume)
1. Started the Revolut job and killed the app during step 3, after steps 1
   (2 min 58 s) and 2 (2 min 2 s) were done.
2. Reopened it: the banner showed the job and "JobLens was closed during
   step 3 (Research the company). Continue keeps the 2 finished steps."
3. Continue: steps 1 and 2 came back as done, with their details. It then
   ran research (3 min 35 s), saving and the draft, and stopped at the
   cover-note review.
4. The run log for the continued run has AI calls **only** for research and
   the draft: none for reading the posting or comparing resumes.

Not shown: the times for steps 1 and 2. A run killed mid-way never wrote its
step times to the run log, so those steps show as done without a time.

6 tests added (stopped run offered, nothing redone, a waiting review comes
back after a restart, Discard, only the latest run, finished runs not
offered). 238 tests pass and the typecheck is clean. Your real `jobs.db`
was unchanged.

## 14e — Follow-up reminders and Start with Windows ✅ (31 Oct 2026, D31)

### What was done
- **Follow-up reminders.** A job in Applied or Interviewing with no change
  for a week (Settings → Reminders: off / 3 / 5 / 7 / 14 days) gets:
  - a "Follow up?" badge on its card and in the list
  - a notice at the top of the Tracker, e.g. "2 applications have had no news
    for a while", with **Show them**, which lists only those jobs
  - in its details: **I followed up** (reminds again a week later) or
    **Remind me in 3 days**
  - a "Follow up?" chip in the List's status filter
- **Tray:**
  - one notification a day while the window is closed ("Time to follow up")
  - a "Follow up on N jobs" line in the menu, which opens the Tracker
- **Start JobLens with Windows, in the tray** (Settings → Reminders):
  - JobLens starts hidden at sign-in
  - closing the window then keeps it in the tray
  - only in the installed app; the uninstaller removes it
- Old trackers get the two new columns automatically.

### Checked in the real window (copy of your data; in the copy Revolut applied 9 days ago, LamdaX interviewing 12 days ago, Lenovo applied 2 days ago)
- Board: the notice said "2 applications have had no news for a while".
  Revolut and LamdaX had the badge; Lenovo didn't.
- "Show them" opened the List with just those two ("2 of 4 jobs · due a
  follow-up").
- Revolut's details: "Applied with no news for 9 days" → **I followed up**.
  `followed_up_at` was saved and the badge went away.
- LamdaX: **Remind me in 3 days** set `snoozed_until` 3 days ahead. The
  notice and badges were then gone.
- Settings: the Reminders card saved "After 3 days" to `.env`. "Start with
  Windows" is disabled in developer mode ("Works in the installed JobLens
  only").
- `--tray`, run as its own process:
  - the window started hidden
  - after 20 s the reminder was sent and today's date written
  - a second start brought the window back
- Fixed on the way: after "Show them", going back to the Board hid the
  notice.

Not checked by hand:
- the real Windows Run key: only the installed app writes it. A test writes
  and removes the same value under a test key.
- what the notification itself looks like: no desktop screenshots, for
  privacy.

14 tests added (`tests/test_followup.py`). 252 tests pass and the typecheck
is clean. Your real `jobs.db` was unchanged.

## 14f — Quick analyze ✅ (31 Oct 2026, D32)

### What was done
- **Ctrl+Alt+J anywhere in Windows** opens a small always-on-top box:
  - It works even with JobLens hidden in the tray.
  - A job link you just copied is already filled in.
  - **Enter** analyzes; **Esc** closes.
- **The run goes on in the background** with your default resumes. The box
  says "Started" and closes itself.
- **A Windows notification** (with Windows' notification sound) when the
  cover note is ready, or if the run needs you or fails.
- **The box refuses** a second job while one is running or waiting for you,
  and says why.
- **Settings → Quick analyze:**
  - change the shortcut (click, press the new keys) or turn it off
  - if another program already has the keys, it says so

### Checked in the real app (`--tray`, copy of your data, real qwen3:8b)
- Started hidden in the tray: the main window and the box were both hidden.
  Ctrl+Alt+J was registered with no conflict.
- **A real Ctrl+Alt+J** (pressed with SendInput):
  - the box opened, always on top
  - the copied LamdaX link was filled in and the field had focus
  - Esc closed it, and the shortcut opened it again
- **Analyze:**
  - "Started. Carry on with your day: you'll get a notification when the
    cover note is ready." The box closed itself.
  - A second Analyze while it ran was refused: "JobLens is already analyzing
    a job. You'll be told when it's done."
- **The notification:** "Cover note ready: The draft for AI Engineer @
  LamdaX is waiting for your review", 20 s later. LamdaX was already in the
  tracker, so the saved analysis was reused and only the draft was written.
  - The main window stayed hidden.
  - Opened, its Analyze screen showed the 137-word draft waiting for review.
- Found on the way: my first check picked up your own open JobLens window
  (same title). The checks now look only at the test's own windows.

Not checked by hand: the sound and what the notification looks like. No
desktop screenshots, for privacy; it's Windows' standard notification.

266 tests pass (14 new in `tests/test_quick.py`, one registers a real
hotkey) and the typecheck is clean. Your real data was unchanged.
