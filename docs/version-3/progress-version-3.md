# Progress Log — JobLens version 3

What was done in each version-3 step, what went wrong, and what it
teaches. Plan: [plan-version-3.md](plan-version-3.md) · Decisions:
[decisions-version-3.md](decisions-version-3.md) · Where things stand:
[handoff-version-3.md](handoff-version-3.md)

| Step | Status | Result |
|---|---|---|
| Planning | ✅ | 4 phases (17 new look, 18 Rust spike, 19 your features, 20 interview practice); E1–E5 recorded |
| Mockup | ✅ | 4 linked screens in your glass style: https://claude.ai/artifact/94ZzgwybxR8ZHdWtKnEUt4 (source in [mockup/](mockup/)) |
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
