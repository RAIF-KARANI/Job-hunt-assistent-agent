# Features — JobLens version 3 look

What the new look does, as designed in the mockup on 16 Nov 2026. It is the
checklist for Phase 17: each feature here has to work in the real app
before the step that owns it is done.

Mockup: https://claude.ai/artifact/94ZzgwybxR8ZHdWtKnEUt4 · source in
[mockup/](mockup/) · Plan: [plan-version-3.md](plan-version-3.md) ·
Decisions: [decisions-version-3.md](decisions-version-3.md) · How we got
here: [progress-version-3.md](progress-version-3.md)

**Status of everything below: designed in the mockup, not built.** Nothing
in the app has changed. The mockup was not checked on screen by Claude;
you review it.

Legend: 🎨 designed · ❓ needs a check before it can be built

---

## 1. Everywhere

| # | Feature | What it does | Status |
|---|---|---|---|
| F1 | **Frosted window** | The app window is frosted glass: what is behind it shows through, blurred. The sidebar lets the most through; the work area is darker so text stays readable | 🎨 ❓ |
| F2 | **Frosted layers** | Panels, cards, the Tracker detail sheet and the quick actions box are each a lighter frosted layer over the window | 🎨 ❓ |
| F3 | **Your colours, one job each** | Fit score is one blue scale (bright = strong, dim = weak). Each status keeps one colour on every screen: Researched grey, Cover note ready blue, Applied purple, Interviewing orange, Offer yellow, Rejected pink | 🎨 |
| F4 | **Gradient cards** | Translucent gradient cards with white text for the headline numbers. A switch in the mockup (`kpiFill`: tinted / vivid) shows the brighter version | 🎨 |
| F5 | **Accordions** | Less important content folds away. A closed accordion still shows a one-line summary, so the main number is visible without a click | 🎨 |
| F6 | **Keyboard and motion** | Focus rings, text selection and scrollbars match the look. With "reduce motion" on in Windows, nothing moves | 🎨 |

**To check (❓):**
- F1: showing the real desktop needs a see-through window with the
  Windows 11 backdrop. Whether today's Python window can do it, or only a
  Tauri one, is a Phase 18 question. Fallback: the same frost over the
  app's own gradient.
- F1, F2: many blurred layers cost graphics time. Measure on this PC in
  step 17b.

## 2. Sidebar

| # | Feature | What it does | Status |
|---|---|---|---|
| F7 | **Two labelled groups** | "Job search": Dashboard, Analyze, Tracker. "Agent": Evals, Settings. Every item has an icon | 🎨 |
| F8 | **Agent group folds** | Closed on the job-search screens (one row with an arrow), open on Evals | 🎨 |
| F9 | **Model status row** | One row at the bottom: status dot, model name, "Ready". During a run: "Step 2 of 5" | 🎨 |
| F10 | **Reminder count** | The number of things waiting for you, on the Tracker item | 🎨 |

Moved out of the sidebar: the version number and "On this PC · free and
private" (both would live in Settings).

## 3. Top bar

| # | Feature | What it does | Status |
|---|---|---|---|
| F11 | **Search widget** | A small "Search · Ctrl K" button replaces the wide search box, on every screen | 🎨 |
| F12 | **Quick actions** | Ctrl K, or a click on the widget, opens a box with three groups: **Actions** (Analyze a new job, Confirm applications, Write a follow-up, Export the tracker as CSV), **Go to** (the five pages), and **Jobs** (the three most recent, or every match as you type) | 🎨 ❓ |
| F13 | **Quick actions by keyboard** | Type to filter, Up / Down to move, Enter to open, Esc or a click outside to close | 🎨 |
| F14 | **New analysis button** | On hover or keyboard focus the label changes to "Land the next one" and the plus becomes a lens that keeps scanning. The button's width doesn't change | 🎨 |

**To check (❓):**
- F12: the label says **Ctrl K** because JobLens is a Windows app (you
  said "command K"; that is the Mac name for the same shortcut). Make
  sure Ctrl K doesn't clash with the global shortcut that opens the
  quick-analyze box.
- F12: in the mockup the shortcut works after you click inside the
  screen in Play mode. In the app it would work from anywhere in the
  window.
- F12: the Tracker's old search also looked in contacts and notes. Quick
  actions has to search the same fields, or the Tracker loses that.

## 4. Dashboard

| # | Feature | What it does | Status |
|---|---|---|---|
| F15 | **Pipeline card** | 33 jobs tracked, as one bar split by status, with a count per status | 🎨 |
| F16 | **Do next** | One list of what is waiting for you: the follow-up, "Did you apply?", and the strong fits that are ready to apply | 🎨 |
| F17 | **Job galaxy** | Each job is a dot; closer to the centre is a better fit. The rings sit at fit 75, 55 and 25. A 3D / Map switch | 🎨 |
| F18 | **Selected job** | Attached to the galaxy: fit, what your resume proves, gaps, Open details, Interview prep | 🎨 |
| F19 | **How JobLens is doing** | Median run, evidence verified, cover notes approved, time per step, safety nets caught. The 7 days / 30 days / All switch sits here because it only changes these numbers | 🎨 |

## 5. Tracker

| # | Feature | What it does | Status |
|---|---|---|---|
| F20 | **Needs you** | An accordion (open): confirm you applied, then follow up | 🎨 |
| F21 | **Board** | Six columns in the order a job moves. Fit on every card. "Show 9 more" when a column holds more than it shows. "Drop a job here" in an empty column | 🎨 |
| F22 | **Detail sheet** | Leads with the next step for that job (Open posting, Yes I applied, Not yet). Then accordions: Fit (open), Status and tools, Job description | 🎨 |
| F23 | **Board / List, Export CSV** | Kept, in the header | 🎨 |

## 6. Analyze

| # | Feature | What it does | Status |
|---|---|---|---|
| F24 | **Link and Stop** | One row: the job link, and Stop while a run is going | 🎨 |
| F25 | **Run spine** | The five steps in order with a progress bar, the time so far and the usual time. The resumes being compared sit inside step 2 | 🎨 |
| F26 | **Decide inside step 5** | Approve and save, Rewrite with my notes, Reject | 🎨 |
| F27 | **Live log** | An accordion (closed) that shows the current line | 🎨 |

## 7. Evals

| # | Feature | What it does | Status |
|---|---|---|---|
| F28 | **A run, step by step** | The agent's five steps in order. Each row: the step's average time as a bar, and its main result | 🎨 ❓ |
| F29 | **Step details** | Step 2 (open): evidence pass rate, made-up quotes caught, claims the judge rejected, pass rate by run. Step 3: invented links and news dates removed. Step 5: cover notes approved | 🎨 ❓ |
| F30 | **Whole-run totals** | Median time, tokens, cost (with "add a price") in the panel's header | 🎨 |
| F31 | **Models compared** | An accordion (open): one row per model | 🎨 |
| F32 | **Tokens by run** | An accordion (closed) | 🎨 |

**To check (❓):**
- F28, F29: which step each safety net belongs to is Claude's reading,
  not taken from the code. Confirm before building.

## 8. Not in the mockup yet

Settings, the setup wizard, the quick-analyze box, the resume screen, the
light theme (E4, open), and the failed / out-of-quota states of a run.
They get the same look in steps 17h to 17j.
