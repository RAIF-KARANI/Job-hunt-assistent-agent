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
| 17g Evals | ✅ | a run step by step, chart colours from the accents (validated), the rest in folds |
| 17h Settings, wizard, quick box | ✅ | Settings folds the less-used sections; the wizard sits on the glass |
| 17i Light theme check | ✅ | all text measured in both themes; one blue lightened |
| 17j Accessibility and sizes | ✅ | keyboard focus, reduced motion, 720 to 2560 px: all pass |
| **Phase 17** | ✅ | the glass look on every screen, both themes |
| 18a The Tauri window | ✅ | your real UI and data in a Rust window, Python beside it |
| 18b Measured | ✅ | 36% faster to your data, 19–24% less memory, only 5% smaller |
| 18c Decide | ✅ | adopt Tauri (your choice) |
| 18d1 The Rust window in the app | ✅ | `desktop_tauri/` + `engine.py`; your data in the Rust window; smoke test |
| 18d2 File dialogs | ✅ | Add PDFs and Save as through the Rust window |
| 18d3 The tray | ✅ | Icon, menu, notifications, hide on close; decisions still tray.py's |
| 18d4 Quick box | ✅ | Ctrl+Alt+J opens the box in the Rust window |
| 18d5 One copy, autostart, shutdown | ✅ | Second start shows the first; --tray; installer and Windows can close it |
| 18d6 Packaging | ✅ | Installer builds, installs, passes both tests, uninstalls clean |
| 18d7 Real update test | ✅ | 1.2.0 → version 3 and 3 → 3: all four update checks pass |
| 18d8 Measured, installed | ✅ | 42 % sooner to data, 7 % less memory, same size |
| 19 Your features | 🚧 | chosen (E7): 19a backup, 19b interview calendar, 19c insights, 19d resume tailoring |
| 19a Backup and restore | ✅ | one .zip, no API keys; restore checks the file and backs up first; weekly + before an update |
| 19b Interview calendar | ✅ | reminders the evening before and an hour before (fired in the real window); .ics; Do next and Needs you |
| 19c Insights | ✅ | new screen: interview rate by resume, site and fit band; wait for an answer; status history from now on |
| 19d Resume tailoring | ✅ | model suggests edits to your lines, code drops what adds or loses facts; 3 rounds on 3 real jobs |
| **Phase 19** | ✅ | all four features (E7) |
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

## 17g Evals ✅ (17 Nov 2026)

### What was done
- **"A run, step by step"** replaces the seven tiles and four chart rows.
  The agent's steps in the order it works; each row has the step's
  average time as a bar (the slowest in the gradient) and its main
  result. The whole run's totals are in the panel's header: median time,
  tokens, cost, unfinished runs.
- **The three checked steps open:**
  - *Compare resumes* (open): evidence pass rate and its change, claims
    checked, fake quotes caught, judge rejections, the pass rate run by
    run and by model, your ratings of the fit score.
  - *Research company*: searches that failed, invented links and dates
    removed.
  - *Draft cover note*: cover notes approved, number warnings, rewrites,
    your ratings of the cover note.
- **Accordions below:** Models compared (open), Run by run (tokens,
  agent time, time against tokens; closed), Recent runs (closed; its
  line shows how many and the latest result).
- **Chart colours from your accents**, checked with the palette
  validator in both themes: blue, orange, purple, gold for models; blue,
  gold, pink for good, mixed, bad ratings.
- Numbers in tables and on chart axes use the text font with even-width
  digits. Model names keep the code font.

### Which check belongs to which step
This was an open point from the mockup. It is taken from the code now:
`EVAL_CHECKS` in `job_agent/monitoring.py` describes each check by what
it looks at. Claims and quotes: the fit analysis. Sources and dates: the
search results. Numbers and rewrites: the cover note.

### Checked
- Build passes; pytest: 471 pass; the real window starts.
- The validator, four palettes (series and ratings, dark and light):
  every check passes.
- Driven in a browser with made-up data, dark and light: the totals, the
  five rows, which step is open, the checks in each step, a chart's hover
  tip, the three accordions, Run by run (4 charts), Recent runs; nothing
  scrolls sideways at 720 or 2560 px.

### Learned
- **Blue next to purple can't be told apart by colour-blind readers**
  (the validator scored it 0 for the commonest kind). Two of your accents,
  so the order matters: blue, orange, purple, gold.
