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
