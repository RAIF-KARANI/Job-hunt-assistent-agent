# Progress Log — JobLens version 3

What was done in each version-3 step, what went wrong, and what it
teaches. Plan: [plan-version-3.md](plan-version-3.md) · Decisions:
[decisions-version-3.md](decisions-version-3.md) · Where things stand:
[handoff-version-3.md](handoff-version-3.md)

| Step | Status | Result |
|---|---|---|
| Planning | ✅ | 4 phases (17 new look, 18 Rust spike, 19 your features, 20 interview practice); E1–E5 recorded |
| Mockup | ✅ | 4 linked screens in your glass style: https://claude.ai/artifact/94ZzgwybxR8ZHdWtKnEUt4 (source in [mockup/](mockup/)) |
| Mockup round 2 | ✅ | same link, elevated after your "looks AI slop" review (see below) |
| 17a Your review of the mockup | 🟡 | waiting for you |
| 17b–17j | ⏳ | after your go |
| 18 Rust spike | ⏳ | |
| 19 Your features | 🟡 | waiting for your list |
| 20 Interview practice | ⏳ | last |

---

## Planning ✅ (16 Nov 2026)

### Starting point
- **v1.2.0 released** the same day (Phase 16). `main` = `version-2` =
  `d90dea6`. 471 tests pass.
- Branch **`version-3`** made from `main`.

### Your answers
| Question | Your answer |
|---|---|
| Redesign | A new look; see 2–3 directions as mockups first |
| Style | Your reference image + prompt in `referance/` |
| Rust | Goals: smaller, faster app; learn Rust. Adopt only if clearly better |
| Features | Interview practice, last; the rest is your list (to come) |
| Release | One big release |
| Job galaxy | Keep it, restyle it |

### What was done
- [plan-version-3.md](plan-version-3.md) and
  [decisions-version-3.md](decisions-version-3.md) (E1–E5). README links
  them. Commit `6f57df0`.

## Mockup ✅ (16 Nov 2026)

### What was done
- A Design canvas of 4 page-sized screens (1440 × 1240), linked by the
  sidebar like the app: **Dashboard, Tracker, Analyze, Evals**. Built from
  JobLens's real screens, wording and kinds of numbers. Nothing in the app
  changed.
- Your reference was followed, and adapted where it doesn't fit JobLens
  (see E3): model status instead of a profile, the bell is the reminders,
  dark text on the gradient cards, a lighter muted grey, no new libraries.
