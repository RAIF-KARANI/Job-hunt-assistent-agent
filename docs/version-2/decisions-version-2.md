# Decisions — JobLens version 2

Every decision for version 2, newest last. Each entry says what was
decided, why, and its status. The plan built on these is in
[plan-version-2.md](plan-version-2.md). Docs for v0.3.0 are frozen in
[../base-version/](../base-version/).

Status: ✅ decided · 🟡 proposed (waiting for your OK) · ❓ open

---

## D1 — Freeze the v0.3.0 docs ✅ (29 Oct 2026)
The v0.3.0 docs (idea, plan, progress, architecture, report, handover) moved
to `docs/base-version/`. Version 2 plans and decisions go in
`docs/version-2/*-version-2.md`.

## D2 — Work on the `version-2` branch ✅ (29 Oct 2026)
All v2 work happens on `version-2`, branched from `main` at `0997c09`.

## D3 — No CI: merge after local checks ✅ (29 Oct 2026)
The GitHub Actions minutes are used up, so PR checks can't run. Before every
merge into `main`:
1. `python -m pytest`, all green
2. for UI changes, run the app and look at it
3. for packaging changes, `python scripts/build_installer.py` (it includes the self-test)

Then merge locally (`git merge`) and push. Don't wait for CI.

## D4 — No git history rewrite ✅ (29 Oct 2026)
The only personal data in old commits is one Gmail address in an old version
of `progress.md`. Rewriting history would change every commit hash and need a
force-push, which isn't worth it for one email address.

## D5 — Auto-update and system tray go in version 2 ✅ (29 Oct 2026)
- Check GitHub Releases for a newer version on startup.
- An on/off option for this in Settings.
- A system tray icon.

## D6 — UI first, new features after ✅ (confirmed 29 Oct 2026)
**Why:** new features add screens. Building them in the old UI and
redesigning later means building those screens twice. `job_agent/` has no
UI code, so a UI rewrite doesn't touch the agent, and its tests keep
guarding it. Exception: a feature that is pure agent logic with no new
screen can go in any time.

## D7 — UI technology ✅ (confirmed by the 12a spike, 29 Oct 2026)
You approved the visual concept, which needs a web front end (three.js).
The spike confirmed it: the frozen build is 134 MB (Qt app: 230 MB), the
window is ready in 2.7 s, and a bridge call takes ~1.5 ms. Details:
[spike-12a-results-version-2.md](spike-12a-results-version-2.md).

**Proposal:** a web front end (HTML/CSS/JS + three.js) shown in a native
window through **pywebview + Microsoft Edge WebView2**. The Python agent
stays as it is.

| Option | 3D (three.js) | Installer size | Work | Verdict |
|---|---|---|---|---|
| A. Keep Qt widgets, restyle with QSS | ✗ | same | small | modern look, no 3D |
| B. Qt + QWebEngineView (web UI inside Qt) | ✓ | much bigger (needs PySide6-Addons with Chromium) | medium | works, but heavy |
| **C. pywebview + WebView2** | ✓ | probably smaller than today (no Qt) | medium–large | **recommended** |
| D. Electron or Tauri + Python sidecar | ✓ | larger, or two runtimes | large | too much for this app |

Why C:
- WebView2 is the Edge engine that comes with Windows 11 (already on this
  PC), so the app doesn't ship its own browser.
- Any web UI tech works, including three.js, CSS animation and chart libraries.
- The agent already talks to the UI through only 4 signals (`log`, `paused`,
  `finished`, `failed`), which map directly to JS events.

Costs of C:
- The Qt UI (~1,900 lines) and its headless Qt tests get rewritten.
- A JS build step gets added to `build_installer.py`.
- Windows 10 PCs without WebView2 need the WebView2 bootstrapper in the installer.

Check before committing to C: the spike in plan step 12a.

## D8 — How 3D is used ✅ (29 Oct 2026, concept approved)
- 3D is for the **overview** (the "job galaxy" on the Dashboard). Exact
  numbers stay in 2D charts and tables, which are easier to read.
