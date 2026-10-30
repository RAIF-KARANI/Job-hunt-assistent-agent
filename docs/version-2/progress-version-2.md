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
