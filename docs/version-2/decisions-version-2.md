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

## D24 — Tray icon and one JobLens at a time ✅ (30 Oct 2026, step 13a)
- **Closing the window while the agent works** (a step running, or a draft
  waiting for you) **hides it to the tray**; the run goes on. One
  notification says so, once per session. **Closing it when nothing is
  going on quits**, as before, so the app never lingers by surprise. (A
  Settings switch "always keep running in the tray" can come with 13c.)
- **Notifications while hidden:** the cover note is ready, the job text
  must be pasted, the run finished or failed. Windows shows them as
  banners unless Do not disturb is on (then they wait in the notification
  center).
- **Tray menu:** Open JobLens (also a click on the icon), a status line
  ("Working: comparing your resumes (step 2 of 5)"), Stop the run, Quit
  (says "stops the run" while working; a quit run shows as interrupted).
- **One JobLens at a time:** a second start brings the first one's window
  back (it may be hidden) and exits. It's a local socket on 127.0.0.1 with a
  random token in `instance.json`, so no other program can trigger it, and a
  stale file from a crash doesn't block starting. The second start never
  marks the first one's run as interrupted (the check comes first).
- **pystray (LGPL-3.0)**, not a home-made tray: it handles the Windows
  message loop, menus and notifications. Compliance as for Qt before: it
  ships **unmodified, as plain .py files** (`module_collection_mode`), so
  it can be replaced, with its license texts and a notice. The alternative,
  ~300 lines of raw Win32 code to maintain, wasn't worth it.
- **If the tray can't start**, closing quits as before: a window must
  never hide with no icon to bring it back.
- The build's window test (`--smoke`) skips the tray and the single-instance
  check, so it never touches a JobLens you have open.

## D25 — v0.3.1: an in-between release for friends ✅ (30 Oct 2026, your call)
Amends D10. A friend needs the new app now, before Phase 13 is finished.
- **v0.3.1** = the new UI (Phase 12), the 12j fixes and the tray (13a),
  built from `version-2` and published on GitHub Releases.
- **v1.0.0 stays the full version-2 release**, after the update check
  (13b–13d). v0.3.1 can't update itself, so its users install v1.0.0 by
  hand once; from then on updates come by themselves.
