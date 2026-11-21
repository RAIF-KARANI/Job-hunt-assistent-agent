## JobLens 2.0.0: a new look, a faster window, four new features

**New look**
- Every screen redesigned in frosted glass, in **dark and light** (or **Like Windows**), with a light/dark switch in the top bar. The 3D job galaxy stays, restyled.
- A grouped sidebar, a top bar with job search and reminders, and **Ctrl+K** for quick actions.

**A faster window**
- The window is now written in **Rust (Tauri)**; the AI agent is still Python, beside it. On this PC your data shows in **1.4 s instead of 3.0 s**, with about **10 % less memory**, at the same size.

**New**
- **Insights:** what your tracker says about your search: the share of applications that reached an interview, by resume, by job site and by fit score, and how long companies take to answer. Plain counts, no AI. A group with fewer than 5 applications shows its counts but no percentage. JobLens records status changes from 2.0.0 on, so the time to an answer fills in from your next applications.
- **Interview calendar:** a reminder the evening before and an hour before an interview (click it to open the job), **Add to calendar** (an `.ics` file for Outlook, Google or Apple), and the week's interviews at the top of the Dashboard's "Do next".
- **Suggested resume edits** (Tracker → a job → Resume prompt): your AI model rewrites lines of your own resume for the job. Before you see them, JobLens drops any edit that adds a number, skill or name your resume doesn't show, or leaves one of yours out. It can't catch a claim in ordinary words, so read each edit before you copy it.
- **Backup and restore** (Settings → Your data): the tracker, resumes, cover notes and settings in one file. **API keys are never in it.** A restore shows what's in the file first and backs up what you have now. An automatic backup is made every week and before each update (the last 4 are kept).

**Updating:** Settings → Updates, from 1.0.3 or later. JobLens closes and opens again as 2.0.0. Your data stays; a backup of it is made just before the update.

**Changed:** 2.0.0 comes as the installer only. The portable `.zip` is gone for now: the new window hasn't been tested as a loose folder.

| File | SHA-256 |
|---|---|
| JobLens-Setup-2.0.0.exe | `948c84095fdc14ded91f7903531450fbe755855ced374f9766ce71cf1ead830e` |
