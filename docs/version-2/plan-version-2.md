# Build Plan — JobLens version 2

Continues the base-version plan ([../base-version/plan.md](../base-version/plan.md),
phases 0–11). Decisions behind this plan are in
[decisions-version-2.md](decisions-version-2.md).

Legend: ✅ done · 🚧 in progress · ⏳ not started · 🟡 waiting for a decision

**Workflow rules:** branch `version-2`; no CI, so merge only after local
checks (D3).

| # | Phase | Main concept | Status |
|---|---|---|---|
| 12 | New desktop UI (web front end + 3D + Evals) | desktop web views, JS↔Python bridge, WebGL, eval dashboards | 🚧 in progress |
| 13 | Tray + auto-update | background apps, update checks, safe updating | ⏳ |
| 14 | New features | to be discussed (Q1) | ⏳ |

Release: **v1.0.0** (D10).

---

## Phase 12 — New desktop UI ✅ (30 Oct 2026)
**Goal:** replace the Qt widgets UI with a modern web UI in a native window,
with a three.js "job galaxy" on the Dashboard. The agent (`job_agent/`) stays as it is.
**Concept:** https://claude.ai/artifact/9y3YMbFBn8QtfV1ie9DMS8

| Step | What | Done when |
|---|---|---|
| 12a ✅ | **Spike (1 day, throwaway):** [results](spike-12a-results-version-2.md): pywebview window + a three.js scene + one JS→Python call + one Python→JS event; package it with PyInstaller | numbers measured: installer size, startup time, GPU use with Ollama running; D7 confirmed or changed |
| 12b ✅ | **Bridge** (`desktop_web/bridge.py`): `start_run`, `resume(decision)`, `paste_text`, `list_jobs`, `get_job`, `set_status`, settings read/write; agent events → JS (`log`/`paused`/`finished`/`failed`) | bridge unit tests pass with no window |
| 12c ✅ | **Front-end scaffold** (React + TypeScript + Vite, D13) + **design tokens + app shell**: colors, type, spacing; sidebar; light/dark | `npm run build` output loads in the pywebview window |
| 12d ✅ | **Analyze** screen: steps timeline, live log, draft editor, approve / rewrite / reject, paste-text fallback | full run approved from the new UI |
| 12e ✅ | **Tracker** screen: board (drag = status change) + list view + job details | status changes saved to `jobs.db` |
| 12f ✅ | **Dashboard**: KPI tiles, 2D charts from the run log, job galaxy in 3 levels (D14: animated / still / 2D map), 30 FPS cap + pause during runs (D12), reduced motion, WebGL fallback | charts match the old Dashboard's numbers; every level shows the same data |
| 12f2 ✅ | **Evals** screen (D9): KPIs, pass-rate trend, ratings, safety nets, time/tokens per step, models compared, recent runs; data from the run log via `monitoring.py`; Langfuse/LangSmith status + trace links when tracing is on | numbers match `runlog` queries in tests |
| 12g ✅ | **Settings + Setup wizard** ported (local vs API, PC check, Ollama install, model download progress) + new **"Look and feel" step** and **Settings → Appearance** (`UI_3D`, recommended from the PC check, D14) | first-run flow works on a clean profile; recommendation rule unit-tested |
| 12h ✅ | **Packaging**: front-end build in `build_installer.py`, WebView2 check in the installer, self-test updated | `build_installer.py` passes; real install/uninstall works |
| 12i ✅ | Remove the Qt UI and PySide6; update tests and docs | `pytest` green, LGPL notice updated |
| 12j ✅ | **Fixes from the first real use** (30 Oct, installed app, a LinkedIn job, 4 resumes: step 2 took 3–8 min and there was no way to stop): **Stop** button on Analyze; a time estimate from your own past runs; a cap on answer length (a runaway answer fails within minutes, not 15+); step 5 timer split into "drafting" and "waiting for you"; the run log records **interrupted** (app closed) and **stopped** runs, so Evals counts them | a run can be stopped mid-step; a closed run appears in Evals as interrupted; tests for each |

**Tests:** keep all `job_agent` tests; replace the Qt tab tests with bridge
tests plus a few Playwright checks against the front end served locally.

## Phase 13 — Tray + auto-update 🚧
| Step | What |
|---|---|
| 13a ✅ | Tray icon (pystray): open, "run in background" during long analyses, notification when a cover note is waiting, quit; plus one JobLens at a time (D24) |
| 13b | Update check: GitHub Releases API on startup (at most once a day), compare with `__version__` |
| 13c | Settings: "check for updates" on/off, "check now" |
| 13d | Update flow: download the installer, check its size/hash, run it, close the app (Inno Setup upgrades in place, same AppId) |

Needs the repo to be **public** so the app can read the Releases (D11).

## Phase 14 — New features ⏳
To be listed (Q1). Candidates from the base version:
- Write the verdict after the judge (known limitation)
- Follow-up reminders for jobs applied more than 7 days ago (pairs with the tray)
- Eval suite: compare models on saved jobs
- Shorter LLM outputs for speed

Candidates from the first real use (30 Oct), each with the question to
answer before building it:
- **Choose which resumes to compare for a run.** Step 2 makes one call per
  resume; with 4 resumes it took 3–8 min. *Question: a checklist on the
  Analyze screen each time, or a default set in Settings (e.g. "UAE
  resumes only for UAE jobs")?*
- **Shorter answers in the fit analysis** (every step faster, ~30–50 %).
  Each resume comparison wrote ~1,150 tokens. *Question: how much
  explanation do you want to keep? The evidence check needs the resume
  quotes, so those stay; the long verdict text could shrink.*
- **"Continue where you left off"** after the app was closed mid-run. The
  checkpoints already keep the finished steps; today a restart begins
  again from step 1. *Question: offer it automatically on the next start,
  or only from the interrupted run in Evals / Analyze?*