- The source is kept in [mockup/](mockup/) (the copy in the session's
  temp folder won't last).

### Learned
- The Artifact publish refused the Windows short (8.3) temp path; the
  long path works.
- White text on the bright gradient cards is about 2.5:1; dark text is
  needed. The mockup has a switch (`kpiInk`) to compare.

## Mockup round 2 ✅ (16 Nov 2026)

You said the first mockup looked like AI slop. Same link, all four screens
rebuilt inside your brief (Inter, your five accents, glass, gradient KPI cards).

### What changed
- **KPI cards:** translucent gradient over the dark glass, with white text
  that passes contrast, closer to your reference. The old bright fill is
  still there behind the `kpiFill` switch (tinted / vivid).
- **One colour job per colour:** fit is now one blue scale (bright = strong
  fit, dim = weak) everywhere: galaxy, chips, Ready to apply. Status
  colours stay fixed per status. Before, the rainbow was used for both.
- **Galaxy:** the rings are now drawn where the fit thresholds really fall
  (75, 55, 25), so the dots and rings agree; 3D / Map switch added.
- **Less boxing:** no cards inside cards. Ready to apply, Safety nets and
  the Evals numbers are rows or one strip; hover lift only on things you
  can click.
- **Data stories:** "Compare resumes" is highlighted as about two thirds of
  a run; applications are one stacked bar with counts.
- **Details:** drawn check icons instead of text glyphs, a step timeline in
  Analyze, sensible empty columns ("Drop a job here"), themed focus rings,
  selection and scrollbars, neutral shadows instead of coloured glows.
- One shared style block in every screen, so the four look like one app.

## Mockup round 3 ✅ (16 Nov 2026)

You asked for better hierarchy, with things grouped by how they relate.
Same link. Checked against Impeccable's layout guide (updated to 4.9.2).

### What changed
- **Dashboard** is two groups. **Your job search** comes first: the
  pipeline (33 jobs, by status) as the lead card, then **Do next**
  (both reminders and Ready to apply in one list), then the galaxy with
  the selected job attached as one split panel. **How JobLens is doing**
  is second and quieter: three smaller KPI cards, then Time per step and
  Safety nets side by side in one panel. The 7 / 30 days / All switch
  moved into that group, because it only changes those numbers.
- **Tracker:** both reminders in one **Needs you** strip; search and
  Board/List sit right above the board they filter; columns show how many
  more jobs they hold; the detail sheet asks "Did you apply?" first, then
  status and actions, then fit, then the description.
- **Analyze:** three groups in order, **Job**, **Run** and **Cover note**.
  Stop and the overall progress bar sit with the run; steps and the live
  log are one split panel.
- **Evals:** **Quality** (pass rate, notes approved, pass-rate chart) and
  **Cost and speed** (time, tokens, cost, token chart), then Models
  compared.
- Spacing has a rhythm: 40 px between groups, 16 px inside a group;
  section headings 20 px, panel titles 16 px.

## Mockup: primary button delight ✅ (16 Nov 2026)

On hover (or keyboard focus), **New analysis** on the Dashboard and
Tracker changes to **Land the next one**: the old label slides up and the
new one slides in, the plus turns into a magnifying lens, and the lens
keeps scanning in a loop with a small glint. The button's width doesn't
change, and with reduced motion on, the text still swaps but nothing moves.

## Mockup: frosted desktop glass ✅ (16 Nov 2026)

You asked for a frosted window that lets the desktop show through, and
frosted panels on top of it.

- Each screen now sits on a stand-in desktop wallpaper (your five accent
  colours, with a few sharp shapes so the blur is visible). The app is a
  rounded window floating on it.
- The window is frosted: the wallpaper shows through, blurred. The
  sidebar lets the most through; the work area is darker so text stays
  readable.
- Panels, KPI cards, the model card, Tracker cards and the Tracker detail
  sheet are frosted layers of their own, each a bit lighter than what is
  under it.
- The faintest grey text went from `#8E8E99` to `#9C9CA8`, because the
  background behind it is now lighter in places.

### To check before building it (not checked yet)
- In the mockup the desktop is a picture. In the real app, showing the
  real desktop needs a see-through window with the Windows 11 backdrop
  (Mica / Acrylic). Whether today's Python window can do that, or only a
  Tauri one, is a question for the Phase 18 spike. Fallback: the same
  frosted look over the app's own gradient.
- Many blurred layers cost graphics time; measure on this PC in 17b.

## Mockup round 4 ✅ (16 Nov 2026)

You asked for a cleaner hierarchy: follow the order of operations, and
fold less important content into accordions. Same link.

- **Dashboard:** the pipeline leads, as five stages in the order a job
  moves (Researched → Cover note ready → Applied → Interviewing → Offer),
  each with its count and what is waiting there. Then **Do next** as
  three numbered steps: 1 Apply (the 5 strong fits), 2 Confirm you
  applied, 3 Follow up. **Job galaxy** is an accordion (open). **How
  JobLens is doing** is an accordion (closed), and its closed line still
  shows the three headline numbers.
- **Tracker:** search and Board/List moved into the header. **Needs you**
  is an accordion (open), in order: confirm, then follow up. The detail
  sheet leads with the next step for that job; **Fit** (open), **Status
  and tools** and **Job description** (closed) are accordions.
- **Analyze:** one spine of the five steps. The resumes being compared
  sit inside step 2, and the approve / rewrite / reject buttons sit inside
  step 5. **Live log** is an accordion (closed) that shows the current
  line.
- **Evals:** "Is it right?" first and biggest, "What does a run cost?"
  second. Then accordions: pass rate by run (open), Models compared
  (open), Tokens by run (closed).
- A closed accordion always shows a one-line summary, so nothing
  important is hidden behind a click.
- To avoid cards inside cards, the three agent numbers inside the
  accordion are plain figures now; the gradient card style is kept for
  the pipeline at the top.

## Mockup round 5 ✅ (16 Nov 2026)

You said the order-of-operations idea was meant for **Evals**, not the
Dashboard, and that you didn't like the round 4 Dashboard.

- **Dashboard:** put back as it was before round 4 (frosted, with the
  button hover): pipeline card, Do next, galaxy with the selected job,
  then How JobLens is doing with its three gradient cards.
- **Evals:** now follows the agent's own order. One panel, "A run, step by
  step": 1 Read the posting, 2 Compare with your resumes, 3 Research the
  company, 4 Save, 5 Draft the cover note. Each row shows the step's
  average time as a bar and its main result. Steps 2, 3 and 5 open as
  accordions: step 2 (open) holds the evidence pass rate, the two
  safety-net counts and the pass-rate chart; step 3 the invented links
  and dates removed; step 5 the notes approved. Models compared (open)
  and Tokens by run (closed) follow.
- Tracker and Analyze are unchanged from round 4.

### Assumption to confirm
- Which step each safety net belongs to is my reading: made-up quotes and
  judge rejections under step 2, invented links and news dates under
  step 3. Check against the code before building.

## Mockup: cleaner sidebar ✅ (16 Nov 2026)

You said the left menu was overwhelming.

- Two labelled groups. **Job search**: Dashboard, Analyze, Tracker.
  **Agent**: Evals, Settings. Every item keeps its icon.
- **Agent** folds: it is closed on the job-search screens (one row with
  an arrow) and open on Evals.
- The model card (three lines) and the version line became one row at
  the bottom: status dot, model name, "Ready" (or "Step 2 of 5" during a
  run). The version number would move to Settings.

## Mockup: search widget and quick actions ✅ (16 Nov 2026)

You said the search bar at the top was overbearing.

- The wide search box is now a small **Search · Ctrl K** button, on all
  four screens.
- Ctrl K or a click opens **quick actions**: Actions, Go to, and Jobs.
  Type to filter, Up / Down to move, Enter to open, Esc to close.
- The label is Ctrl K, not Command K, because JobLens runs on Windows.
- In the mockup, press Play and click inside the screen first; then the
  shortcut works. The mockup's "Quick actions" switch shows the box open
  without clicking.
- The logic of each screen was run once outside the browser (it filters
  and groups correctly); how it looks was not checked.

## Features file ✅ (16 Nov 2026)

[features-version-3.md](features-version-3.md): every feature of the new
look (F1 to F32), by screen, with what still needs a check before
building. It is the checklist for Phase 17.

## Mockup: light mode and toggle ✅ (16 Nov 2026)

You asked for a light mode in a fully see-through style, and a light /
dark toggle. Decision E4 is now settled: both themes, both glass.

- All four screens have a light mode: clear white glass over a bright
  wallpaper, dark text, and darker versions of the accent text colours.
- A sun / moon button sits in the top bar next to Search. The choice is
  remembered and carries across the four screens.
- In the mockup's Tweaks, **theme** (auto / dark / light) sets a screen
  without pressing Play; "auto" uses what the toggle last chose.
- How it was done: every hard-coded colour became a variable with a dark
  and a light value. Dark mode should look the same as before, apart from
  a few text tints that were merged into one shade.
- The logic of each screen was run once outside the browser; neither
  theme was looked at on screen. A copy of the screens from before this
  change is in git (commit fb559d6) if dark mode came out worse.