- The 3D scene **pauses while the agent runs** and when the window is
  hidden, because the local LLM needs the same GPU.
- Settings gets a "3D effects" switch, and the scene respects Windows'
  reduced-motion setting.

Visual concept (3 screens, sample data):
https://claude.ai/artifact/9y3YMbFBn8QtfV1ie9DMS8

## D9 — An "Evals" screen for agent quality ✅ (29 Oct 2026)
You asked for an LLM eval dashboard showing how the agent did.
- **Main data source: the built-in run log** (`jobs.db`: `runs`,
  `run_steps`, `run_llm_calls`, `run_quality`, `run_feedback`). It is always
  on and works for every user, with no Docker and no cloud.
- **Langfuse and LangSmith stay optional developer tools.** Langfuse needs
  Docker, and LangSmith uploads traces (including resume text) to the cloud,
  so neither can be required for users. When tracing is on, the Evals screen
  shows its status and links each run to its trace.
- **The screen shows:**
  - KPIs: evidence pass rate, notes approved, agent time, tokens, tool failures
  - evidence pass rate per run (trend)
  - your ratings (human eval)
  - the 7 safety-net checks
  - time and output tokens per step
  - models compared side by side
  - recent runs, with trace links
- The Dashboard's "Safety nets" card links to it.

Concept: the "Evals" artboard at the link in D8.

## D10 — Version number: v1.0.0 ✅ (29 Oct 2026, you left it to me)
Version 2 (new UI, tray, auto-update, public repo) ships as **v1.0.0**: the
first public, stable release. Fixes in between use 1.0.x.

## D11 — The repository goes public ✅ (29 Oct 2026)
You make it public yourself (the pre-public check was done on 28–29 Oct).
This also lets auto-update (Phase 13) read GitHub Releases.

## D12 — 3D is capped at 30 FPS and paused during runs ✅ (29 Oct 2026, measured)
The spike measured qwen3:8b's speed with the scene running:
- uncapped (~144 FPS): 25–35 % slower
- capped at 30 FPS: 5–7 % slower
- paused: no slowdown

So the scene runs at 30 FPS at most, pauses while the agent runs, and
stops when the window is hidden (WebView2 already does this).

## D13 — Front end: React + TypeScript + Vite ✅ (30 Oct 2026)
Closes Q3.
- React has the biggest ecosystem, and it's a useful skill for the job search.
- three.js through react-three-fiber.
- TypeScript catches bridge mistakes (typed events and API).
- Vite builds static files that ship inside the app (no server, works offline).

Node is needed only to **build**, not to run the app.

## D14 — The user chooses the 3D level, in setup and in Settings ✅ (30 Oct 2026)
**Why:** a friend's laptop (no dedicated GPU, a smaller local model) would
be slowed by the 3D scene. The spike showed that 3D takes GPU time away
from a local LLM.

Three levels, stored as `UI_3D` in `.env`:

| Level | What it does | GPU cost |
|---|---|---|
| `animated` | 3D galaxy, slow rotation, max 30 FPS | small (−5–7 % LLM speed, measured) |
| `still` | 3D galaxy that moves only while you drag or zoom | ~0 when idle |
| `off` | flat 2D orbit map (SVG) with the same information: fit = distance | none |