- The accents as given are too light for chart marks on a dark surface
  (orange and yellow fall outside the validator's lightness band); the
  chart steps are darker versions of the same hues.

### Not checked
- **The model filter**: the made-up data ignores it, so the numbers
  didn't change in the browser. The request it sends is unchanged.
- The validator was run against one colour for the card (dark `#1B2130`,
  light `#F3F6FC`). The real card is see-through, so what is behind a
  chart shifts a little with the backdrop.

### Different from the mockup, on purpose
- **Six rows when the app reports six steps** ("Check tracker" is one in
  the real run log); the mockup drew five.
- **More in the folds than the mockup**: ratings, pass rate by model,
  agent time per run, time against tokens, recent runs and the tracing
  chips are real parts of this screen that the mockup left out.

## 17h Settings, the setup wizard, the quick-analyze box ✅ (17 Nov 2026)

These three had no mockup. They already had the new look from 17b's shared
styles; this step looked at each in both themes and fixed what was off.

### What was done
- **Settings in two parts.** AI model and Your resumes stay open: they are
  what setup needs and what you change most. Under a "More settings"
  heading, Appearance, Options, Reminders, Quick analyze and Updates are
  accordions, each with a line saying what it is set to ("Like Windows ·
  3D animated", "Follow up after a week", "Shortcut Ctrl+Alt+J"...). The
  "Saved" mark shows inside the open section.
- **The setup wizard** had its own flat background, which hid the glass
  backdrop. It now sits on the same backdrop as the app, as one frosted
  card.
- **The quick-analyze box** already looked right in both themes: no
  change.

### Checked
- Build passes; pytest: 471 pass; the real window starts.
- In a browser with made-up data, dark and light: Settings (the five
  summaries, opening Appearance, choosing a theme there updates its
  summary), the wizard's first two steps, the quick box; nothing scrolls
  sideways at 720 px.

### On the way
- The PC ran out of memory during this step (0.5 GB free) and Windows
  stopped the dev server. You closed apps and we went on. A leftover dev
  server from an earlier step was still running in the background; it is
  stopped now. For the next steps: one dev server and one test browser at
  a time, closed as soon as the checks are done.

## 17i Light theme check ✅ (17 Nov 2026)

Both themes had been built screen by screen since 17b, so this step
measured them instead of only looking at them.

### What was done
- **A contrast script** (`scripts/check_contrast.js`): for every piece of
  visible text, it blends the layers behind it, from the backdrop up
  through the window and the cards, and works out the contrast. It does
  this against the brightest and darkest spots of the backdrop (its four
  coloured corners and the plain middle), so a pass holds wherever the
  text sits. The bar is WCAG AA: 4.5:1, or 3:1 for large text.
- Run on 9 views per theme: Dashboard, Analyze, Tracker (board, list, a
  job's details with every section open), Evals (every step open),
  Settings (every section open), the component sheet, quick actions.

### Result
- **Light: every piece of text passes.**
- **Dark: one near-miss.** The light-blue text on small blue badges
  ("Interviewing", "5 jobs") was 4.5:1 exactly. The dark theme's accent
  text went from `#93C5FD` to `#A8D0FD` (5.2:1); measured again: no
  failures in either theme.

### Not measured (checked by eye instead)
- Text on gradients (the gradient cards, the main button, the job galaxy)
  and on disabled controls. The gradient cards and buttons were looked at
  in both themes in 17c and 17d.

## 17j Accessibility and window sizes ✅ (17 Nov 2026)

### Checked
- **Keyboard**, in both themes, on Dashboard, Analyze, Tracker, Evals and
  Settings: Tab through every control (11 to 27 stops a screen) and check
  that each one *visibly changes* when it gets the focus, by comparing it
  focused and unfocused. A first version only asked "does it have a
  shadow?", which glass buttons always have, so it would have passed
  anything; the stricter one is `scripts/check_focus.js`. Result: every
  stop changes, in both themes.
- **Reduced motion** (Windows' "show animations" off): on the Dashboard,
  during a run on Analyze, and with the mouse over New analysis, nothing
  keeps moving.
- **Window sizes** 720, 1024, 1440, 1920 and 2560 px, all five screens:
  nothing scrolls sideways and no text runs out of its card. Looked at the
  Dashboard at 720 and 2560.
- **Contrast**: done in 17i, both themes.

### Nothing needed fixing in this step.

## Phase 17 done ✅ (17 Nov 2026)

Every screen has the glass look in dark and light: the shell, Dashboard,
Analyze, Tracker, Evals, Settings, the setup wizard, the quick-analyze box
and the dialogs. Commits `03bb5c1` (17b) to this one, all on `version-3`.

### Left open (none of them blocks Phase 18)
- **The blur's graphics cost** was never measured. Nothing felt slow in the
  real window, but a slower PC may notice. If it does, `--glass-blur` in
  `tokens.css` is the one place to turn it down.
- **The "Stopped" and "Something went wrong / API limit" panels** on Analyze
  were not seen in the new look (the simulator can't make them). Worth a
  look on a real run: start one and press Stop.
- **Showing the real desktop through the window** (F1) needs a see-through
  window: a question for the Phase 18 spike.
- **E4:** whether "Like Windows" stays as a theme choice (it does for now).

## 18 Before starting: a size check (17 Nov 2026)

Today's app folder, by part: the window code Tauri would replace is about
3–4 MB of the libraries; `pandas`/`numpy` are ~40 MB (used only to add up
Evals and Dashboard numbers); the web search library ~15 MB; `PIL` ~13 MB
(the tray icon). From that I expected Tauri to be neither clearly smaller
nor faster, and suggested slimming the Python side instead. You chose to
run the spike as planned. **The size part of that expectation held; the
speed part was wrong** (below).

## 18a The Tauri window ✅ (17 Nov 2026)

### What was done
- **Rust installed** (1.100.0, the minimal toolchain, in
  `%USERPROFILE%\.cargo\bin`; not added to PATH, so nothing else on the
  PC changes). The C++ build tools were already there.
- **`spikes/18_tauri/`**: a Rust program (Tauri 2) that opens a window
  with the real built UI, starts the Python side and passes messages:
  each `api.something(...)` on the page becomes one JSON line to Python,
  and Python's events (log lines, run steps) come back the same way.
- **The Python side** (`sidecar.py`) is today's `Api` class, unchanged,
  behind a pipe. It refuses hidden methods, and keeps the agent's own
  `print`s out of the pipe.
- **The page** (`bridge.ts`): a few lines so that inside Tauri it talks to
  `call(...)`; the normal app is untouched (its build and tests pass).

### Checked
- The Python side alone: answers `app_info` (v1.2.0) and `list_jobs` (your
  33 jobs), refuses `_secret`.
- The Rust build: compiled in about 10 minutes, 3.7 MB program with the UI
  built in, 1.8 MB installer (without Python).
- The window started and the page got its data from Python, every time
  (measured in 18b; it closes itself after measuring).

## 18b Measured ✅ (17 Nov 2026)

Both windows run from source with the same Python and the same start-up
work, started from outside and timed the same way; 5 runs each after a
warm-up, alternated. Scripts: `spikes/18_tauri/measure.py`, `size.py`.

| | Today (pywebview) | Tauri | Change |
|---|---|---|---|
| Time until your data shows | 2.11 s | 1.34 s | **36% faster** |
| The page drawn (before data) | – | 0.32 s | |
| Memory, 1 s after ready | 585 MB | 474 MB | **19% less** |
| Peak memory at start | 626 MB | 476 MB | **24% less** |
| Installer, compressed (estimate) | 62.1 MB | 59.0 MB | **5% smaller** |

- **Why faster:** the Rust window draws the page in 0.3 s while Python
  starts beside it. Today the window waits for Python to load pywebview
  and .NET (pythonnet) first. Python itself takes about 1.3 s either way.
- **Why barely smaller:** what only the window and tray need is 16.5 MB of
  the 153 MB app folder (webview, pythonnet, the tray's PIL and pystray,
  the UI files). The rest is Python and the agent, which ship either way.
  The installer size is an estimate: today's v1.2.0 folder minus those
  files plus the Rust program, compressed the same way (LZMA) as today's.

### Against the bar proposed in E2
"The installer at least 25% smaller, **or** the window ready at least 30%
sooner, **and** nothing worse (tray, shortcut, updates, memory)."
- Size: 5%, no. Speed: 36%, **yes**. Memory: better, yes.
- Tray, shortcut, updates: **not known yet.** The spike doesn't have them;
  they would be rewritten in Rust (18d), with the real update test again.

### Not measured
- The frozen (installed) app. Both were run from source; the installed
  app may start a little differently.
- How long 18d would take, and whether any of today's features are harder
  in Tauri (Add PDFs dialog, the tray, the global shortcut, Start with
  Windows, one copy at a time, the updater).

## 18c Decided ✅ (17 Nov 2026)

You chose to adopt Tauri: version 3's window moves to Rust, the agent stays
Python. The bar for 18d is "nothing worse": every feature of today's
window works the same before the release, and the real update test
passes. How it is built: decision E6. The steps: the plan, Phase 18.

## 18d1 The Rust window in the app ✅ (17 Nov 2026)

### What was done
- **`desktop_tauri/`**: the Rust program, out of the spike and into the app
  (README there). It finds the engine next to itself once installed, or
  the repo's Python from source.
- **`desktop_web/engine.py`**: the Python side. Besides answering the page,
  it can now ask the window for things and wait for the answer (show,
  hide, quit, open a page; the file dialogs and the tray next). The window
  tells it when the page has loaded and when it is shown or hidden.
- **`desktop_web/startup.py`**: the start-up and quit work (cut-off runs,
  old scores, the update check, tidying, freeing the model on quit) moved
  out of `app.py`, so the old and new windows do exactly the same.
- `bridge.py` no longer loads pywebview when it is imported (only when the
  old window opens a file dialog), so the engine runs without it.
- On close, the window closes the pipe and gives the engine up to 8 s to
  end a running step and free the model, like Quit today.
- **A smoke test**: `JOBLENS_SMOKE=out.json` (and `JOBLENS_SMOKE_SHOT` for a
  picture): once the page asks for its first data, a report is written and
  the window closes.

### Checked
- pytest: 484 pass (13 new: the engine's protocol, without a window and
  without your data).
- The Rust window from source: your real Dashboard (33 jobs, the galaxy,
  Do next), engine running beside it. Smoke test: start, data on screen,
  report, both processes ended in 1.5 s; no engine left behind.
- The old window still works (`python -m desktop_web --smoke`).

### Learned
- **Two copies of the window can't share WebView2's profile**: a second
  one crashed at start ("the requested resource is in use") while the
  first was still closing. One copy at a time (18d5) prevents it.
- A filter that kills processes by command line must not match its own
  command (it stopped itself once; nothing else was touched).

## 18d2 File dialogs ✅ (17 Nov 2026)

### What was done
- **Rust** shows Windows' own Open and Save dialogs (Tauri's dialog
  plugin), on top of the JobLens window, with the file name and type
  filled in. They never block the window; the answer (the path, or nothing
  when you cancel) goes back to the engine.
- **Python**: `bridge.py`'s two dialog helpers ask the Rust window when the
  engine runs them (`Api._dialogs`), pywebview otherwise. So Add PDFs and
  every Save as (tracker CSV, cover notes, interview prep sheets) work in
  both windows without changing the screens.
- The smoke test can open a dialog (`JOBLENS_SMOKE_DIALOG=open` or `save`),
  to check the window's side end to end.

### Checked
- pytest: 487 pass (3 new: the file types, saving through the window's
  dialog with the extension added, cancelling).
- In the Rust window: **Open** appeared ("Open"), was cancelled, and the
  engine got "nothing chosen". **Save** appeared over the JobLens window
  with "JobLens test.csv" and "CSV file (*.csv)" filled in.
- The old window still starts.

### Not checked
- **Saving to a path you pick in the Rust window**, all the way: my
  automated typing went to VS Code instead of the dialog, so that run
  ended without an answer. Choosing a file uses the same route back as
  Cancel, which worked, and the Python side of it is tested. Worth one
  real try: Tracker, Export CSV, in the Rust window.

### Learned
- **Never type into the desktop from a script**: the keyboard belongs to
  whichever window has the focus, which was VS Code. Checked afterwards:
  no file in the project changed. The keys may have landed in an open
  editor or terminal without being saved.

## 18d3 The tray ✅ (17 Nov 2026)

### What was done
- **Python decides, unchanged.** The Rust window uses the same `Tray`
  class as the pywebview window (`tray.py`): the menu's words, which
  notification to show, whether the X hides or quits. `engine.ShellTray`
  sends only the drawing to the window: the menu and tooltip after every
  change, and each notification.
- **Rust draws.** The tray icon with its menu (Open JobLens, the status,
  Follow up on N jobs, Stop the run, Quit); a left click on the icon opens
  JobLens. Notifications are Windows' own, with their sound; clicking one
  opens the screen it is about (Analyze or the Tracker).
- **The X asks the engine first.** While a run is going (or JobLens is
  kept in the tray) the window hides; otherwise it quits, as in 1.2.0. If
  the engine isn't there to answer, the window simply closes.
- Windows shows notifications only for an app it knows, so the engine
  registers "JobLens" (name and icon) for the user under
  `HKCU\Software\Classes\AppUserModelId\JobLens.Desktop` at each start.
  **18d6: the uninstaller must remove this key.**
- `keeps_tray` and the follow-up reminder loop moved from `app.py` to
  `tray.py`, shared by both windows (`app.py` keeps the old names).

### Checked
- pytest: 495 pass (8 new: the menu and how it follows a run, closing
  while idle quits, closing while working hides and tells you once, each
  menu item, a notification click, the engine routing tray and window
  messages, the notification registration).
- In the Rust window: the tray icon was created; a notification was sent
  and Windows recorded it for "JobLens.Desktop". It didn't pop up on
  screen because Do Not Disturb was on, so it went to the notification
  centre. Closing the window while idle quit it in 0.2 s, and no engine
  was left running.
- The old window still starts.

### Not checked yet (one real try)
- Right-clicking the tray icon and choosing each item; closing during a
  run (it should hide, with the "still working" notification); clicking
  a notification with Do Not Disturb off.

## 18d4 The quick-analyze box ✅ (17 Nov 2026)

### What was done
- **The shortcut stays in Python** (E6): the same `HotkeyListener`, started
  by the engine; Settings still changes it and shows whether it works.
- **Rust has the box ready**: a second small window (480 × 210, no frame,
  on top, not in the taskbar), made hidden at start so Ctrl+Alt+J opens it
  at once. Each time it's shown it is centred, focused, and cleared, with a
  copied link filled in (the page's own `joblensQuick.opened()`).
- **Its own small API**: every call from the page now says which window it
  came from; calls from the box go to `QuickApi` (clipboard link, start,
  close) and can't reach the main window's API, as with pywebview.
- Events go only to the main window. Alt+F4 on the box hides it. When the
  main window is gone the app ends: the hidden box can't keep JobLens
  running (the 1.0.0-1.0.1 bug).

### Checked
- pytest: 498 pass (3 new: the box's calls go to its API, it can't reach the
  main API, the shortcut asks the window for the box and Close hides it).
- In the Rust window (smoke test with `JOBLENS_SMOKE_QUICK=1`, no keys
  pressed): the box became visible, its page called `app_info` and
  `clipboard_link` through the engine, then it hid again. The whole run took
  4.5 s, and nothing was left running.
- The old window still starts.

### Not checked yet (one real try)
- Pressing Ctrl+Alt+J itself in the Rust window: the installed JobLens holds
  the shortcut while it runs, so a second copy can't register it. Close the
  installed JobLens first, then try it.

### Learned
- A process check that matches "desktop_web.engine" in command lines also
  matches itself. Filter by process name, or leave out your own process.

## 18d5 One copy, Start with Windows, closing at shutdown ✅ (17 Nov 2026)

### What was done
- **One JobLens at a time**: Tauri's single-instance plugin. A second start
  brings the first one's window back (out of the tray too) and exits.
  1.2.0's own check (`instance.py`) stays for the pywebview window.
- **Start with Windows**: the Run value must name the Rust `JobLens.exe`,
  not the engine. The window tells its engine where it is
  (`JOBLENS_APP_EXE`); `autostart.py` uses that, and `sys.executable` for
  the pywebview app as before. A 1.2.0 Run value (`...\JobLens.exe --tray`)
  still counts as on after the update, as long as 18d6 keeps the name and
  folder.
- **`--tray`**: the main window is made hidden and shown only for a normal
  start; with `--tray` the page still loads, hidden, and the engine knows the
  window is hidden (tray notifications, reminders).
- **Windows shutdown and installers**: the main window answers Windows'
  "may JobLens close?" with yes and, when the session really ends, stops the
  engine properly (the run, the model) before exiting. The X button can't
  be used for this, since it may only hide to the tray; that was 1.0.3's
  update bug.

### Checked (the real Rust window, no keys pressed)
- Started with `--tray`: the window stayed hidden, the engine ran.
- A second start exited in 1.5 s, one copy was left, and its window came
  back.
- Closed through the Windows Restart Manager (what Inno Setup uses to close
  running apps before an update), once with the window shown and once
  hidden in the tray: closed both times, the window and engine gone in
  0.2 s.
- pytest: 499 pass (1 new: the Run value names the window's exe). Both
  windows' smoke tests pass.

### Not checked
- A real Windows shutdown or sign-out (same messages as the Restart
  Manager's, but untested); worth noticing once after 2.0.0 is installed.

## 18d6 Packaging ✅ (17 Nov 2026)

### What was done
- **The installed app is now two programs** in the same folder as before
  (`%LOCALAPPDATA%\Programs\JobLens`):
  - `JobLens.exe`: the Rust window (4 MB, the UI built in);
  - `engine\joblens-engine.exe` + `engine\_internal\`: Python and the
    agent (PyInstaller, `joblens.spec`). It's a console program, so its
    stdin and stdout are the pipe; it's started with no console window.
    It no longer bundles pywebview, pythonnet or pystray.
- **What the installed engine prints** goes to
  `%LOCALAPPDATA%\JobLens\engine.log`, new on each start (from source it
  still goes to the terminal).
- **The engine checks itself**: `joblens-engine.exe --self-test report.txt`
  runs the same self-test as before, without the window-only checks.
- **The installer** has the same app id and folder, so 1.2.0 updates in
  place. It removes 1.2.0's `_internal\` folder first, so ~150 MB isn't
  left behind. The uninstaller also removes the notification entry (18d3)
  and, as before, the Start with Windows value.
- **`scripts/build_installer.py`** builds in this order: front end, WebView2
  bootstrapper, Rust window, engine, app folder, checks, installer. A build
  is refused unless the engine's self-test passes **and** the real window
  opens with its engine, shows the page, and shows and hides the quick box.
- **THIRD_PARTY_NOTICES.md**: Tauri and its Rust libraries (MIT or
  Apache-2.0); the pywebview and pystray sections are marked "up to 1.2.0".

### Checked: `scripts/build_installer.py --test-install` passes
- **The app folder:** engine self-test PASS, including a real web search
  and a real structured call to the local model ("Paris"). Window test OK:
  Rust window, page answering, quick box shown and hidden.
- **The Test Build installer:** 68 MB; app folder 161 MB.
- **Installed silently into a temp folder:** the installed copy passed the
  same two tests.
- **Uninstalled:** no files and no registry entry left. The real JobLens
  1.2.0 install was not touched.
- pytest: 499 pass.

### Size: not smaller yet
The installer and app folder are the same size as 1.2.0's (68 MB, 161 MB),
not the 5 % smaller the spike measured. The engine is 152 MB; the biggest
parts are numpy (27 MB with its libraries), primp (15 MB, the web search),
pandas (13 MB), Pillow (13 MB) and cryptography (10 MB). For 18d8: measure
properly, and see what the engine can still leave out.

## 18d7 The real update test ✅ (17 Nov 2026)

`python scripts/check_real_update.py --old 1.2.1 --new 2.0.0`: **all four
checks pass.** Real installers, real apps, a local stand-in for GitHub; the
real JobLens 1.2.0 install was not touched.

| Check | What happened |
|---|---|
| new_from_old (1.2.0's app → version 3) | 1.2.0's updater downloaded and verified the new installer, quit, Setup installed it and opened the **Rust window** with its engine; data kept; 1.2.0's `_internal\` removed |
| self_update (version 3 → next) | the Rust app updated itself: the engine ran the installer, the window quit by itself, the new one opened; data kept |
| hand_run | the X button hid JobLens to the tray; Setup run by hand closed it through the Restart Manager (18d5), nothing force-closed |
| failure | Setup couldn't replace a file; the old JobLens reopened, knew the update failed, and Settings said so |

The "old" app is `JobLens-TestBuild-Setup-1.2.1.exe`: built from the 1.2.0
code just before that release (16 Nov), so it is 1.2.0's app numbered 1.2.1.
The new Test Builds are numbered 2.0.0 and 2.0.1 by `--new`; the version
inside the code is still 1.2.0 until the release (E5).

### Fixed on the way
- **A real problem, found by the failure check:** since Phase 17 the Updates
  section of Settings is a closed accordion, so "The update didn't finish"
  was hidden. Settings now asks for the update status itself: when an update
  failed, or a new version is out, the Updates section opens by itself and
  its one-line summary says so.
- **The check script** (`check_real_update.py`) learned the Rust window:
  - it calls the API through either bridge;
  - it looks for the window titled "JobLens", because .NET's "main window"
    can be one of Tauri's hidden helper windows;
  - it writes the saved update check with the app's own version (the
    updater ignores a record for another version);
  - it stops the engine when cleaning up;
  - it checks that the app is the Rust window, that `engine\` is installed,
    and that `_internal\` is gone.

### Learned
- `build_installer.py` without `--test-install` writes
  `dist/JobLens-Setup-<version>.exe`, so while the code says 1.2.0 it
  replaces the local copy of the released 1.2.0 installer. (The released one
  is on GitHub.) Keep the old Test Builds; rebuilding one means checking out
  its tag.
- The engine's self-test loads the local model (~5 GB) for one real call.
  On this PC that can be enough for Windows' memory pressure to stop a
  build: close Chrome first.

## 18d8 Measured, installed ✅ (17 Nov 2026) — Phase 18 done

`python scripts/measure_installed.py 5`: each Test Build installed silently
in a temp folder with an empty data folder, started **normally** (as you
would), watched through WebView2's debug port, closed the way an installer
closes it, 5 runs after a warm-up, then uninstalled. The real JobLens was
not touched.

| | 1.2.0 (pywebview) | Version 3 (Rust) | Change |
|---|---|---|---|
| Installer | 64.8 MB | 64.5 MB | the same |
| App folder | 158 MB | 158 MB | the same |
| Time to data (median) | 1.85 s | **1.07 s** | **42 % sooner** |
| Memory 1 s after (median) | 567 MB | **526 MB** | **7 % less** |
| Peak, first 3 s after (median) | 589 MB | 552 MB | 6 % less |

"Time to data": from launching `JobLens.exe` until the page has its first
answer from Python, i.e. when the screens can show your data. "Memory": the
app and everything it started (WebView2, Python) added up.

Against the bar proposed for E2 (installer ≥ 25 % smaller **or** ready
≥ 30 % sooner, nothing worse): **ready 42 % sooner, memory a little lower,
and the tray, shortcut, notifications and updates pass every check
(18d2-18d7).** Size is unchanged.

### How not to measure (two wrong first attempts)
1. **Smoke mode:** 1.2.0's `--smoke` skips the tray, the quick box and the
   shortcut, and with `--screenshot` it reports 1.5 s after it is ready and
   is already closing at "one second after". That gave 3.3 s vs 4.0 s and
   190 MB vs 448 MB, which were wrong in both directions.
2. **Killing the app between runs:** 1.2.0 then took ~3.9 s on every later
   start (2.3 s on the first), presumably recovering from the kill. Closing
   it cleanly (Restart Manager) gave 1.8-2.2 s.

### Size: what's left
Version 3 drops pywebview, pythonnet and pystray from the app but adds the
4 MB `JobLens.exe`. The engine is 152 MB, and nothing big in it is unused:
- numpy + pandas (~40 MB) compute the Dashboard's numbers (`monitoring.py`);
- primp (15 MB) is the web search;
- Pillow (13 MB) is needed by the PDF export (ReportLab);
- cryptography (10 MB) is needed by Google's sign-in library (Gemini).

Making it smaller means rewriting the Dashboard's sums without pandas. That
would be a separate decision, not part of Phase 18.

## Phase 19 chosen ✅ (21 Nov 2026)

You had no feature list, so I suggested nine features based on what
JobLens doesn't do yet. You chose resume tailoring, insights, the
interview calendar and backup (E7). Two of them were partly there already:
the interview date and contact (14h) and the CSV export (14i). The plan
only builds what is new.

## 19a Backup and restore ✅ (21 Nov 2026)

**Settings → Your data** (a new fold before Updates):

- **Back up now…** writes one `.zip` you choose: the tracker and run log
  (`jobs.db`, copied with SQLite's own backup so it is consistent even
  mid-write), the resumes, the cover notes, and the settings **without
  API keys** (E7).
- **Restore from a backup…** first says what the file holds (jobs, resumes,
  cover notes, when, which version) and asks. Then it backs up what is
  there now ("before restore", so a restore can be undone), replaces the
  data, keeps your API keys, and reloads the page.
- **Automatic backups** go to `APP_HOME\backups`: once a week (a minute
  after start) and just before an update installs. The newest 4 are kept.
  A failed automatic backup never stops the app or the update.

**Left out on purpose: paused runs** (`checkpoints.db`). The plan listed
them, but only the last run can be continued (D30), the file is the
largest one, and the agent keeps it open, so replacing it under a running
app is risky. After a restore, the "Continue" offer simply doesn't appear
for a run whose checkpoint isn't there (already handled since 14d).

**A file from anywhere is checked before anything changes:** only the
names a backup is made of (no folders, no `..`, no other files, no Windows
device names like `CON.pdf`), no name twice, at most 1 GB unpacked,
`jobs.db` must pass SQLite's integrity check, and a backup from a newer
JobLens is refused. Settings come back only for keys the app knows, never
secrets, never with a line break. An older backup gets today's columns
(the same migrations as at start).

**Checks:**
- `tests/test_backup.py`: 21 tests (round trip, no keys in the file, keys
  kept, undo, 10 kinds of bad file each leaving the data untouched, an
  old-schema tracker, keep-4, weekly timing, the bridge's two-step restore,
  no restore during a run). All 520 tests pass.
- The real test data: 33 jobs, 6 resumes, 10 cover notes → 0.7 MB in
  0.1 s; the file holds no key. (The test zip was deleted afterwards: it
  held the friends' resumes.)
- Screenshots (dev server, made-up data): the restore question in dark,
  light and at 720 px.
- On Windows, Python's `zipfile` turns a `\` in a name into `/` when it
  writes, so a "backslash" test file can't be made with it. The check for
  `\` stays as a guard for zips made by other tools.

**Learned:** Windows PowerShell 5.1's `Get-Content -Raw` reads a UTF-8
file without a BOM as ANSI, and `Set-Content -Encoding utf8` then writes
it back garbled with a BOM. That happened to the plan and this log in the
first 19a commit; fixed in the next one. Edit docs with the editor, not
PowerShell string replacement.

## 19b Interview calendar ✅ (21 Nov 2026)

The interview date you type on a job (since 14h) now does something:

- **Reminders** (`job_agent/interviews.py`, sent by the tray loop): one
  **the evening before** (from 18:00) and one **an hour before**, each once
  per date. The tracker remembers what was sent in a new column,
  `interview_reminded` = `"<date>|evening,hour"`, so a moved interview gets
  fresh reminders by itself. A date without a time gets only the evening
  one. If JobLens wasn't running the evening before, the morning reminder
  says "today", not "tomorrow"; a late start gets only the hour one. No
  reminders for rejected jobs. Unlike the follow-up reminders, these show
  **even with the window open** (you may be in another program). A click
  opens that job (`tracker?job=12`), not just the Tracker.
- The reminder loop now looks every **5 minutes** (was 30): "an hour
  before" needs it. The follow-up notice is still once a day and "Did you
  apply?" still once per job.
- **Add to calendar…** in the job's notes (only for a saved date still
  ahead): an `.ics` file, then **Open in your calendar**. "Floating" time
  (no time zone) so every calendar shows the 10:30 you typed; a date only
  is an all-day event; a reminder an hour before is built in; contact,
  posting link and location go in the event. Lines are folded at 75 bytes
  without splitting a character (tested with Polish and Nordic names).
- **Needs you** (Tracker) lists interviews today or tomorrow first, with
  "Open the job"; they count in the sidebar's number too.
- **Dashboard → Do next** starts with the next 7 days' interviews. (The
  plan said a separate card; Do next already is "what's waiting for you",
  and a second card would push the galaxy down. So no new bridge call
  either: it uses the job list the Dashboard already has.)
- **Rust window:** a page name may now carry a query (`?`, `=`, `&`), so a
  notification can open one job. Still no quotes or brackets: it can't
  break out of the script string.

**Checks:**
- `tests/test_interviews.py`: 14 tests (upcoming order, evening then hour
  each once, late start, "today", a moved date, date-only, the tray shows
  each once and a click opens the job, the .ics fields, escaping and
  folding, all-day, the bridge export, only exported .ics files open).
  534 tests pass.
- **In the real Rust window**, on a temporary copy of the test tracker with
  an interview 50 minutes ahead: the reminder went out about 20 s after
  start and was recorded; no errors; the engine exited with the window.
  Your installed JobLens kept running untouched. The copy was deleted.
- Screenshots (dev server, made-up data): Do next (dark), Needs you
  (light), the notes with "Add to calendar" and the saved file.

**Left for you:** open one `.ics` in your own calendar (Outlook or
Google) to see the time come out as typed. I can't check that without
your calendar.

## 19c Insights ✅ (21 Nov 2026)

A new screen, **Insights**, in the sidebar after Tracker. Plain counting
(`job_agent/insights.py`), no AI, offline.

- **The history:** a new table, `status_changes`, records every status
  change (one place: `tracker.update_status`, which the cover note, "Did
  you apply?" and the board all use). **An undo within 10 minutes takes
  the change back out** instead of recording its mirror image, so a job
  dragged to Applied by mistake never counts as an application. Deleting a
  job deletes its history.
- **Tiles:** applications, the share that reached an interview, offers,
  the typical wait for an answer (median, with fastest and slowest).
- **Three groupings**, each "interviews out of applications": by the best
  resume, by the posting's site (LinkedIn, Indeed, Bayt… and company career
  pages by the system they run on: Greenhouse, Lever, Workday…), and by fit
  band (75 and up, 60 to 74, under 60, matching Ready to apply's 75).
- **Where your jobs are now:** every status, and where the rejected ones
  stopped.

**Honest by design** (from E7):
- A group with **fewer than 5 applications shows its counts but no rate**
  ("2 of 4 · too few to say") and no bar: 1 of 2 is not "50 %".
- A **Rejected job with no history** (all of today's) might be a no from
  them or one you dropped before applying. It is counted as **unknown**
  and left out of the rates, and the screen says how many.
- The wait for an answer needs both changes recorded, so it starts with
  jobs applied to from now on; until then the tile says how it will fill.

**Checks:**
- `tests/test_insights.py`: 15 tests (recorded once, undo, later reversal
  kept, cascade delete, the 5-application rule, unknown vs placed
  rejections, wait times and still waiting, sites and bands, the bridge).
  549 tests pass.
- **The test tracker against a hand count in SQL:** 33 jobs, 18
  applications, 0 interviews, 6 rejected unknown. Insights says the same.
- Screenshots (dev server, made-up data with interviews and an offer):
  dark and light at 1440 px, dark at 720 px with no sideways scroll. Two
  fixes came from looking: "4 They are…" repeated the number, and
  "Greenhouse (company page)" was cut off, so sites are now plain names and
  the card's hint explains company pages.
- The bars reuse the Dashboard's single-hue bars (one series: no legend
  needed, the numbers are written beside every bar, hover gives a
  sentence), so no new chart colour had to pass the palette validator.

## 19d Resume tailoring ✅ (21 Nov 2026)

In the job's **Resume prompt** dialog ("Improve your resume for this
job"), a new first section, **Suggested edits**: your model rewrites lines
of your own resume for this job (before → after, the requirement, why),
and **plain code checks every edit before you see it**
(`job_agent/tailoring.py`). The prompt for another AI stays below it, as
"Or ask another AI". Copy one edit or all.

**The check drops an edit that** (with the reason shown under "Why … were
dropped"):
- changes a "before" line that isn't really in your resume (the fit
  check's quote test, stricter);
- adds a number the line doesn't have, or turns "about 40" into an exact
  40;
- **leaves out** one of your numbers or named tools (see round 1 below);
- adds a skill from the job that your resume doesn't show, or a new
  name-like word (a tool, product, employer, certificate). The job's own
  words are allowed only for requirements the fit check and judge already
  verified ("RAG" for a verified "RAG pipelines"); hyphen and plural forms
  of your words count as yours ("MVC-based", "UIs");
- changes nothing.

**What it can't catch, and the screen says so:** a claim in ordinary
words. Seen once in measuring: the label "REST API experience:" was put on
a WebSockets chat-app line. REST and API are in the resume elsewhere, so
the code has no objection. You read every edit before you copy it.

**Measured on 3 real jobs** (your own resumes, qwen3:8b on this PC, about
35 to 47 s each), three rounds:

| Round | Prompt | Shown | Dropped | What I saw reading every edit |
|---|---|---|---|---|
| 1 | first version | 11 | 7 | nothing invented, but edits **cut facts** ("reduced latency by 25%", a list of 5 databases), one turned "about 40 s" into "within 40 s"; 2 good edits dropped by mistake ("MVC-based", "UIs") |
| 2 | + "keep every fact" | 2 | 16 | overcorrected: the model copied 16 lines unchanged; the 2 shown only swapped a word |
| 3 | + "bring in the job's own words", with an example; "an unchanged line is useless" | 11 | 7 | useful: requirement-led lines with every fact kept. Dropped for real reasons: an invented "obtained by summer 2026", "about 40" made exact, one edit mixing in another project, two that altered the "before" line. One misleading label got through (above) |

After round 1 the check got the "leaves out" and "about" rules and the
hyphen/plural fix; the prompt was rewritten twice.

**In Evals:** a "Resume tailoring" fold (per model, when there is any):
times asked, edits shown out of suggested, and the drop reasons grouped
(added a number, added a skill or name, left out something of yours, made
an estimate exact, changed your line, no change). The 9 measuring runs are
in the test tracker's log: 54 suggested, 24 shown.

**Checks:** `tests/test_tailoring.py`, 16 tests (each rule, both ways,
the log, the bridge refusing during a run and without the resume file).
565 tests pass. Screenshots (dev server, made-up data): the section with
two edits and a dropped one, dark and light.

**Learned:** the strictness of a prompt and the usefulness of the result
pull against each other with a small model. The code check is what makes
the strict part safe, so the prompt can ask for real rewriting.

**Phase 19 is done.**

## Release checks for 2.0.0 ✅ (21–22 Nov 2026)

Your choices (21 Nov): release now as **2.0.0** (E5), "Like Windows"
stays (E4), interview practice waits (E8). Installer only (E9).

- `pytest`: 565 pass.
- `build_installer.py --test-install`: the Test Build (68 MB, app folder
  161 MB) passed the engine self-test and the window test, both in the
  build folder and installed; uninstalled with nothing left; your JobLens
  1.2.0 not touched.
- `check_real_update.py --old 1.2.1 --new 2.0.0`: **all four checks pass**
  (1.2.0 → 2.0.0, 2.0.0 → 2.0.1, Setup run by hand with JobLens in the
  tray, a failed update reopens the old JobLens and says so); your JobLens
  not touched.
- `measure_installed.py 5`, installed, medians of 5 runs:

| | 1.2.0 (pywebview) | 2.0.0 (Rust) |
|---|---|---|
| Installer | 64.8 MB | 64.5 MB |
| App folder | 158 MB | 158 MB |
| Time to data | 3.04 s | 1.44 s (53 % sooner) |
| Memory 1 s after | 572 MB | 515 MB (10 % less) |
| Peak, first 3 s | 594 MB | 536 MB |

- The release build: self-test and window test PASS; no PDF, database,
  `.env` or backup in the app folder.
  `JobLens-Setup-2.0.0.exe`: 67,663,417 bytes, SHA-256
  `948c84095fdc14ded91f7903531450fbe755855ced374f9766ce71cf1ead830e`.
- Release notes: [release-notes-version-3.md](release-notes-version-3.md).

## Release v2.0.0 ✅ (22 Nov 2026)
https://github.com/RAIF-KARANI/Job-hunt-assistent-agent/releases/tag/v2.0.0
- `main` fast-forwarded to `version-3` (`8c8e131`); you published the
  release with `gh release create`.
- **Checked after publishing:** Latest; not a draft or pre-release; tag →
  `8c8e131`; GitHub's SHA-256 of the installer matches the build
  (`948c8409…ead830e`); the updater (real API), asked as 1.2.0 and as
  1.0.3, offers v2.0.0 with that checksum; asked as 2.0.0, nothing.
- **Left for you:** update your own JobLens (Settings → Updates), open an
  interview `.ics` in your calendar, try Suggested edits on a real job.
  Phase 20 (interview practice) waits (E8).
