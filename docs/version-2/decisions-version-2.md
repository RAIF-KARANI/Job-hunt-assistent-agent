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

## D7 — UI technology ✅ (accepted 29 Oct 2026, to be checked by the 12a spike)
You approved the visual concept, which needs a web front end (three.js).
The spike in 12a measures it before the rewrite starts.

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

## Open questions ❓
- Q1: Which new features go into v2? (we'll discuss them later)
- Q3: Front-end framework: vanilla TypeScript, React, or Svelte (decided in the 12a spike).