- **Setup Wizard:** a new "Look and feel" step, pre-selected from the PC
  check, with the reason shown. The rules:
  - **off** when there's no dedicated GPU, the local model doesn't fully fit
    in graphics memory, or WebGL isn't available
  - **still** when the local model fits but leaves less than ~2 GB of
    graphics memory free
  - **animated** when there's spare graphics memory, or when you use the
    Claude API (the GPU isn't busy with the LLM)
- **Settings → Appearance:** change it any time; takes effect immediately,
  no restart.
- **Always on, whatever the level:**
  - pause during agent runs, and when the window is hidden (D12)
  - follow Windows' "reduce motion" setting (`animated` acts as `still`)
  - if WebGL fails, switch to `off` automatically and say so once
- No information is lost: every 3D view has the same data in 2D.

## D15 — Progress comes from Python as structured events ✅ (30 Oct 2026, step 12d)
**Why:** the steps timeline needs to know "step 2 started", "best resume
found", "waiting for you". The agent only *prints* that. Parsing print
text in two places (Qt did it in the tab) would break silently when a line
is reworded.
- The runner (`desktop_web/runner.py`) reads the agent's lines once and
  sends `step` / `step_detail` / `reused` events. The page never parses log
  text; it still shows the raw log too.
- A test checks that the lines the runner looks for still exist in the
  agent's code, so rewording one fails a test instead of the timeline.
- The agent itself is unchanged.

## D16 — A run survives page switches and reloads ✅ (30 Oct 2026, step 12d)
- The run's state lives in a small store outside React. Going to the
  Tracker mid-run and back shows the same steps, log and draft.
- The runner keeps the current run's events; after a reload (F5) the page
  gets them from `run_state()` and replays them through the same function
  that handles live events. One code path, so the two can't disagree.
- Not kept across an app restart (the paused run itself is: SqliteSaver).
  Resuming a run after a restart is a possible later feature.

## D17 — Small safety choices on the Analyze screen ✅ (30 Oct 2026, step 12d)
- **The model is checked before a run starts** (about 2 s), so a stopped
  Ollama shows a clear message right away, not a crash minutes in.
- **Reject asks once more**, inline ("Reject this draft? Nothing is
  saved."): a draft takes minutes to make.
- **Rewrite warns** when you edited the text yourself, because the rewrite
  starts from the agent's draft.
- **Pasted job text must be at least 200 characters** (same rule as the
  Qt app).
- **The rating form appears after every reviewed run**, with the cover note
  rating pre-filled from what you did (Phase 11c rule). Skipping is one click.

## D18 — Tracker: one column per status, links open outside ✅ (30 Oct 2026, step 12e)
- **Six columns, not the concept's five.** The concept merged "offer" and
  "rejected" into "Closed"; dropping a card there would have to guess which
  one. Empty columns are narrow, so all six fit at a normal window width.
- **Every status change can be undone** for 8 seconds (a small "Undo"
  notice). Dragging is quick, so a wrong drop is easy.
- **Keyboard path:** a card opens its details, where the status is a normal
  dropdown; the List view has the same dropdown in each row. Dragging is
  never the only way.
- **Web links always open in your browser** (new bridge call `open_link`,
  http/https only). A plain link would have navigated the app window away
  from JobLens. Other schemes (`file:`, `javascript:`...) are refused,
  because the page shows links that came from the web.
- **"Analyzed 2 days ago"** uses when the job was added (`created_at`, now
  in `list_jobs()`); "Applied 3 days ago" uses the last status change.
- **"Draft a cover note"** fills in the Analyze form but doesn't start the
  run: you see the model check and press Analyze yourself.

## D19 — Dashboard: plain three.js, loaded only when 3D is on ✅ (30 Oct 2026, step 12f)
- **Plain three.js, not react-three-fiber** (changes D13 for this one
  scene). The galaxy is one component, and its value is the frame loop:
  30 FPS cap, draw-only-on-change for "still", stop during runs. Owning the
  loop directly is simpler than steering r3f's, and one less dependency.
- **three.js loads only when needed.** It's a separate file (~570 kB) the
  page loads only when the 3D level is animated or still. With 3D off the
  page never loads it and never creates a WebGL canvas (checked).
- **"Low-power" GPU** is requested for the scene: on laptops with two
  GPUs, the big one stays free for the local model.
- **The jobs are real buttons** over the scene, at every level: Tab
  reaches them (best fit first), screen readers read company, role, fit and
  status. 3D only draws the dots.
- **No mouse-wheel zoom:** the wheel scrolls the page. Zoom has buttons
  (+, −, Reset).
- **WebGL failure → flat map for this session**, with a notice. The saved
  setting is not changed (a driver hiccup shouldn't turn 3D off for good).
- **Distance = fit, 100 → 20:** fits from 100 down to 20 use the whole
  radius (anything lower sits on the edge). On a 0-100 scale your four 75+
  jobs were crowded into the middle fifth.
- **Run numbers have a time range** (7 days / 30 days / All); the jobs
  are always everything in the tracker. Numbers come from the same
  `monitoring.py` functions as the Qt Dashboard (tested equal).
- **"Draft cover note" time = the `draft` step**, not `cover_note`. The
  `cover_note` step pauses for your review, so its own timing is split in
  two and showed ~0 s. Fixed in `monitoring.py`, so the old Dashboard and
  the Langfuse dashboard are fixed too.
- **Where the Qt Dashboard's 6 charts went:** fit per job → galaxy;
  status → "Where your applications are"; time per step and safety nets →
  Dashboard cards; LLM time vs tokens and your ratings → Evals (12f2, D9).

## D20 — Evals: the run log is the source; tracers are shown, not switched to ✅ (30 Oct 2026, step 12f2)
- **No "data source" switch.** The concept had Run log / Langfuse /
  LangSmith buttons. Following D9, every number comes from the run log
  (works for everyone, offline). The three become **status chips**
  (always on / running / not reachable / no key).
- **Trace links only for runs that have a trace.** The run log now
  records which tracer was on for each run (new `runs.tracing` column;
  older databases get it automatically, like `decision` in 11). Langfuse
  links go straight to the run's session (the project id is read from
  Langfuse's API); LangSmith links open LangSmith (its run pages need IDs
  JobLens doesn't have), with the session id on hover.
- **The Langfuse check is a separate call** (`tracing_status()`), so the
  numbers never wait up to 3 s for a Langfuse that isn't running.
- **No cost column.** Prices change and aren't in the run log, so a cost
  figure would be invented. "Tokens / run" lets you compare instead.
- **The model filter changes everything except "Models compared"**, which
  always shows every model (that's its job).
- **Rating colors were checked**, not picked by eye: the dataviz palette
  validator (color-blind and normal-vision separation, both themes). The
  concept's blue and violet were too close to tell apart, so the colors are
  blue / green / orange.
- **The trend note** compares the latest runs with the same number of runs
  before them (up to 10 each); with fewer than 4 runs it isn't shown.

## D21 — Settings and the Setup wizard ✅ (30 Oct 2026, step 12g)
- **Same flow as the Qt wizard, plus "Look and feel"** (D14):
  welcome → where the AI runs → this PC | Claude API → resumes → look and
  feel → done. Nothing is saved until Finish (resumes added and models
  downloaded stay, of course). "Skip for now" shows it again next launch.
- **When it opens:** on first launch only (setup never finished and no
  resumes, the Qt rule, so you won't see it). Any time from Settings →
  "Run setup wizard".
- **The 3D recommendation** (`system_check.recommend_3d`, pure and tested):
  - Claude API: animated
  - no graphics card: off
  - graphics memory unknown: still
  - otherwise by how much graphics memory the chosen model leaves free: below 0 off, below 2 GB still, else animated

  The page overrules it with "off" if WebGL doesn't work. **This laptop
  (RTX 4060, 8 GB) with qwen3:8b gets "still"**: about 1.1 GB is left over.
- **Settings saves in two ways:** the AI model card has a Save button
  (typing a model name shouldn't save every letter); appearance and options
  save the moment you change them. A new 3D level reaches the Dashboard
  immediately, with no restart.
- **"Check connection" for Claude makes a real 5-token call.** The quick check
  only sees that a key exists, so a wrong key looked fine (found in testing).
  The API key is never sent back to the page; it only says "a key is saved".
- **Tracing says "applies after restarting JobLens"**: it's read once at
  start. The evidence double-check applies at once.
- **Native file dialog for resumes**, and PDFs are copied (never moved).
  Removing asks first and deletes only the app's copy; a name with a folder
  in it (`../x.pdf`) is refused.
- **Installing Ollama and downloading a model stream progress** as events, one
  at a time. Without winget, the download page opens in your browser.

## D22 — Packaging the web app ✅ (30 Oct 2026, step 12h)
- **One command still builds everything** (`python scripts/build_installer.py`):
  1. front end (`npm ci` + build)
  2. WebView2 bootstrapper
  3. PyInstaller
  4. self-test **and** window test of the frozen app
  5. installer

  Node is needed to build, never to run (D13).
- **The installer adds WebView2 only when it's missing.** It runs
  Microsoft's ~2 MB bootstrapper silently (per user, no admin prompt). The
  build downloads the bootstrapper once and **refuses it unless it is validly
  signed by Microsoft**; it's never committed (`build/` is ignored). The
  installer, the app and the self-test use the same three registry keys
  to look for it. If it's still missing at start (e.g. a portable copy),
  the app shows a Windows message with the download link, not a crash.
- **The build no longer contains Qt, matplotlib or Pillow** (the code
  stays in the repo until 12i). Result: **54 MB installer** (Qt: 81 MB),
  126 MB app folder (Qt: 230 MB).
- **Third-party notices updated now, not in 12i:** the build already ships
  React, three.js, the fonts (SIL OFL) and pywebview, and the Qt LGPL
  section no longer applies.
- **Testing an install never touches a real JobLens.** `--test-install`
  builds a separate "JobLens Test Build" (own AppId, folder and shortcut;
  its uninstaller never deletes data). It installs it silently in a temp
  folder, runs the **installed** copy's self-test and window test,
  uninstalls it, and checks that nothing is left and the real install is
  unchanged. Needed because v0.3.0 is installed on the build PC, and the
  real installer would upgrade it in place (same AppId).
- **The version stays 0.3.0** until the release (D10: v1.0.0 after
  Phase 13).

## D23 — Stop, an answer-length cap, and unfinished runs in the log ✅ (30 Oct 2026, step 12j)
From the first real use of the installed app (a LinkedIn job, 4 resumes:
step 2 took 3–8 min, and the only way out was closing the app).
- **Answer-length cap: 4,096 tokens per LLM call** (`LLM_MAX_OUTPUT_TOKENS`).
  The largest real answer is ~1,230 tokens, so normal runs never reach it.
  Before, Ollama had no limit and Claude's client default was 128,000 (a
  runaway costs money). **A cut-off answer is not retried**: it fails at
  once with a clear message, because a model stuck repeating itself usually
  repeats again. A token cap, not a time limit: a normal answer on a slow PC
  can take minutes, so a time limit would be wrong on one PC or the other.
- **Stop button** on Analyze (asks once, like Reject in D17). A thread can't
  be killed, so the run stops itself: a callback raises `RunStopped` at the
  next event. Ollama reports every token, so an answer being written stops
  at once and Ollama is free immediately (measured). If the model is still
  reading the prompt, Stop waits for its first token (up to a few seconds).
  `RunStopped` lives in `job_agent` (no UI dependency) and is never retried.
- **Nothing is saved to the tracker on Stop or close** (a half-analyzed job
  would be a wrong card). The finished steps stay in the checkpoint; a
  "continue where you left off" feature is a Phase 14 candidate.
- **The run log has a row from the start** ("running", refreshed after each
  step). At start, the app marks its own leftover "running" runs as
  **interrupted** (only `desktop` ones: a CLI run going on is left alone).
  Stop → **stopped** (not an error). Evals shows both, plus an
  "Unfinished runs" tile with the agent time they cost.
- **Time estimates** come from this PC's own run log (average per step), not
  from guesses.
- **Step 5's timer** shows "drafting · waiting for you": the old timer
  included the time you spent reading the draft.

## Open questions ❓
- Q1: Which new features go into v2? (we'll discuss them later)
