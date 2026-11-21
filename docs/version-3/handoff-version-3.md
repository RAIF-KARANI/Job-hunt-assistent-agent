# Handoff — JobLens version 3

Last updated **21 Nov 2026**. Read this first when picking the work up
again (a new chat, a new machine, or after a break). It says where
everything is, what is decided, what is waiting, and the rules the work
follows.

Plan: [plan-version-3.md](plan-version-3.md) · Decisions:
[decisions-version-3.md](decisions-version-3.md) · Progress:
[progress-version-3.md](progress-version-3.md) · Features of the new look:
[features-version-3.md](features-version-3.md)

---

## 1. Where things stand (one minute)

| | |
|---|---|
| Released | **v1.2.0** (16 Nov 2026): https://github.com/RAIF-KARANI/Job-hunt-assistent-agent/releases/tag/v1.2.0 |
| `main` | `d90dea6`, the same as `version-2` (v1.2.0) |
| Working branch | **`version-3`**, pushed. Phases 17 (new look) and 18 (Rust window) are done |
| Open pull requests | none |
| Tests | 499 pass (`.venv\Scripts\python -m pytest`); also `scripts/build_installer.py --test-install` and `scripts/check_real_update.py --old 1.2.1 --new 2.0.0` |
| Released | **v2.0.0** (22 Nov 2026). Next: Phase 20 when you want it (on hold, E8) |
| Waiting on you | the release number (E5) and "Match Windows" (E4); neither blocks Phase 19 |

## 2. Version 3 in short

| # | Phase | Status |
|---|---|---|
| 17 | **New look**: your glass reference, adapted to JobLens, every screen | ✅ done 17 Nov |
| 18 | **Rust (Tauri) window**: adopted 17 Nov (E2); every window feature moved to Rust (18d) | ✅ done 17 Nov |
| 19 | **Your features** (E7): backup, interview calendar, insights, resume tailoring | ✅ done 21 Nov |
| 20 | **Interview practice**: model-written questions and answers, checked against the resume | ⏳ last (your choice) |

**One release at the end** (E1), proposed as **v2.0.0** (E5). The agent stays
Python whatever happens in Phase 18; only the window/tray/updater shell
could move to Rust.

## 3. Open questions (answer these to unblock work)

1. ~~The mockup (E3)~~ ✅ approved 16 Nov.
2. ~~Light theme (E4)~~ ✅ both themes in glass. Still open inside it:
   keep "Match Windows" as a third choice (it is kept for now).
3. ~~"Clearly better" for Rust (E2)~~ ✅ adopted 17 Nov.
4. **Release number (E5):** 2.0.0?
5. ~~Your feature list (Phase 19)~~ ✅ chosen 21 Nov (E7).

When one is answered: record it in `decisions-version-3.md` (✅ + date),
update the plan's status column, commit and push.

## 4. The mockup

- **Link:** https://claude.ai/artifact/94ZzgwybxR8ZHdWtKnEUt4 (private to
  you until you share it from its Share menu).
- **Source in the repo:** [mockup/](mockup/): `canvas.json` and four
  artboards (`Main.dc.html` = Dashboard, `Tracker.dc.html`,
  `Analyze.dc.html`, `Evals.dc.html`), each 1440 × 1240, linked by the
  sidebar.
- **To change it:** edit the files in `mockup/` and republish to the same
  link (Artifact tool, `url` = the link above; read it first). Don't
  publish from a Windows 8.3 short temp path; that was refused.
- **What each screen shows**
  - *Dashboard:* gradient KPI cards, the job galaxy restyled, the selected
    job, Ready to apply, time per step, status bars, safety nets.
  - *Tracker:* the board, the two reminders, a job's details with
    "Did you apply?".
  - *Analyze:* a run in the middle: steps, live log, the cover note slot.
  - *Evals:* tiles, gradient token bars, pass rate by model, the models
    table with cost.

### How your reference was adapted (E3)
| Reference | JobLens | Why |
|---|---|---|
| Profile + avatar | Model status (ready / working, which model) | no accounts in JobLens |
| Notifications bell | Reminders (follow-ups, "Did you apply?") | that's what JobLens notifies about |
| Top-bar search | Search jobs | today only the Tracker has it |
| White text on gradient cards | Dark text (switch `kpiInk` in the mockup shows white) | white is ~2.5:1 there |
| Muted `#71717A` | `#8E8E99` | 3.2:1 → 4.8:1 on a card |
| Tailwind, Recharts, Framer Motion | not added | your prompt: no unnecessary dependencies; the app works offline |

## 5. The design reference (kept here because `referance/` is not committed)

`referance/` stays untracked: it also holds the Gemini key screenshot.
The two design files in it are `Glassmorphism Dashboard Design Kit.png`
and `ui promt`. Their tokens:

