# Build Plan — JobLens version 3

Continues [version 2](../version-2/plan-version-2.md) (phases 12–16, released
up to **v1.2.0**). Decisions behind this plan are in
[decisions-version-3.md](decisions-version-3.md). What was done:
[progress-version-3.md](progress-version-3.md). Picking the work up again:
[handoff-version-3.md](handoff-version-3.md).

Legend: ✅ done · 🚧 in progress · ⏳ not started · 🟡 waiting for a decision

**Workflow rules:** branch `version-3`; no CI, so merge only after local
checks (version 2's D3 still applies: pytest, look at the app, the installer
build, the real update test). Commit and push after each step. **One release
at the end** (E1).

| # | Phase | What | Status |
|---|---|---|---|
| 17 | New look: the glass direction | your reference + prompt, adapted to JobLens; every screen, nothing lost | ✅ 17a to 17j done (17 Nov) |
| 18 | Rust (Tauri) spike | measure a Tauri shell against 1.2.0; adopt only if clearly better | 🚧 18a to 18c done (adopt); 18d next |
| 19 | New features | your list (to come) | 🟡 waiting for your list |
| 20 | Interview practice | AI-written practice questions and answers per job, checked against your resume | ⏳ (last, your choice) |

Release: **v2.0.0**, once, after all phases (E1, E5).

---

## Phase 17 — New look: the glass direction ✅

**Source:** your reference image (`referance/Glassmorphism Dashboard Design
Kit.png`) and prompt (`referance/ui promt`): dark glassmorphism, frosted
cards on a dark gradient, blue / purple / pink / orange / yellow accents,
Inter, gradient KPI cards, 16–24 px radii.

**Mockup:** https://claude.ai/artifact/94ZzgwybxR8ZHdWtKnEUt4 —
Dashboard, Tracker, Analyze, Evals, linked like the app (click the sidebar).
Made from JobLens's real screens and numbers; nothing in the app changed.
Source kept in [mockup/](mockup/).

### How the reference is adapted (see E3)
| In the reference | In JobLens |
|---|---|
| User profile + avatar | No accounts in JobLens: the slot shows the model status (ready / working, which model) |
| Notifications bell | The reminders: follow-ups and "Did you apply?" |
| Search in the top bar | Search jobs (today it's only on the Tracker) |
| White text on bright gradient cards | Dark text: white on those colours is 2.5:1, too faint to read. A switch in the mockup shows both |
| Muted text `#71717A` | `#8E8E99`: the given grey is 3.2:1 on a card, below the 4.5:1 minimum |
| Recharts / Tailwind / Framer Motion | Not added: the app's charts and CSS are its own, and the prompt says "no unnecessary dependencies" |

### Steps (after your OK on the mockup)
| Step | What | Done when |
|---|---|---|
| 17a ✅ | **Your review of the mockup**: what to keep, change, drop | you say go (16 Nov: "I am happy with the design") |
| 17b ✅ | **Tokens and base components**: colours, gradients, glass surfaces, radii, spacing, Inter (bundled, works offline) as CSS variables in `tokens.css`; buttons, inputs, selects, cards, badges, tabs, dialogs, tooltips | a component sheet screen shows every piece |
| 17c ✅ | **Shell**: sidebar with gradient active state, top bar (title, search, reminders, New analysis), page transitions | every page opens in the new shell |
| 17d ✅ | **Dashboard**: gradient KPI cards, the **job galaxy restyled** in the new palette (kept, your choice), Ready to apply, charts | the 3D galaxy, the flat map and "3D off" all match |
| 17e ✅ | **Tracker**: board, list, job details, follow-up email, interview prep, resume prompt | every dialog restyled; drag and drop still works |
| 17f ✅ | **Analyze**: steps, live log, review, the failed / out-of-quota panels, Continue banner | a full run looks right from start to approval |
| 17g ✅ | **Evals**: tiles, all charts in the new palette (checked with the palette validator), tables | charts readable; colour-blind check passes |
| 17h ✅ | **Settings, setup wizard, quick-analyze box** | first-run setup looks right |
| 17i ✅ | **Light theme check** (E4: both themes are built in every step) | every screen looks right in light and dark |
| 17j ✅ | **Accessibility and sizes**: contrast, keyboard, reduced motion; window sizes from 720 px to a 2560 px monitor | checked in the real window |

## Phase 18 — Rust (Tauri) window 🚧
**Your goals:** a smaller, faster app, and learning Rust. **Your rule:** move
the shell to Rust only if it is clearly better; otherwise the spike stays a
learning project (E2).

The agent stays Python either way; only the shell could move (window, tray,
shortcut, updater, the bridge). Python still ships beside it.

| Step | What |
|---|---|
| 18a ✅ | A Tauri window showing the built UI, one bridge call into the Python agent (a sidecar) |
| 18b ✅ | Measure against 1.2.0: installer size (68 MB), app folder (161 MB), time to a ready window (~3 s), memory, a bridge call's time |
| 18c ✅ | Decided: adopt (E2, 17 Nov). 36 % faster, 20 % less memory, 5 % smaller |
| 18d | Everything today's window does, in the Rust window (E6). Sub-steps below |

### 18d — the Rust window, feature by feature (E6)

| Step | What | Done when |
|---|---|---|
| 18d1 ✅ | **Into the app**: the spike becomes `desktop_tauri/` (Rust) and `desktop_web/engine.py` (Python); the pipe carries Python's requests to the window too (show, hide, notify, a dialog) | the Rust window runs JobLens from source like `python -m desktop_web` does |
| 18d2 ✅ | **File dialogs**: Add PDFs, Save as (CSV, cover notes, prep sheets) | every export and the resume upload work |
| 18d3 ✅ | **Tray**: icon, menu (open, status, follow-ups, stop the run, quit), notifications and their clicks; the close button hides to the tray when it should | the tray behaves like 1.2.0's |
| 18d4 ✅ | **Quick-analyze box**: the global shortcut (kept in Python) opens the small box window | Ctrl+Alt+J works with the window hidden |
| 18d5 | **One copy at a time, Start with Windows (in the tray), closing at Windows shutdown** | a second start brings the first back; sign-in starts it hidden |
| 18d6 | **Packaging**: PyInstaller builds the agent, Tauri the window, Inno Setup the installer (same app id); `--smoke` and `--self-test` again | `scripts/build_installer.py --test-install` passes |
| 18d7 | **Updates**: from an installed 1.2.0 to this build, with the real update test | `scripts/check_real_update.py` passes |
| 18d8 | **Measure again, installed**: start time, memory, size against 1.2.0 | the numbers are in the progress log |

## Phase 19 — New features 🟡
Your list, when you have it. A feature that adds a screen is built in the
new look.

## Phase 20 — Interview practice ⏳ (last, your choice)
Left out of 1.2.0's prep sheet on purpose (D43): practice questions for a
job and suggested answers, written by the model and checked against your
resume like the cover note is (no claim the resume doesn't show). Built in
the new look, measured on a few real jobs.