- `main` stays at v0.3.0 until v1.0.0; the v0.3.1 tag points at `version-2`.
- **v0.3.2** (31 Oct, your call): the settings-after-restart fix (your
  friend's 0.3.1 went back to qwen3:8b on every start) plus 13b–13d. It is
  the **first version that updates itself**: 0.3.x users install it by
  hand once; from it on, Settings → Updates installs new releases.
- **v1.0.0** = version 2 **with the Phase 14 features** (you: "keep 1.0.0
  for both ui update and features"). This corrects the note above and the
  Phase 13 summary, which put v1.0.0 straight after Phase 13.
- **`main` follows the latest release** (31 Oct; replaces "main stays at
  v0.3.0"). The Latest release was the new app while the repo's front page
  still showed the Qt app's README. `version-2` was merged into `main` after
  the D3 local checks (no CI), as a fast-forward. Phase 14 continues on
  `version-2` and is merged again for v1.0.0.

## D26 — The update check ✅ (30 Oct 2026, step 13b)
- **Source:** GitHub's public `releases/latest` for this repo, no account.
  Drafts and pre-releases are never offered (that endpoint skips them).
- **What GitHub sees:** one request with the User-Agent `JobLens/<version>`.
  No personal data, no device id, nothing about your jobs.
- **When:** at most **once a day**, 5 s after the window opened, on a
  background thread (startup never waits). The answer is cached in
  `update_check.json` in the data folder. After a network error it tries
  again an hour later, not at every start. After an update it asks again
  at once (the cached answer was about the old version).
- **Versions are compared as numbers** (`0.3.10` > `0.3.9`); anything that
  isn't `X.Y.Z` (e.g. `1.0.0-rc1`) is never offered.
- **Only the installer** `JobLens-Setup-<version>.exe` is offered (not the
  portable zip, never a test build), with the **SHA-256 GitHub publishes**
  for it. 13d checks the download against it before running anything.
- **Shown** as "Update available: v1.0.0" in the sidebar (the approved
  concept); for now it opens the release page; 13d installs from there.
- **`UPDATE_CHECK`** setting, on by default; when off, no request is made
  at all. The switch and "Check now" are 13c.

## D27 — Installing an update from inside the app ✅ (30 Oct 2026, step 13d)
JobLens runs a program it downloaded, so every rule here is about only ever
running the real installer.
- **Where from:** only `https://github.com/RAIF-KARANI/Job-hunt-assistent-agent/releases/download/…`
  (GitHub redirects to its own storage; the requests library follows that),
  and only a file named `JobLens-Setup-X.Y.Z.exe`. Checked **before** any request.
- **Verified twice:** size and **SHA-256 must match what GitHub publishes**
  (the asset `digest`), right after the download and again right before
  running it (the file sat on disk in between). A file that fails is
  deleted; nothing is ever run.
- **No checksum, no install:** a release without a published SHA-256 only
  gets the release-page link.
- **Not during a run** (a step running or a draft waiting): installing
  closes JobLens.
- **How:** the installer runs detached and silent (`/SILENT /SUPPRESSMSGBOXES
  /NORESTART /RELAUNCH=1 /LOG=…`). JobLens closes itself a second later.
  Inno Setup upgrades in place (same AppId, same folder; the data folder is
  never touched) and starts the new version (`/RELAUNCH=1`, a new [Run]
  entry; a plain silent install doesn't start the app). Windows' Restart
  Manager is not allowed to restart it too (`RestartApplications=no`).
- **Downloads are cleaned up** at the next start; the installer's log stays
  next to it until then.
- **The flow:** the sidebar's "Update available" goes to Settings →
  Updates: "Download and install v… (58 MB)" → progress → "✓ Downloaded and
  verified" → "Install now".

## D28 — Phase 14: the features for v1.0.0 ✅ (31 Oct 2026, discussed with you)
Closes Q1. The steps are in the plan (14a–14i). Your choices:
- **Resumes:** a default set plus "ask me for each job". Not a checklist
  every time (too much).
- **Fit answer:** short or detailed, your choice.
- **Reminders:** Applied **and** Interviewing, after 7 days.
- **Shortcut:** `Ctrl+Alt+J`.
- **Resume prompt:**
  - your resume is **not** in the prompt; you give it to the other AI yourself
  - generated **only when you press the button** (no compute spent otherwise)
  - not offered as needed when the resume already covers the job
    (≥ 95 % coverage, no gaps)

  My additions you agreed to:
  - built with **no AI call** (a template filled from the analysis)
  - "keyword coverage", not an "ATS score" (there's no standard ATS score)
  - "rephrase only real experience, never invent"
- **Kept from my extras:** verdict after the judge (A), notes per job (B),
  export (C) **with PDF**.
- **Dropped:** the near-duplicate-resume hint (D). Your reason: resumes for
  two countries are meant to differ in structure, and the user knows which
  one fits.

## D29 — The verdict is written last; "Short" is the default ✅ (31 Oct 2026, step 14c)
- **The verdict moved out of the per-resume AI call.**
  - It used to be written before the quote check and the judge, so it could
    praise a claim they then rejected. That happened in the "before" run.
  - Now one small extra call writes it, for the best resume only. It sees
    only the proven skills and the gaps.
  - A verdict under 8 words is replaced by one built in code from the same
    facts. That covers the bare "apply" seen in testing.
- **Default "Short":**
  - step 2 is about 20% faster than before
  - about 25% less AI output
  - the matches, the quotes and the score formula are untouched
- **"Detailed" keeps up to 5 talking points.** qwen3:8b mostly ignores the
  "2–3 sentences" request for the verdict, so Settings doesn't promise a
  longer verdict.

## D30 — Continue where you left off: what is offered ✅ (31 Oct 2026, step 14d)
- **Only your latest run** is offered, and only if it didn't finish:
  - closed mid-run ("interrupted")
  - stopped with Stop
  - or a cover note / paste left waiting for you ("paused")

  A run you left days ago and then followed with others isn't offered.
- **Failed runs are not offered.** An error (bad link, model crash) would
  usually just happen again. "Try again" stays for those.
- **Continue** runs from the checkpoint. The step that was cut off runs
  again; the finished steps don't. A run that was waiting for you shows the
  same draft again, with no AI work.
- **Discard:**
  - marks the run so it isn't offered again
  - deletes its checkpoint
  - leaves the run in Evals as it was (still "stopped" or "interrupted")

## D31 — Follow-up reminders and Start with Windows ✅ (31 Oct 2026, step 14e)
- **When a job is due a follow-up:**
  - its status is **Applied or Interviewing**
  - and it has had no change for **FOLLOW_UP_DAYS** (default 7; Settings →
    Reminders: off, 3, 5, 7 or 14 days). The clock starts at the last
    status change or your last "I followed up".
  - and it isn't snoozed
- **What you see:**
  - a "Follow up?" badge on the card and in the list
  - a notice at the top of the Tracker, whose "Show them" lists only those jobs
  - in the job's details: **I followed up** (the clock starts again) or
    **Remind me in 3 days**
- **The tray notification:** at most **one a day**, and only while the
  window is closed. The day is remembered in `follow_up_notice.txt`, so a
  restart doesn't repeat it. JobLens checks every half hour.
- **Start JobLens with Windows** is off by default and lives in the
  registry (`HKCU\...\Run\JobLens = "JobLens.exe" --tray`), not in `.env`.
  Turning it off in Task Manager shows as off in Settings too.
  - JobLens then starts **hidden in the tray**.
  - Closing the window **keeps it in the tray** even when idle; quit from
    the tray icon. Without the setting, closing an idle JobLens quits, as
    before.
  - Only the installed app can turn it on. In developer mode the
    checkbox is disabled.
  - The uninstaller removes the value.
- The rule is plain dates in `job_agent/followup.py`, with no AI. Old
  `jobs.db` files get the two new columns (`followed_up_at`,
  `snoozed_until`) on first use.

## D32 — Quick analyze ✅ (31 Oct 2026, step 14f)
- **The shortcut:** **Ctrl+Alt+J** by default, changeable in Settings →
  Quick analyze ("Change", then press the keys) or turned off.
  - It needs Ctrl or Alt plus one letter, digit or F1-F12, so it never fires
    while you type.
  - If another program already uses it, Settings says so and you pick
    another.
  - It's a Windows global hotkey (`RegisterHotKey`), so it works with the
    window in the tray. It needs JobLens running.
- **The box:** a small frameless window, always on top.
  - A link you just copied is filled in. Only http(s) links: other
    clipboard text is never shown.
  - **Enter** = Analyze, **Esc** = close.
  - It is made once at start (hidden), so the shortcut opens it at once.
- **Analyze from the box** is the same run as on the Analyze screen:
  - It uses your **default resumes** and never asks, even with "Ask me which
    resumes" on: the box is for speed.
  - It checks the model first, as Analyze does.
  - It refuses while a run is going or a cover note / paste is waiting for
    you, and says why.
  - The box closes; the Analyze screen shows the run if you open it.
- **The notification:** a quick run is always told about ("Cover note
  ready", "JobLens needs you", "Run failed"), even if the window is open,
  because you didn't start it from there.
  - The sound is Windows' own notification sound, so it follows your
    Windows sound and Do Not Disturb settings.
  - After that first notification, the run is a normal one.

## D33 — The resume-improvement prompt ✅ (31 Oct 2026, step 14g)
- **Only on request:**
  - **Generate resume prompt** after a run
  - **Resume prompt** in a job's details
- **No AI call.** A template filled from the analysis already in the
  tracker, so it is instant and free.
- **Your resume is not in it.** You paste the prompt and your resume into
  the other AI yourself, so you choose what leaves your PC.
- **Keyword coverage, not an "ATS score":**
  - It counts the job's own required skills that your resume visibly
    proves, i.e. a quote that passed the code check and the judge. Example:
    "5 of 7 required skills (71%) · 0 of 1 nice-to-haves".
  - It uses the job's own list, so a requirement the model skipped still
    counts as not shown.
  - A skill counts as shown only if at least 80% of the shorter wording's
    words appear in the other. The fit score's looser rule (half the words)
    would count "NoSQL databases" as "SQL databases".
- **Already fits:** coverage of 95% or more, and no required skill missing.
  Then it says "Your resume already fits this job", with a small "Generate
  the prompt anyway". Nice-to-haves don't block this.
- **The rules in the prompt:**
  - use only experience already in the resume
  - never invent or inflate anything
  - ask about a missing skill instead of adding it
  - keep the resume's structure and country conventions
- **What it asks for back:**
  - edits as before -> after
  - questions about the gaps
  - keywords, only where they are true

## D34 — Your notes per job ✅ (31 Oct 2026, step 14h)
- **Three fields per job**, in a "Your notes" section of its details:
  - **Interview** (date and time)
  - **Contact** (free text: name, email, LinkedIn; up to 300 characters)
  - **Notes** (up to 5000 characters)
- **Saving:** with a **Save notes** button, not on every key. It's disabled
  until something changes and shows "Saved" afterwards.
- **The interview time is stored as you typed it** (your local time,
  `2026-11-04T10:30`), not converted to UTC: an interview is at a time on
  your clock.
- **On the card:** the interview ("Interview Wed, Nov 4, 10:30 AM", muted
  once it has passed) and the contact. Notes stay in the details.
- **On the list:** an **Interview** column you can sort by; jobs without one
  go last.
- **Search** also finds contacts and notes.
- **Notes don't count as news:** saving them doesn't change `updated_at`,
  so the follow-up clock (D31) isn't reset by your own notes.
- A re-analysis keeps them. Old trackers get the columns automatically.

## D35 — Export ✅ (31 Oct 2026, step 14i)
- **Where:**
  - **Export CSV** on the Tracker
  - **Save as: Word (.docx) / PDF / Text (.txt)** under the cover note in a
    job's details (the latest approved note)
- **Saving:** Windows' own Save dialog, with a suggested name ("Cover note -
  LamdaX - AI Engineer.docx", "JobLens jobs - 2026-10-31.csv"). Afterwards
  "Saved to ..." with **Show in folder**, which only opens a file exported
  in this session.
- **CSV:**
  - one row per job, 14 columns, your notes / interview / contact included
  - UTF-8 with a BOM, so Excel shows non-English names correctly
  - a cell starting with `= + - @` gets a leading `'`: job titles come from
    the web, and Excel would otherwise run such a cell as a formula
- **.docx** is written with the standard library (a .docx is a zip of XML):
  Calibri 11, A4. No new dependency.
- **PDF** uses **ReportLab** (BSD-3-Clause, the one new dependency), with
  Windows' Arial embedded so any name in the note prints. Helvetica if Arial
  is missing.
- No AI anywhere: the files are exactly what's in the tracker.
- The installed app's self-test now writes a .docx and a .pdf, so a build
  that can't is caught before release.

## D36 — 1.0.1: Langfuse keys in the app, and deleting a job ✅ (31 Oct 2026)
**Langfuse.** You set Tracing to Langfuse and restarted, and Evals said
"not reachable". Langfuse was running; the installed app simply had **no
keys**: they were only in the developer `.env`, and Settings had nowhere to
enter them. Every failure was reported as "not reachable".
- **Settings → Options → Tracing = Langfuse** now shows:
  - the address, the public key and the secret key
  - **Save keys** and **Test**
- **The secret key is write-only, like the Claude key.** The page never
  receives it; the field just shows "Saved".
- **The status says what's wrong** (Evals' chip and the Test button):
  - "no keys"
  - "keys rejected" (Langfuse answered 401/403)
  - "not reachable" (nothing answers; start Docker)
- Your installed app got the keys copied from the repo `.env` (your OK,
  "fix both").

**Deleting a job** (your friend's idea):
- **Where:** "Delete this job…" at the bottom of a job's details. You confirm
  first ("Delete LamdaX? … can't be undone"); the focus starts on Cancel.
- **It removes:**
  - the tracker row and its analysis
  - its approved cover notes, in the database and their `.md` copies
  - your notes on it
- **The run log keeps its runs:** Evals' numbers stay right; they just no
  longer link to a job.
- **Refused while the agent works on that job,** or while its cover note
  waits for you.
- **Analyzing the same link later starts fresh,** with nothing reused.

## D37 — 1.0.3: the shortcut keeps JobLens in the tray; notification clicks open it ✅ (31 Oct 2026, your choice)
Amends D32 and 13a's "closing an idle JobLens quits".
- **While the quick-analyze shortcut is registered,** closing the window
  hides JobLens to the tray instead of quitting. The shortcut only works
  while JobLens runs, and your way of using it (scrolling LinkedIn, then
  Ctrl+Alt+J) needs it running. Quit from the tray icon.
  - The first close each session shows "JobLens is in the tray: it keeps
    running so your shortcut and reminders work".
  - With the shortcut off, or taken by another program, closing quits as
    before, unless Start with Windows is on (D31).
  - The other options were "always quit" (1.0.2) and "ask once"; you chose
    keeping it in the tray.
- **Clicking a notification opens JobLens on the screen it's about:**
  - Analyze: "Cover note ready", "JobLens needs you", "Run failed"
  - the Tracker: "Run finished", "Time to follow up"

  pystray ignores notification clicks (`NIN_BALLOONUSERCLICK`), so JobLens
  adds that one message to pystray's handler.

## Open questions ❓
- (none)