| Group | Values |
|---|---|
| Accents | blue `#60A5FA`, purple `#A78BFA`, pink `#F472B6`, orange `#FB923C`, yellow `#FACC15` |
| Backgrounds | main `#0B0F17`, secondary `#131A29`, card `#1E2433`, elevated `#2A3245` |
| Text | primary `#FFFFFF`, secondary `#A1A1AA`, muted `#71717A` (→ `#8E8E99` in JobLens) |
| Border | `rgba(255,255,255,0.10)` |
| Glass | `rgba(255,255,255,0.06)`, `backdrop-filter: blur(12–24px)` |
| Gradients | blue→purple, purple→pink, pink→orange, orange→yellow; only for KPI cards, active nav, main buttons, chart accents, selected items |
| Type | Inter. Page 28–32 bold, section 20–24 semibold, card 16–18 medium, body 14–16, labels 12–14, KPI 18–24 semibold |
| Radii | cards 16–24, buttons 12–16, inputs 10–12 |
| Motion | subtle: page transitions, card hover lift, nav active state, chart entrance, modal/dropdown |

The prompt's own last rule: plan first, then change the app step by step
with every feature still working. That is how Phase 17 is laid out.

## 6. Notes for each phase

### Phase 17: new look
- **Frontend:** React 19 + TypeScript + Vite in `frontend/`, built into
  `desktop_web/web/` (`cd frontend; npm ci; npm run build`).
- **Styles are plain CSS** in `frontend/src/styles/`: `tokens.css`
  (colours, dark + light), `base.css`, `controls.css`, `app.css`, then one
  file per screen (`dashboard`, `tracker`, `analyze`, `evals`,
  `settings`, `quick`, `resume`). Step 17b starts in `tokens.css`.
- **Fonts (since 17b):** Inter (`@fontsource-variable/inter`, one variable
  file) and IBM Plex Mono, bundled, offline. Sora and IBM Plex Sans are
  gone.
- **Shell (since 17c):** `app/Sidebar.tsx` (two groups from `NAV_GROUPS` in
  `routes.ts`), `app/TopBar.tsx`, `app/QuickActions.tsx` (Ctrl K),
  `app/useReminders.ts` (the number on Tracker).
- **Accordions (since 17e):** `app/Fold.tsx` (`<Fold title digest defaultOpen flat>`),
  styled by `.acc` in `controls.css`. Use it for anything that folds.
- **Focus check (since 17j):** `scripts/check_focus.js` tabs through each
  screen and lists controls with no visible focus change.
- **Contrast check (since 17i):** `scripts/check_contrast.js` measures every
  piece of text in both themes against the glass; see its first lines.
- **Component sheet:** `#/components` (not in the menu) shows every shared
  piece; use it to check a token change in both themes.
- **How the glass is built:** `body` paints `--backdrop`; `.shell` is the
  frosted window (`--window`); `.card`, `.tile`, `.glass` and dialogs are
  frosted layers. Surfaces are see-through, so anything that must hide
  what is under it uses `--surface-raised`.
- **Screenshots without the real window:** `npm run dev` in `frontend/`
  serves the UI with made-up data (the mock bridge), safe to capture.
- **Screens by folder:** `app/` (shell, `Sidebar.tsx`, `routes.ts`,
  `useTheme.ts`), `dashboard/` (+ `galaxy/`: `Galaxy3D.tsx`, `scene.ts`,
  `OrbitMap.tsx`, `declutter.ts`, `layout.ts`), `tracker/`, `analyze/`,
  `evals/` (`RunCharts.tsx`, `PassRateChart.tsx`), `settings/`, `setup/`,
  `quick/`, `resume/`.
