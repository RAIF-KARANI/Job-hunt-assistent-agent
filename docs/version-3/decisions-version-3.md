# Decisions — JobLens version 3

Version 2's decisions (D1–D43) are in
[../version-2/decisions-version-2.md](../version-2/decisions-version-2.md).
Version 3's are numbered E1, E2… so the two never mix.

## E1 — Version 3 is one big release ✅ (16 Nov 2026, your choice)
Redesign, features, interview practice, and Rust if it wins, all in one
release at the end. Work goes on branch `version-3`, committed and pushed
after each step, like Phase 16.

## E2 — Rust: a spike first; adopt only if clearly better ✅ (16 Nov 2026, your choice)
Your goals: a smaller, faster app, and learning Rust. If the Tauri shell is
only about equal to 1.2.0, the app stays as it is and the spike was a
learning project.
- **Open:** what "clearly better" means. Proposal: the installer at least 25 %
  smaller, or the window ready at least 30 % sooner, and nothing worse (tray,
  shortcut, updates, memory).

## E3 — The new look: your glass reference, adapted ✅ direction, 🟡 details (16 Nov 2026)
Your reference image and prompt set the direction: dark glassmorphism,
Inter, your five accents, gradient KPI cards. A mockup of four screens came
first, before any app code: https://claude.ai/artifact/94ZzgwybxR8ZHdWtKnEUt4
(source in [mockup/](mockup/)).
- **Adapted where the reference doesn't fit JobLens:** no accounts, so no
  avatar or profile (the model status instead); the bell is the reminders.
- **Changed for readability:** dark text on the bright gradient cards
  (white is 2.5:1 there), and the muted grey lightened from `#71717A` to
  `#8E8E99` (4.8:1 instead of 3.2:1 on a card).
- **No new libraries** (Tailwind, Recharts, Framer Motion): the app's own
  CSS and charts get the new look; your prompt asks for no unnecessary
  dependencies, and the app works offline.
- **The 3D job galaxy stays**, restyled (your choice).
- **Open:** your review of the mockup.

## E4 — Light and dark, both glass, with a toggle ✅ (16 Nov 2026, your choice)
You asked for a light mode in a fully see-through glass style, and a
light / dark toggle. So version 3 has both themes in the glass look; the
old-style light theme goes.
- Every colour in the mockup is now a theme variable with a dark and a
  light value, so Phase 17 builds both themes in each step (step 17i is
  no longer a separate job at the end).
- The toggle is a sun / moon button in the top bar. The mockup remembers
  the choice on this PC.
- **Open:** today the app can also follow Windows. Keep that as a third
  choice in Settings (proposed), or only the toggle?

## E5 — The release number is 2.0.0 🟡 proposed
A new look in every screen is a big change for the people using it.

## Open questions ❓
- Your review of the mockup (E3).
- Follow Windows as a third theme choice (E4).
- "Clearly better" for Rust (E2).
- The release number (E5).
- Your feature list (Phase 19).
