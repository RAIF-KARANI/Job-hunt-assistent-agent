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
| 15 | Output quality + cleanup (evals first) | golden-set evals, per-requirement classification, grounded research | 🟡 proposed |

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

## Phase 13 — Tray + auto-update ✅ (30 Oct 2026)
| Step | What |
|---|---|
| 13a ✅ | Tray icon (pystray): open, "run in background" during long analyses, notification when a cover note is waiting, quit; plus one JobLens at a time (D24) |
| 13b ✅ | Update check: GitHub Releases API on startup (at most once a day), compare with `__version__` |
| 13c ✅ | Settings: "check for updates" on/off, "check now" |
| 13d ✅ | Update flow: download the installer, check its size/hash, run it, close the app (Inno Setup upgrades in place, same AppId) |

Needs the repo to be **public** so the app can read the Releases (D11).

## Phase 14 — New features 🚧 (agreed 31 Oct 2026, D28)
These go into **v1.0.0** together with the new UI (D25). Decided in the
Phase 14 discussion; each step is done when its tests pass and it works in
the real window.

| Step | What | Done when |
|---|---|---|
| 14a ✅ | **Quick wins:** <br>• Settings → model is a **dropdown** of your installed Ollama models (and the known Claude models), with "Other…" to type one <br>• Tracker **List: status filter** (chips with counts, several at once, remembered) <br>• Board: **click a column's title** → the List, filtered to that status | the dropdown only offers installed models; filter and column click work |
| 14b ✅ | **Which resumes to compare:** a **default set** in Settings → Resumes (all at first) + a switch **"Ask me for each job"**. On Analyze: "Comparing with 2 of 4 resumes · change" (switch off) or the chips pre-ticked with the defaults (switch on) | step 2 only scores the chosen resumes; the choice survives a restart |
| 14c ✅ | **Short or detailed fit answer** (a setting; *short* keeps every resume quote, which the evidence check needs, and trims the verdict and talking points) + **the verdict written after the judge** (fixes "the verdict mentions a claim the judge rejected") | measured before/after on the same job; the verdict never cites a rejected claim |
| 14d ✅ | **Continue where you left off:** after an interrupted or stopped run, Analyze offers **Continue / Discard**; Continue picks up after the last finished step (from the checkpoint) | a closed run continues without redoing finished steps |
| 14e ✅ | **Follow-up reminders:** jobs in **Applied or Interviewing** for **7 days** (a setting) get a "Follow up?" badge and one tray notification a day; mark as followed up, or snooze. Plus **"Start JobLens with Windows (in the tray)"** | reminders appear on time, once; snooze and done work |
| 14f ✅ | **Quick analyze:** a global shortcut **`Ctrl+Alt+J`** (changeable) opens a small always-on-top box (link + Analyze); the run goes to the background; a **notification with sound** when the draft is ready | works with the main window hidden in the tray |
| 14g ✅ | **Resume-improvement prompt**, on demand only: a "Generate resume prompt" button after each run and in the job's details. Built from the analysis with **no AI call**. Your resume isn't in it: you paste yours into the other AI with it. Rules in the prompt: rephrase only real experience, never invent any. Shows **keyword coverage** (e.g. 9 of 14 requirements), not an "ATS score". At **≥ 95 % coverage and no gaps** it says your resume already fits, with a small "Generate anyway" | the prompt is correct for a job; no LLM call is made |
| 14h ✅ | **Your notes per job:** notes, an interview date, a contact, in the job's details | saved in the tracker, shown on the card |
| 14i ✅ | **Export:** the tracker to **CSV**; a cover note to **.txt, .docx and .pdf** | the files open in Excel / Word / a PDF viewer |
| then ✅ | **v1.0.0:** merge `version-2` → `main` after the D3 checks, release; 0.3.2 users get it through Settings → Updates | |

