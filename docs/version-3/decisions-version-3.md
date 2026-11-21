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
- **Measured (18b, 17 Nov):** 36 % faster to your data, 19–24 % less memory,
  5 % smaller. Passes the proposed bar on speed, not on size; tray,
  shortcut and updates are not built yet.
- **Decided (18c, 17 Nov, your choice): adopt Tauri.** Version 3's window
  moves to Rust (step 18d); the agent stays Python. "Nothing worse" is now
  the bar for 18d: every feature of today's window works the same before
  the release, and the real update test passes.

## E3 — The new look: your glass reference, adapted ✅ (16 Nov 2026; mockup approved the same day)
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
- **Approved:** after several rounds on the mockup you said to start building. What it does is listed in
  [features-version-3.md](features-version-3.md).

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

## E6 — How the Rust window is built ✅ (17 Nov 2026, proposed with 18d)
- **Rust shows, Python decides.** The decisions behind the tray (its text,
  when to remind you, what the close button does) stay in Python, where
  they are already tested; Rust only draws the tray, the windows and the
  dialogs, and tells Python what you clicked. One pipe carries both ways.
- **Kept in Python because they work the same with any window:** the global
  shortcut (Windows sends it to the Python thread that registered it), the
  updater (download, check, run the installer), Start with Windows (a
  registry entry, now pointing to the new program).
- **Moved to Rust:** the window and the quick-analyze box, the tray icon and
  its menu, notifications, file dialogs (Add PDFs, Save as), one copy at a
  time, closing when Windows shuts down.
- **The installer stays Inno Setup with the same app id**, so JobLens 1.2.0
  can update itself to 2.0.0 like every update before. It installs two
  programs: `JobLens.exe` (Rust) and the agent beside it (PyInstaller).

## E7 — Phase 19 is four features ✅ (21 Nov 2026, your choice)
You had no list, so a list of suggestions was made from what JobLens
doesn't do yet. You chose 1, 2, 3 and 5:

| # | Feature | What already exists | What Phase 19 adds |
|---|---|---|---|
| 1 | Resume tailoring | the resume prompt (14g, D33): the skills gap and a prompt to paste into another AI | the model writes before → after edits of your own bullets, each checked against your resume (19d) |
| 2 | Insights | the Dashboard's pipeline counts | response rate by resume, by site, by fit band; time to answer; where jobs stop (19c) |
| 3 | Interview calendar | the interview date and contact on a job (14h), shown on the board and in the prep sheet | reminders before it, `.ics` export, Upcoming on the Dashboard (19b) |
| 5 | Backup | CSV export of the tracker (14i) | a full backup and restore, and automatic backups (19a) |

Not chosen: contacts per job (the contact field from 14h stays as it is),
batch analyze, duplicate warning, salary and location filters, rejection
notes. Advised against: pulling jobs from LinkedIn or Indeed (their terms
forbid it, and it breaks often).

Proposed with it (say if you want any of them different):
- **The backup leaves out API keys.** A backup is a file you may copy to a
  USB stick or a cloud drive; keys stay only in `.env`. After a restore on
  a new PC you type the key once.
- **No Excel (.xlsx) export:** the CSV already opens in Excel, and .xlsx
  would add a dependency or a lot of code for the same table.
- **Insights only count what was recorded.** Jobs from before 19c have
  their current status but no history, so "time to answer" starts from
  19c's jobs; the screen says so instead of guessing.
- **Tailoring uses the model you set in Settings**, so with a cloud model
  your resume text goes to it, as it already does for the analysis.

## Open questions ❓
- Follow Windows as a third theme choice (E4).
- The release number (E5).
