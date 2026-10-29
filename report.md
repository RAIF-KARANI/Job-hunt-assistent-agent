# JobLens — Project Report

*An AI job application assistant, built as a learning project for AI agents.*
**Author:** Raif Karani · **Period:** 27–29 October 2026 · **Version:** 0.3.0 ·
**Repository:** github.com/RAIF-KARANI/Job-hunt-assistent-agent (private)

---

## 1. Summary

JobLens takes a job posting link and, in about three minutes on a laptop GPU:

1. **reads the posting** and extracts its key facts,
2. **compares it with your resumes**, picks the best one and scores the fit,
   backing every claimed skill with a quote that is **checked**,
3. **researches the company** with an agent that chooses its own web searches,
4. **saves the job** to a local tracker,
5. **drafts a tailored cover note** that is saved **only if you approve it**.

It runs **fully on your PC** by default (Ollama + Qwen3), ships as a Windows
installer with a first-run setup wizard, and has a **built-in eval system**
that measures its own quality without any server.

The project went through 12 phases (0–11), each adding one capability and
one agent-engineering concept. Every phase is documented step by step in
`progress.md`.

---

## 2. Goals and outcome

| Goal (from `idea.md`) | Outcome |
|---|---|
| Learn how AI agents work: loop, tools, state, human-in-the-loop | ✅ Each concept built and explained in its own phase |
| Read a posting, compare with resume, research company, track job, draft note | ✅ All five steps, as one LangGraph workflow |
| Nothing saved without explicit approval | ✅ Enforced in code (`PermissionError` guardrail), tested |
| Explain what the agent is doing at every step | ✅ Live step log in CLI, web UI and desktop app |
| (Added along the way) usable by people without Python | ✅ JobLens Windows app + installer (v0.3.0) |
| (Added along the way) measure quality | ✅ Built-in run log, quality checks, user ratings |

---

## 3. What was built

### The agent (`job_agent/`)
- **Workflow with one agent inside** (LangGraph): the step order is fixed in
  code; only company research lets the LLM decide (ReAct loop with
  DuckDuckGo web/news search tools, capped at 5 tool calls).
- **Structured output** everywhere (Pydantic models), with automatic retries.
- **Verification layer**: resume quotes must exist in the resume; an
  **LLM-as-judge** rejects quotes that don't actually prove the claim;
  invented source URLs and news dates are removed; unverified numbers in the
  cover note are flagged.
- **Fit score computed in code** from verified facts, not by the LLM.
- **Human-in-the-loop**: `interrupt()` pauses the graph for approve / edit /
  reject; a checkpointer lets a paused run survive restarts.
- **SQLite tracker** with idempotent upserts and an application status.

### Four ways to use it
| Front end | File | Notes |
|---|---|---|
| CLI | `main.py` | developer use |
| Web UI | `app.py` (Streamlit) | reload-safe paused runs |
| Monitoring dashboard | `monitor.py` (Streamlit + Altair) | developer tool, Langfuse-based |
| **Desktop app JobLens** | `desktop_app.py` + `desktop/` (Qt) | Analyze, Tracker, Dashboard, Settings tabs |

### Distribution
- **`JobLens-Setup-0.3.0.exe`** (81 MB, Inno Setup): per-user install (no
  admin), shortcuts, Windows *Apps* entry, uninstaller that **asks whether to
  keep your data**.
- **Portable zip** (111 MB).
- **First-run Setup Wizard**: choose local AI or a Claude API key; for local
  AI it **checks the PC** (RAM, GPU memory, disk), **recommends a model**,
  installs Ollama via winget and downloads the model with a progress bar.
- Published as GitHub Releases v0.1.0 → v0.2.0 → **v0.3.0 (latest)**.

### Observability and evals
- **Langfuse** (self-hosted with Docker) for developer tracing.
- **Built-in run log** (Phase 11), always on, no server: every run's steps,
  LLM calls, tokens, timings and tool failures in local SQLite.
- **Automatic quality checks** per run and **user ratings** of the fit score
  and cover note, all charted on the desktop Dashboard.

---

## 4. Key results and measurements

| Measurement | Value | Source |
|---|---|---|
| Full analysis time (qwen3:8b, RTX 4060 laptop) | ~174–186 s | run log, Langfuse |
| Slowest step | analyze_fit ~78–85 s (2 analyses + 2 judge calls) | run log |
| LLM calls / tokens per full run | 9 calls, ~18–20k tokens | run log, Langfuse |
| Latency correlation with **output** tokens | **0.90** (input tokens: 0.16) | Langfuse, Phase 8c |
| qwen3:8b vs qwen3:14b (fit analysis) | 76 s vs 291 s; 14b gave a nonsensical 4/100 | Phase 7 |
| Judge on one real run | rejected **5 of 12** claims → **58 %** evidence verified | Phase 11 |
| qwen3:8b memory at 16k context | 6.3 GB, 100 % GPU | `ollama ps`, Phase 10 |
| Installer / app folder / zip size | 81 MB / 230 MB / 111 MB | Phase 9f–10 |
| Automated tests | **92 passing** (13 test files, no LLM needed) | `pytest` |
| Codebase | ~5,400 lines of app code; 22 commits | git |

**The three most important findings**
1. **Verification beats model size.** Code checks + a judge improved
   quality more than switching to a model 2× larger (which was ~4× slower).
2. **Output tokens drive speed** on a local model. To make the agent
   faster, ask for shorter answers; trimming prompts matters much less.
3. **The first LLM call over-claims.** The judge rejects a large share of
   skill claims (58 % pass rate in the measured run), which is why the score
   is computed only from claims that survive every check.

---

## 5. Lessons learned (selected)

- **Code for facts, LLM for understanding.** Downloading, parsing, saving
  and scoring belong in code.
- **Don't trust, verify**, and when verification needs judgment, use a
  second, narrowly scoped LLM call.
- **Guardrails live in code, not prompts** (approval gate, tool-call limit).
- **Tools must fail gracefully:** return errors as text so the agent recovers.
- **Measure instead of guessing:** model choice, memory needs, latency.
- **Look at the real thing:** screenshots, frozen-app self-tests and a real
  install / uninstall found bugs unit tests could not (layout bugs, an exit
  race, Windows' 260-character path limit, a GPU memory reading capped at 4 GB).
- **Every component costs upkeep:** the n8n + HTTP API integration was built,
  tested and then deliberately removed when the use case didn't need it.

---

## 6. Limitations

- The **verdict sentence** is written before the judge runs and can mention
  claims the judge later removed (the score itself is safe).
- Research facts without a URL or date (e.g. employee counts) aren't verified.
- The app is **not code-signed** (Windows SmartScreen warning on first run).
- **Windows only**; local AI needs ~8–16 GB RAM (API option for weaker PCs).
- The repository is **private**, so only the owner can download releases.
- The Streamlit monitor still reads Langfuse; the desktop Dashboard uses the
  built-in run log.

---

## 7. Status

**Complete.** All planned phases (0–11) are done, tested, committed and
released as v0.3.0. See **`handover.md`** for how to run, build, release and
continue the project, and **`progress.md`** for the full step-by-step story.
