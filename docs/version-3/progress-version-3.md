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
| 17a Your review of the mockup | ✅ | approved after several rounds: "I am happy with the design" |
| 17b Tokens and base components | ✅ | both glass themes in the real app; component sheet at `#/components` |
| 17c The shell | ✅ | grouped sidebar, top bar, quick actions (Ctrl K), light/dark switch |
| 17d The Dashboard | ✅ | pipeline card, Do next, galaxy joined to the selected job, agent numbers |
| 17e The Tracker | ✅ | Needs you, the board, the detail sheet in folds, dialogs |
| 17f Analyze | ✅ | one column: the link, the run card with five steps, your decision, the log folded |
| 17g–17j | ⏳ | 17g (Evals) is next |
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
look (F1 to F34), by screen, with what still needs a check before
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

## 17a Your review ✅ (16 Nov 2026)

"good lets start building i am happy with the design reference artifact."
The mockup is the reference; [features-version-3.md](features-version-3.md)
is the checklist.

## 17b Tokens and base components ✅ (16 Nov 2026)

The first change to the app itself.

### What was done
- **`tokens.css` rewritten** for the glass look, dark and light: the five
  accents, the gradient for the main button, see-through surfaces, the
  backdrop, the frost recipe, the one-blue fit scale, one colour per
  status. The token names the screens already use were kept, so every
  screen picked up the new look without being touched.
- **Inter** replaces Sora and IBM Plex Sans (bundled, works offline).
  IBM Plex Mono stays for the log. Licence notices updated.
- **Base and controls:** the gradient main button, glass secondary
  buttons, inputs with a soft focus ring, the segmented switch, badges,
  themed selection and scrollbars.
- **Glass:** the page background is the backdrop, the app shell is the
  frosted window, cards and tiles are frosted layers; dialogs, the job
  sheet, toasts and chart tips use a more solid frosted surface so they
  stay readable.
- **Component sheet** at `#/components`: type, buttons, fields, notices,
  tiles, colours, in whichever theme is on.

### Checked
- `npm run build` (types and bundle): passes.
- pytest: 471 pass.
- The real window (`python -m desktop_web --smoke`): starts, and the
  glass shows in it.
- Looked at Dashboard, Tracker, Settings and the component sheet in dark
  and light (dev server, made-up data).

### Changed from the mockup, on purpose
- **Faint grey text is `#B4B4BE`, not `#A1A1AA`.** Measured over the
  brightest corner of the backdrop, the reference grey is 4.3:1; the
  lighter one is 5.0:1.
- **The dark window is a little more solid** (68 %, the mockup used 58 %
  plus a second tint) for the same reason.
- **"Match Windows" stays** as a third theme choice next to dark and
  light (the app already had it; E4 leaves it open).

### Not done yet (so don't be surprised)
- The sidebar, top bar, search and quick actions still have the old
  layout: that is 17c. Each screen's own layout (pipeline card, Do next,
  accordions, Evals by step) comes in 17d to 17g.
- Chart colours and the galaxy's 3D sky are still version 2's (17d, 17g).
- Graphics cost of the blur has not been measured yet; it will be, with
  the full layout in place.

### Learned
- The version 2 styles were already built on tokens, which is why one
  file could restyle the whole app.
- The reference grey fails contrast on glass over a bright backdrop: on
  see-through surfaces, check text against the worst spot behind it.

## 17c The shell ✅ (16 Nov 2026)

### What was done
- **Sidebar:** two labelled groups, "Job search" (Dashboard, Analyze,
  Tracker) and "Agent" (Evals, Settings). Agent folds away and opens by
  itself on its own pages. The number of jobs waiting for you sits on
  Tracker. The model card became one row: dot, model, state; a click
  opens Settings.
- **Top bar** on every screen: Search · Ctrl K, the light/dark switch,
  and New analysis (not on Analyze, where it leads). On hover or focus
  the button reads "Land the next one" and its plus becomes a scanning
  lens.
- **Quick actions:** Ctrl K or a click. Actions (Analyze a new job,
  Confirm applications and Follow up when there are any, Export the
  tracker as CSV, Switch to light / dark mode), Go to (the five pages),
  and Jobs (the three newest, or every match as you type). It searches
  the same fields as the Tracker's search: company, role, contact, notes.
  Picking a job opens its details in the Tracker.
