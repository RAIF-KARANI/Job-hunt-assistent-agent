# Features — JobLens version 3 look

What the new look does, as designed in the mockup on 16 Nov 2026. It is the
checklist for Phase 17: each feature here has to work in the real app
before the step that owns it is done.

Mockup: https://claude.ai/artifact/94ZzgwybxR8ZHdWtKnEUt4 · source in
[mockup/](mockup/) · Plan: [plan-version-3.md](plan-version-3.md) ·
Decisions: [decisions-version-3.md](decisions-version-3.md) · How we got
here: [progress-version-3.md](progress-version-3.md)

**Status: built where a row says so; the rest is designed in the mockup
and not built yet.** The mockup was not checked on screen by Claude;
you review it.

Legend: 🎨 designed · ❓ needs a check before it can be built · ✅ built

---

## 1. Everywhere

| # | Feature | What it does | Status |
|---|---|---|---|
| F1 | **Frosted window** | The app window is frosted glass: what is behind it shows through, blurred. The sidebar lets the most through; the work area is darker so text stays readable | 🎨 ❓ |
| F2 | **Frosted layers** | Panels, cards, the Tracker detail sheet and the quick actions box are each a lighter frosted layer over the window | 🎨 ❓ |
| F3 | **Your colours, one job each** | Fit score is one blue scale (bright = strong, dim = weak). Each status keeps one colour on every screen: Researched grey, Cover note ready blue, Applied purple, Interviewing orange, Offer yellow, Rejected pink | 🎨 |
| F4 | **Gradient cards** | Translucent gradient cards for the headline numbers: white text in dark, dark text in light. (The mockup's brighter "vivid" version was not built) | ✅ built (17d) |
| F5 | **Accordions** | Less important content folds away. A closed accordion still shows a one-line summary, so the main number is visible without a click | ✅ built (17e), used on more screens in 17f, 17g |
| F6 | **Keyboard and motion** | Focus rings, text selection and scrollbars match the look. With "reduce motion" on in Windows, nothing moves | 🎨 |

**To check (❓):**
- F1: showing the real desktop needs a see-through window with the
  Windows 11 backdrop. Whether today's Python window can do it, or only a
  Tauri one, is a Phase 18 question. Fallback: the same frost over the
  app's own gradient.
- F1, F2: many blurred layers cost graphics time. Measure on this PC in
  step 17b.

### Themes

| # | Feature | What it does | Status |
|---|---|---|---|
| F33 | **Light mode** | The same screens in clear, light glass: white see-through layers over a bright wallpaper, dark text, darker accent text so it stays readable | 🎨 ❓ |
| F34 | **Light / dark toggle** | A sun / moon button in the top bar of every screen. The choice is saved in your settings. "Match Windows" is still a choice in Settings | ✅ built (17c) |

**To check (❓), light mode:**
- F33: not looked at on screen by Claude. Text over the brightest parts
  of the wallpaper is the thing to check first.
- F34: whether "follow Windows" stays as a third choice (E4, open).

## 2. Sidebar

| # | Feature | What it does | Status |
|---|---|---|---|
| F7 | **Two labelled groups** | "Job search": Dashboard, Analyze, Tracker. "Agent": Evals, Settings. Every item has an icon | ✅ built (17c) |
| F8 | **Agent group folds** | Closed on the job-search screens (one row with an arrow), open on Evals and Settings | ✅ built (17c) |
| F9 | **Model status row** | One row at the bottom: status dot, model name, "Ready". During a run: "Working"; when it waits for you: "Your turn". A click opens Settings | ✅ built (17c) |
| F10 | **Reminder count** | The number of jobs waiting for you (follow-ups and "Did you apply?"), on the Tracker item | ✅ built (17c) |

Moved out of the sidebar: the version number and "On this PC · free and
private" (both would live in Settings).

## 3. Top bar

| # | Feature | What it does | Status |
|---|---|---|---|
| F11 | **Search widget** | A small "Search · Ctrl K" button, top right on every screen | ✅ built (17c) |
| F12 | **Quick actions** | Ctrl K, or a click on the widget, opens a box with three groups: **Actions** (Analyze a new job, Confirm applications, Write a follow-up, Export the tracker as CSV), **Go to** (the five pages), and **Jobs** (the three most recent, or every match as you type) | ✅ built (17c) |
| F13 | **Quick actions by keyboard** | Type to filter, Up / Down to move, Enter to open, Esc or a click outside to close | ✅ built (17c) |
| F14 | **New analysis button** | On hover or keyboard focus the label changes to "Land the next one" and the plus becomes a lens that keeps scanning. The button's width doesn't change | ✅ built (17c) |

**To check (❓):**
- F12: the label says **Ctrl K** because JobLens is a Windows app (you
  said "command K"; that is the Mac name for the same shortcut). Make
  sure Ctrl K doesn't clash with the global shortcut that opens the
  quick-analyze box.
- F12: in the mockup the shortcut works after you click inside the
  screen in Play mode. In the app it would work from anywhere in the
  window.
- ~~F12: the Tracker's search fields~~ Settled in 17e: the Tracker keeps
  its own search box (it filters the board in place), and quick actions
  searches the same fields.

## 4. Dashboard

| # | Feature | What it does | Status |
|---|---|---|---|
| F15 | **Pipeline card** | Jobs tracked, as one bar split by status, with a count per status | ✅ built (17d) |
| F16 | **Do next** | One list of what is waiting for you: the follow-up, "Did you apply?", and the strong fits that are ready to apply. A row opens that job's details | ✅ built (17d) |
| F17 | **Job galaxy** | Each job is a dot; closer to the centre is a better fit. The rings sit at fit 75, 55 and 20 (as before). A 3D / Map switch on the card | ✅ built (17d) |
| F18 | **Selected job** | Attached to the galaxy: fit, what your resume proves, gaps, Open details, Draft a cover note | ✅ built (17d) |
| F19 | **How JobLens is doing** | Median run, evidence verified, cover notes approved, time per step, safety nets caught. The 7 days / 30 days / All switch sits here because it only changes these numbers | ✅ built (17d) |

## 5. Tracker

| # | Feature | What it does | Status |
|---|---|---|---|
| F20 | **Needs you** | An accordion (open): confirm you applied, then follow up. "Show them" lists just those jobs | ✅ built (17e) |
| F21 | **Board** | Six columns in the order a job moves. Fit on every card. "Show 9 more" when a column holds more than it shows. "Drop a job here" in an empty column | ✅ built (17e) |
| F22 | **Detail sheet** | Leads with the next step for that job. Status and Open posting stay in view. Then accordions: Fit (open), Cover note, Your notes, More tools, About the company; then the job description | ✅ built (17e) |
| F23 | **Board / List, Export CSV, the search box** | Kept, in the header | ✅ built (17e) |

## 6. Analyze

| # | Feature | What it does | Status |
|---|---|---|---|
| F24 | **Link and Stop** | One row: the job link, the Analyze button (it shows the running time), and Stop while a run is going | ✅ built (17f) |
| F25 | **Run spine** | One card: "Step 2 of 5", its state, the time so far and the usual time, one bar for the whole run, then the five steps in order. Each step says what it found | ✅ built (17f) |
| F26 | **Decide at step 5** | The draft and Approve and save / Rewrite with my notes / Reject sit directly under the steps, and come into view when the run stops for you | ✅ built (17f) |
| F27 | **Live log** | An accordion (closed) that shows the current line | ✅ built (17f) |

## 7. Evals

| # | Feature | What it does | Status |
|---|---|---|---|
| F28 | **A run, step by step** | The agent's steps in order. Each row: the step's average time as a bar, and its main result | ✅ built (17g) |
| F29 | **Step details** | Compare resumes (open): evidence pass rate, claims checked, fake quotes caught, judge rejections, pass rate by run and by model, your fit-score ratings. Research: searches that failed, invented links and dates removed. Draft: cover notes approved, number warnings, rewrites, your cover-note ratings | ✅ built (17g) |
| F30 | **Whole-run totals** | Median time, tokens, cost (with "add a price") and unfinished runs in the panel's header | ✅ built (17g) |
| F31 | **Models compared** | An accordion (open): one row per model | ✅ built (17g) |
| F32 | **Run by run** | An accordion (closed): tokens per run, agent time per run, and time against tokens. **Recent runs** is an accordion too | ✅ built (17g) |

**To check (❓):**
- ~~F28, F29: which step each safety net belongs to~~ Settled in 17g from
  the code: each check's own description in `job_agent/monitoring.py`
  says what it looks at (the fit analysis, the search results, the cover
  note).

## 8. Not in the mockup yet

Settings, the setup wizard, the quick-analyze box, the resume screen, and the failed / out-of-quota states of a run.
They get the same look in steps 17h to 17j.