Not doing: a **"nearly identical resumes" hint** (dropped by you: resumes
for different countries are meant to differ, and you know which fits).
**Compare models on saved jobs** stays a developer idea (`compare_models.py`).
**A Windows Widgets-board widget**: not realistic for this app (needs a
packaged Store-style app); the 14f shortcut window gives the same thing.

## Phase 15 — Output quality + cleanup 🟡 (proposed 3 Nov 2026, waiting for your OK)
**Why:** testing with a friend's resume (jobs 14–17 in the repo tracker) and
reading the 35 cover notes in the installed app showed wrong gaps, research
about the wrong company, and repetitive cover notes. **Rule for this phase:
measure first.** Build the eval set (15a), record a baseline, then change
one thing at a time and re-run the evals after each change.

### What the data showed (checked, 3 Nov)
| # | Finding | Evidence |
|---|---|---|
| F1 | **Nice-to-haves are dumped into gaps without being checked.** Job 16: all 8 nice-to-haves (OpenCV, ArUco, inverse kinematics, FFT, PyTorch/scikit-learn, PCB/soldering...) are listed as missing, but every one is in the resume | `fit_json` job 16 vs the resume text |
| F2 | **The quote check fails on text the PDF glues together.** The PDF reads `LanguagesEmbedded C/C++, C, Python`, so the quote `Languages: Embedded C/C++, C, Python` scores 3 of 4 words (< 80 %) and is rejected. C/C++/Python, the most basic requirement, was lost in jobs 16 and 17 | `fit.is_evidence_in_resume`, `rejected_matches` |
| F3 | **A rejected quote disappears.** It's neither proven nor a gap, so the score never sees that requirement (job 16: 2 of the 10 requirements vanished) | `fit.verify_analysis` |
| F4 | **The judge rejects exact matches for invented reasons.** "HTTP/REST APIs and JSON" with the quote "HTTP/REST, JSON telemetry" was rejected ("not in an embedded context") | `unsupported_matches`, job 17 |
| F5 | **The writer picks weak quotes.** "Embedded debugging" was quoted as "technical problem-solving" (rightly rejected), though "DHT retry/fault handling", "Troubleshooting" and "rework, multimeter" are in the resume | job 17 |
| F6 | **Gaps are trusted without any check** (only matches are verified), and invented gaps count as required: "Firmware development in Embedded C" is in neither list of job 17 | job 17 `missing_skills` |
| F7 | **The score caps at ~77 when every requirement is met** but nice-to-haves are missing (8 / (8 + 0.3 × 8)); and "3+ years" was accepted from a student project (job 14) | `compute_fit_score` |
| F8 | **Research describes a different company.** Nexora: a $725M sale and a crypto token of an unrelated Nexora; Vertex: "2,106 employees" and a scam alert of unrelated Vertex firms. The URL check only proves a URL was in the search results, not that it's about this employer | `company_json`, jobs 16 and 17 |
| F9 | **Cover notes repeat one project and misplace it.** 23 of 35 notes mention CodeLens, some in the wrong place ("As a Software Engineering Intern, I built CodeLens", "At my university...", "At Tap Academy, I built a code review tool that reduced DB latency..."). Openings are near-identical ("I'm excited to apply ... aligns with my passion") | installed app's `cover_notes/` (read only) |
| F10 | **Talking points are never checked** but feed the cover note (job 14: "Experience with cloud-connected IoT platforms", which the judge had rejected) | `draft_cover_note` |
| F11 | **Every launch leaves a WebView2 profile in %TEMP%**: 20 folders, 162 MB | `%TEMP%\tmp*\EBWebView` |
| F12 | **`checkpoints.db` is never pruned**: 43 runs, 713 checkpoints, 8.5 MB with the WAL, though only the latest run can be continued (D30) | installed `checkpoints.db` |
| F13 | **Stop/Quit can't end a call while the model reads the prompt** (found 1 Nov, not fixed yet) | Ollama `server.log`: a 25 min 20 s request |