- **Pages settle in** with a short fade when you change screens.
- The Dashboard's own "New analysis" button is gone (it is in the top
  bar now). The three-way theme switch left the sidebar; "Match Windows"
  is still in Settings.

### Checked
- Build passes; pytest: 471 pass; the real window starts (5 menu items)
  and shows the new shell.
- Driven in a browser with made-up data: the fold opens and closes;
  the theme switch flips; Ctrl K opens, the search box has the focus,
  arrows move, typing filters, Enter on a job opens its details in the
  Tracker; Esc and a click outside close; export reports the saved file;
  no "New analysis" on Analyze; at 720 px wide nothing scrolls sideways.

### Found and fixed on the way
- The light/dark button showed no icon: a later rule gave it side padding
  wider than the button. Seen in the first screenshot, fixed.

### Different from the mockup, on purpose
- The top bar is its own slim row above the page title, not on the title's
  line: each screen keeps its own controls next to its title (the
  Dashboard's 7 / 30 days / All, the Tracker's search and Board / List).
- The Tracker keeps its own search box for now. Quick actions searches
  the same fields, so 17e can decide whether the box goes.
- "Confirm applications" and "Follow up" open the Tracker; they don't
  switch on its filter yet (17e).

### Not checked
- Ctrl K was pressed in a browser, not inside the real JobLens window.
  Try it there: `.venv\Scripts\python -m desktop_web`.

## 17d The Dashboard ✅ (16 Nov 2026)

### What was done
- **Two groups**, each with its own heading. "Your job search" first:
  - **Pipeline card** (the lead): jobs tracked, one bar split by status,
    a count per status.
  - **Do next**: the follow-up reminder, "Did you apply?", and the strong
    fits ready to apply to, in one list. One job: the row opens its
    details. Several: it opens the Tracker.
  - **Job galaxy and the selected job** in one panel, with a **3D / Map**
    switch on the card (Map is the flat view; it doesn't change the 3D
    setting, and it is hidden when 3D is off in Settings).