- **Chart colours (since 17g)** are `--series-1..4` and `--rate-*` in
  `tokens.css`: the accents stepped until the palette validator passes
  (dark `#4c8df6 #d9621a #9374f7 #b08408`, light `#2563eb #ea580c #7c3aed
  #a67c00`). Keep the order: blue next to purple fails for colour-blind
  readers. Any new chart colour must pass the validator too (the
  `dataviz` skill's `scripts/validate_palette.js`).
- **The galaxy stays** (your choice): restyle the 3D view, the flat map,
  and the "3D off" fallback together.
- **Look at it in the real window**, not only the browser:
  `.venv\Scripts\python -m desktop_web` (or `--dev` with `npm run dev`).
  Check sizes from 720 px wide to a 2560 px monitor.
- `frontend/.impeccable/` is a design tool's working folder: leave it
  untracked.

### Phase 18: Rust spike
- **The Rust window (since 18d1)** is `desktop_tauri/` (README there); its
  Python side is `desktop_web/engine.py`, the start-up work both windows
  share is `desktop_web/startup.py`. Run it from source:
  `desktop_tauri/target/release/joblens.exe`. Smoke test: `JOBLENS_SMOKE=out.json`.
- **The spike** is in `spikes/18_tauri/` (README there). Rust is installed
  in `%USERPROFILE%\.cargo\bin`, not on PATH. Build with
  `CARGO_BUILD_JOBS=2` to keep memory down.
- **Numbers to beat (v1.2.0):** installer 68 MB, app folder 161 MB,
  window ready in about 3 s.
- Only the shell could move: window, tray (`desktop_web/tray.py`),
  global shortcut, updater, the JS ↔ Python bridge
  (`desktop_web/bridge.py`). The agent (`job_agent/`) stays Python and
  ships beside it (a sidecar).
- If adopted, the real update test (`scripts/check_real_update.py`) must
  be redone for the new shell before the release.

### Phase 19: your features (E7)
- **Backup:** `job_agent/backup.py`; Settings → Your data
  (`settings/BackupCard.tsx`). Automatic ones in `APP_HOME\backups`
  (weekly from `startup.weekly_backup`, and in `install_update`). No API
  keys, no paused runs.
- **Interview calendar:** `job_agent/interviews.py`; reminders from the tray
  loop (`tray.interview_reminders`, every 5 min, shown even with the window
  open). A notification can open one job: `tracker?job=12` (the Rust
  `navigate` accepts `? = &` since 19b).
- **Insights:** `job_agent/insights.py` over the `status_changes` table
  (written only by `tracker.update_status`; an undo within 10 min takes the
  change out). Screen `insights/Insights.tsx`. Under 5 applications in a
  group: counts, no rate.
- **Resume tailoring:** `job_agent/tailoring.py` (one model call, then the
  code check); UI `resume/TailorSection.tsx` in the Resume prompt dialog;
  numbers in Evals from the `tailoring_log` table. Read the progress log's
  19d table before changing the prompt: stricter wording made qwen3:8b
  copy lines unchanged.
- **Measuring with the real model:** set `TRACING=off` for a script (the
  repo `.env` has Langfuse on); run one job after another.

### Phase 20: interview practice
- 1.2.0's prep sheet (`job_agent/interview_prep.py`) is code only, no
  model, on purpose (D43). Practice questions + answers would use the
  model and must be checked against the resume the way the cover note
  is: no claim the resume doesn't show. Measure on a few real jobs.

## 7. Working rules (yours, carried over from version 2)

- **Before each commit:** `git status`; check `version-3` is up to date
  with `main` (`git fetch`, compare); check for open PRs (`gh pr list`).
- **Commit and push on `version-3` after each step.**
- **No CI** (Actions minutes are used up): run the checks locally.
  Before merging: pytest, look at the app, `scripts/build_installer.py
  --test-install`, `scripts/check_real_update.py`.
- **At the very end:** merge into `main`, then one release.
- **Docs in the same turn as the decision:** plans, decisions (E1, E2…),
  progress, all in `docs/version-3/*-version-3.md`.

## 8. Handle with care

- **The Gemini API key** is only in `.env` (git-ignored). Never print it,
  copy it into docs, or commit it. Same for any other key.
- **`referance/`** stays untracked (key screenshot).
- **Your installed JobLens** (`%LOCALAPPDATA%\JobLens`) is hands-off:
  copy data from it, never change it.
- **Resumes in `data/`** include two friends' resumes; the test tracker
  has 22 jobs copied from your installed app. Keep them out of
  screenshots and anything shared.
- Use **`.venv\Scripts\python`**, not the system Python.

## 9. Commands

```powershell
.venv\Scripts\python -m pytest                       # 471 tests
cd frontend; npm ci; npm run build; cd ..            # UI -> desktop_web\web\
.venv\Scripts\python -m desktop_web                  # run from source (repo data\ and .env)
.venv\Scripts\python -m desktop_web --dev            # with `npm run dev`: live React edits
.venv\Scripts\python scripts\build_installer.py --test-install
.venv\Scripts\python scripts\check_real_update.py    # before a release
.venv\Scripts\python -m evals.fit run --runs 3       # fit evals (baseline: 83 % accuracy)
```

## 10. Things learned the hard way

- **Two apps, one port:** the installed app and the source app both used
  42001, so the source window showed the old UI. `free_page_port()` now
  takes the first free port.
- **Fit evals and low memory:** a full eval run was killed once; run it in
  halves and merge the results.
- **Gemini free tier:** a small daily limit per model (gemini-3.5-flash
  ran out after about 20 calls; 3.1-flash-lite finished a 38-call job).
  A run that hits the limit stops as `out_of_quota` and can be continued.
- **Running resumes in parallel was slower** (16h dropped): one after
  another is fastest on this machine.
- **Shell quoting on Windows:** for edits with tricky quoting, write a
  small script to the scratchpad and run it, instead of inline commands.

## 11. Left for you (you said you'd do these)

- Update your own JobLens to 1.2.0 (the app offers it).
- The Windows shutdown test with 1.2.0 installed.
- Try OpenAI with your key.
- Gemini: choose a Flash Lite model, or turn on billing.
- Answer section 3, and write your Phase 19 feature list.