Not true, or not about JobLens: the whole resume is sent (4,881
characters, nothing cut), and project evidence *is* used (most proven
matches quote projects). The "job description generation" issues are
about the test postings another AI wrote, not about JobLens.

### Steps
| Step | What | Done when |
|---|---|---|
| 15a ✅ | **Eval set + runner** (`evals/`, personal files git-ignored). Each case = resume + posting + **hand labels per requirement** (proven / partial / missing). `python -m evals.fit` runs **only step 2** (no research, no cover note), 3 times per case, and reports gap precision/recall (false gaps = F1), match precision, score vs expected, run-to-run stability, time and tokens. Start with ~8 cases: your 4 tests, a full match, a partial, a low match, a project-only resume. `--model` compares models (replaces `compare_models.py`) | baseline numbers recorded in progress |
| 15b | **Code owns the requirement list.** Instead of "list matches and gaps", the model gets the job's numbered requirements (required + nice, de-duplicated in code) and answers each one: `proven / partial / missing` + quote + why, in batches of ~6 (an 8B model gets lazy on 19 items at once). No requirement can be skipped (F1, F3, F6) | false gaps ≤ 10 % on the eval set; nothing skipped |
| 15c | **Fair checks.** (1) Clean the PDF text (bullets `�` → `•`, a space between glued words) and also accept a quote whose letters appear in the resume once spaces are ignored (F2). (2) A failed quote becomes **"uncertain"**: shown, never lost (F3). (3) **Second look at gaps:** if a gap's key terms (OpenCV, FFT, SQLite...) appear in the resume, those resume lines are sent back for that requirement (F1, F6). (4) The judge sees the quote's whole resume line and answers proven / partial / no; an exact-term quote isn't rejected for "context" (F4, F5). (5) "N+ years" requirements: projects count as partial at most (F7) | each check has a unit test; the eval numbers improve, or the change is dropped |
| 15d | **The score shows two coverages:** required (proven 1, partial 0.5) and nice-to-have; overall = 80 % required + 20 % nice. The breakdown and every gap say why (F7) | all-required-met cases score ≥ 80 |
| 15e | **Research must be about this employer.** The posting's own "about us" comes first; a search result counts only if it matches the company name **and** something from the posting (website, location, industry). No match, or "(Fictional)" in the name → "No reliable research found", and the cover note uses only the posting (F8) | Nexora/Vertex give "no reliable research"; real companies unchanged |
| 15f | **Better cover notes.** Code picks the 2–3 achievements whose resume lines best match *this* job's verified requirements (so CodeLens appears only where it fits); each is passed with its section and employer, so it can't move to the wrong place. Talking points are checked like matches (F10). More banned openings. A new check: an employer or role named next to a project must belong to that project in the resume (F9) | on the eval jobs: no project in > 50 % of notes, no misplaced project |
| 15g | **Stop and Quit** (F13): Stop closes the AI request's connection (Ollama then cancels at once, as its log shows); Quit marks the run interrupted and exits after a short grace; optionally unload the model (`keep_alive: 0`) | with a deliberately slowed model, Stop during prompt reading frees the GPU in seconds |
| 15h | **Disk:** one fixed WebView2 profile in the data folder instead of a new one per launch, plus a one-time cleanup of old leftovers (F11); keep checkpoints only for continuable runs and compact the file at exit (F12); skip tracing for the session when Langfuse doesn't answer at start (no endless "Failed to export spans"). **The run log records whether Langfuse was reachable**, so Evals shows "no trace (Langfuse wasn't running)" instead of a link that gives "Session not found" (3 Nov: 40 runs since 31 Oct are marked "langfuse", but none reached it) | `%TEMP%` gains nothing per launch; `checkpoints.db` stays small |
| then | **v1.1.0** after the D3 checks | |

Order: 15a → 15b, 15c, 15d (re-run the evals after each) → 15e → 15f;
15g and 15h are independent and can go any time. Step 2 will get slower
with 15b; the evals measure by how much, and the batch size is tuned on them.