- "How JobLens is doing" second: the 7 / 30 days / All switch, three
  **gradient cards** (median run, evidence verified, cover notes
  approved), then **Time per step** and **Safety nets** in one panel.
  The longest step is highlighted and named ("Compare resumes takes
  about 45% of a run"); safety nets are rows, not tiles.
- **Galaxy colours**: the sky is see-through glass in both themes; dots
  and rings use the one-blue fit scale.
- In the selected job, what your resume proves and the gaps are lists
  with check and dash icons instead of chips.

### Checked
- Build passes; pytest: 471 pass; the real window starts and shows the
  new Dashboard with your data.
- Driven in a browser with made-up data, dark and light: 3D to Map and
  back; picking a dot changes the selected job; a Do next row opens the
  job's details; 7 days changes the numbers; nothing scrolls sideways at
  720, 1100 or 2560 px wide.

### Found and fixed on the way
- At 720 px the third gradient card sat alone on a row: the cards may be
  narrower now, so three fit.
- With your real data only one thing was waiting, and Do next was a tall
  empty card next to the galaxy: it is as tall as its content now.

### Different from the mockup, on purpose
- **The outer galaxy ring is at fit 20, not 25.** The app's galaxy already
  placed rings where the fit levels change (75, 55) and at its floor
  (20), and the dots already matched them. The mismatch was only in the
  first mockup.
- **"Draft a cover note" stays** as the second button on the selected job
  (the mockup said "Interview prep"). It is what the app offers there
  today; interview prep is in the job's details.
- **No "vivid" gradient switch.** The tinted cards were the default you
  reviewed; the brighter version was a mockup-only comparison.
- **The safety nets list has five rows**, the app's real ones, not the
  mockup's four.

### Not done
- Chart colours on Evals (17g). The blur's graphics cost is still not
  measured.

## 17e The Tracker ✅ (17 Nov 2026)

### What was done
- **Needs you**: one accordion (open) instead of two banners, in the
  order you'd act: confirm you applied, then follow up. "Show them"
  lists just those jobs.
- **Board**: a long column shows six cards, then "Show N more" / "Show
  fewer". An empty column says "Drop a job here". The small fit bar on
  each card is gone (the fit number is on the card).
- **Detail sheet**, in this order:
  1. the next step for that job: the "Did you apply?" or follow-up
     reminder if one is open; otherwise what comes next at its stage
     (Researched: draft a cover note. Cover note ready: open the posting,
     "I applied". Applied: write a follow-up email. Interviewing:
     interview prep);
  2. Status and Open posting, always in view;
  3. accordions: **Fit** (open), **Cover note** (open while the job is
     at "Cover note ready"), **Your notes** (open when you have any),
     **More tools**, **About the company**;
  4. the job description, the dates, Delete.
- A new shared accordion, `Fold`, for 17f and 17g too.
- Links to a reminder now open the Tracker on it: quick actions'
  "Confirm applications" and "Follow up", and the Dashboard's Do next
  rows that cover several jobs.
- "Ignore" on "Did you apply?" now reads "Stop asking". The small line
  above a dialog's title is plain words, not capitals.

### Checked
- Build passes; pytest: 471 pass; the real window starts.
- Driven in a browser with made-up data: the fold closes and opens;
  "Show them" gives 2 of 6 jobs; `#/tracker?show=follow` gives 1 of 6;
  the sheet's order and each fold's summary line; the next step for a
  Researched and an Interviewing job; dragging a card from Researched to
  Applied (count 1 to 2, with Undo); "Show more" (with the limit set to
  1 for the test, then put back to 6); the list view, interview prep,
  the follow-up email and the resume prompt in dark and light; nothing
  scrolls sideways at 720 or 2560 px.

### Found and fixed on the way
- "Your notes" appeared twice (the fold's title and the section's own).
- More tools promised a follow-up email on jobs that don't offer one.

### Different from the mockup, on purpose
- **Status stays in view**, not inside a closed "Status and tools". The
  board's drag has no keyboard version; people who use the keyboard
  change a status in this sheet, so it must not be a click away.
- **The sheet has more folds than the mockup** (Cover note, Your notes,
  About the company): the real sheet holds more than the mockup showed.
- **The Tracker keeps its search box.** It filters the board in place,
  which quick actions doesn't do.

## 17f Analyze ✅ (17 Nov 2026)

### What was done
- **One column, in the order things happen** (it was two columns: steps
  left, the draft right).
- **The run card**: a heading that says where the run is ("Step 2 of 5",
  "Step 5 of 5", "All five steps", "Stopped at step 3"), a state pill
  (Running, Your decision, Needs the posting text, Done, Something went
  wrong), the time so far next to the usual time, one bar for the whole
  run, then the five steps. A finished step has a gradient check and a
  coloured line down to the next; the running step breathes; a step
  reused from the tracker has a dashed outline.
- **Your decision** sits directly under the steps and scrolls into view
  when the run stops for you or ends. Before a run, one sentence under
  the steps says what happens at step 5.
- **Live log** is an accordion, closed, and shows the line the agent is
  on.

### Checked
- Build passes; pytest: 471 pass; the real window starts.
- A simulated run in a browser, dark and light: idle, running (heading,
  bar, step states, the log's line), your decision (the draft is in
  view), the log opened (9 lines), approve (bar full, "Done"), and a
  posting that can't be read ("Needs the posting text"); nothing scrolls
  sideways at 720 px.

### Found and fixed on the way
- The heading named the wrong step when an earlier step was marked
  stopped while a later one ran. It now goes by the step in progress.

### Not checked
- **The "Stopped" and "Something went wrong / API limit" panels.** The
  simulator keeps sending steps after a stop and has no failing run, so
  those two panels were not seen. Their markup didn't change (only the
  shared card look did). Worth a look on a real run: start one, press
  Stop.
- A real run with the real model.

### Different from the mockup, on purpose
- **The draft is under step 5, not inside it.** The real review is an
  editor with warnings and a "why this fit" section; inside a step row it
  would be cramped. It sits directly below and comes into view by itself.
- **The resumes being compared are words, not chips** ("best:
  AI_Engineer.pdf"): that is what the agent reports for step 2.
- **The Analyze button stays** and shows the running time; Stop is next
  to it.
