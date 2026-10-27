# Build Plan — Job Hunt Assistant

Each phase adds **one working piece** and teaches **one or two agent
concepts**. Every phase ends with a test script you can run yourself.
Details of what was actually done in each phase live in
[progress.md](progress.md); the design is in [architecture.md](architecture.md).

Legend: ✅ done · 🚧 in progress · ⏳ not started

| # | Phase | Main concept | Status |
|---|---|---|---|
| 0 | Setup + first LLM call | LLM API basics, provider-agnostic design | ✅ |
| 1 | Read a job posting | Structured output | ✅ |
| 2 | Resume fit analysis | Context, verification, "LLM judges / code decides" | ✅ |
| 3 | Company research | Tools, the agent loop, first LangGraph graph | ✅ |
| 4 | Job tracker (SQLite) | Persistent state | ✅ |
| 5 | Cover note + approval | Human-in-the-loop, `interrupt()`, checkpointer | ✅ |
| 6 | Full pipeline + CLI | Workflow graph, shared state | ✅ |
| 7 | Polish | Error handling, observability, LLM-as-judge, tests | ✅ |
| 8 | Optional extras | Score in code, web UI, tracing, monitoring dashboard (n8n tried, removed) | ✅ |
| 9 | Windows desktop app | Packaging, local-first distribution | ⏳ future |

---

## Phase 0 — Setup + first LLM call ✅
**Goal:** talk to the local Qwen model from Python through LangChain.
**Concepts:** messages (System/Human/AI), `.invoke()`, virtual environments,
config via `.env`, one factory function for the LLM.
**Tasks**
- [x] Create `.venv`, `requirements.txt`, `.gitignore` for Python + secrets + `data/`
- [x] `.env.example` → `.env` with provider/model settings
- [x] `job_agent/llm.py` — `get_llm()` supporting Ollama (active) + Claude/OpenAI/Gemini (commented paths)
- [x] `hello_llm.py` test
**Done when:** `python hello_llm.py` prints a reply from qwen3. ✅

## Phase 1 — Read a job posting ✅
**Goal:** URL → clean `JobPosting` object.
**Concepts:** structured output with Pydantic; code vs. LLM responsibilities;
context window size.
**Tasks**
- [x] `fetch_page_text()` — requests + BeautifulSoup, strip noise, detect JS/login pages
- [x] `JobPosting` model with field descriptions as instructions
- [x] `extract_job_posting()` with `with_structured_output`
- [x] Raise Ollama context window (`OLLAMA_NUM_CTX=16384`)
- [x] `phase1_read_posting.py` (URL or `.txt` fallback)
**Done when:** a real posting is extracted correctly. ✅ (GitLab, ~23 s)

## Phase 2 — Resume fit analysis ✅
**Goal:** pick the better of your resumes and explain the fit.
**Concepts:** giving the LLM context; field order as a reasoning aid;
hallucination and how to verify; "LLM judges, code decides".
**Tasks**
- [x] `load_resumes()` — every PDF in `data/`
- [x] `SkillMatch`, `FitAnalysis`, `ResumeMatch` models
- [x] One focused LLM call per resume
- [x] Evidence verification in code (quote must exist in resume)
- [x] Winner chosen by code, tie-break on verified matches
- [x] `phase2_fit.py`
**Done when:** scores + verified evidence are printed, fake claims are dropped. ✅

## Phase 3 — Company research agent ✅
**Goal:** the LLM researches the company on its own using search tools.
**Concepts:** tools (`@tool`), `bind_tools`, the ReAct loop, LangGraph
`StateGraph` / nodes / conditional edges / `ToolNode`, loop limits, streaming steps.
**Tasks**
- [x] `web_search` + `news_search` tools (DuckDuckGo), Tavily as commented alternative
- [x] LangGraph graph: `agent` ⇄ `tools`, `tools_condition`
- [x] Hard limit `MAX_TOOL_CALLS` enforced in code
- [x] Stream and print every agent step
- [x] Summarize into `CompanyBrief`, verify source URLs
- [x] `phase3_research.py` (also prints the graph as Mermaid)
**Done when:** the agent picks its own searches and returns a brief with real sources.

## Phase 4 — Job tracker (SQLite) ✅
**Goal:** every analyzed job is saved and can be listed later.
**Concepts:** persistence (agent memory across runs); idempotency (same URL
twice = update, not duplicate); keeping the DB layer free of LLM calls.
**Tasks**
- [x] `job_agent/tracker.py`: `init_db()`, `save_job()` (upsert by URL),
      `list_jobs()`, `get_job()`, `update_status()`
- [x] Schema from architecture.md §6 (`jobs`, `cover_notes`)
- [x] `phase4_tracker.py`: `add`, `list`, `show`, `status` commands
- [x] Upsert keeps your `status`; research failure still saves the job
- [ ] Learn: open `data/jobs.db` in a viewer (e.g. DB Browser for SQLite) — your turn!
**Done when:** running the same URL twice leaves one row with updated data. ✅

## Phase 5 — Cover note + human approval ✅
**Goal:** draft a tailored note; nothing is saved without your OK.
**Concepts:** prompt design for writing tasks; human-in-the-loop;
LangGraph `interrupt()` + `Command(resume=...)`; checkpointer; guardrails in
code; serialization allow-lists.
**Tasks**
- [x] `draft_cover_note()` — uses verified matches, talking points, research, resume
- [x] Number check: unknown numbers shown as warnings
- [x] Graph: `draft` → `review (interrupt)` → `save` / back to `draft` / END
- [x] Edit loop: feedback in the system message, overrides defaults
- [x] `save_cover_note()` refuses unless approved; saves to DB + `data/cover_notes/*.md`
- [x] Allow-list our models in the checkpoint serializer
- [x] `phase5_cover_note.py <job-id>`
- [ ] **Your turn:** approve a note yourself and check it in the DB viewer
**Done when:** approve saves, edit re-drafts with feedback, reject saves nothing.
✅ edit + reject + guardrail tested; approve is yours to try.

## Phase 6 — Full pipeline + CLI ✅
**Goal:** one command does everything.
**Concepts:** workflow graph with shared typed state; subgraphs; nested
agent; conditional entry; resuming after interrupt.
**Tasks**
- [x] `JobHuntState` (inherits `CoverNoteState`) in `job_agent/graph.py`
- [x] Nodes wrapping phases 1–4; Phase 5 graph added as a **subgraph**
- [x] `check_tracker` conditional entry: skip analysis for tracked URLs; `--fresh` to redo
- [x] `main.py`: run, `list`, `show`, `status`, `graph`
- [x] Clear step-by-step console output `[1/5] … [5/5]`
**Done when:** `python main.py <url>` runs all six steps end to end. ✅ (176 s new job, 13 s reused)

## Phase 7 — Polish ✅
**Goal:** make it robust and trustworthy.
**Concepts:** error handling in agents; human as fallback; LLM-as-judge;
retries; testing non-deterministic systems; measuring model choices.
**Tasks**
- [x] Blocked/unreadable page → graph pauses (`interrupt`) and asks you to paste text
- [x] Search down → continue without research (Phase 3/6); tool errors → text
- [x] Malformed structured output → automatic retry (`structured_llm()`, 3 attempts)
- [x] Ollama not running / model missing → clear message before the run starts
- [x] LLM-as-judge: second call checks each `SkillMatch` quote really proves the
      requirement; unproven claims move to gaps (`JUDGE_EVIDENCE` in `.env`)
- [x] `compare_models.py` + 8b vs 14b comparison on job #1
- [x] `pytest` suite: 19 tests for code-only parts (no LLM, temp DB)
- [x] README with setup + usage
- [ ] **Your turn:** run `compare_models.py` on 2–3 more jobs before switching models
**Done when:** a broken URL or offline search doesn't crash the run. ✅

## Phase 8 — Optional extras ✅
You chose all four, built in this order.

### 8a — Fit score computed in code ✅
**Concepts:** deterministic scoring; facts vs. numbers; explainability.
- [x] Remove `fit_score` from the LLM's `FitAnalysis`
- [x] `compute_fit_score()`: proven / (proven + required gaps + 0.3 × nice-to-have gaps)
- [x] `ResumeMatch.fit_score` + `score_breakdown`, set after the judge
- [x] `python main.py rescore` (no LLM) + 7 tests
- [ ] Next small fix: write the verdict from the final facts (after the judge)

### 8b — Streamlit web UI ✅
**Concepts:** UI for agents; persistent checkpointer (SQLite) so a paused run
survives page reloads; streaming steps to a UI; headless UI tests.
- [x] Paste URL → live step log → draft with Approve / Rewrite / Reject buttons
- [x] Edit the draft text directly before approving
- [x] Tracker table, score breakdown, status changes, "draft a note" per job
- [x] Paste-text fallback in the UI
- [x] SQLite checkpointer + thread id in the URL → reload-safe
- [x] Tested headlessly with Streamlit's `AppTest` (incl. reload + reject)

### 8c — Tracing ✅
**Concepts:** observability; traces, spans, generations, sessions, scores;
callbacks; self-hosting with Docker Compose.
- [x] Self-hosted Langfuse v4 in `infra/langfuse` (official compose + override:
      no port clashes, localhost only, telemetry off, generated secrets)
- [x] `job_agent/tracing.py`: `TRACING=off|langfuse|langsmith`
- [x] Wired into CLI + web UI; thread_id = session; tags `cli`/`web` + model
- [x] Approve/edit/reject recorded as a `cover_note_decision` score
- [x] Traced a full run and analyzed it via the API (54 observations, 9 LLM calls)
- [ ] **Your turn:** explore the trace at http://localhost:3000

### 8d — n8n integration ↩️ built, then removed
**Concepts:** agents inside automation tools; exposing an agent as an API;
async jobs (202 + callback/webhook); API keys; human-in-the-loop in n8n
(Wait node + resume URL) mirroring LangGraph's interrupt.
- [x] Built and tested end to end: FastAPI `api.py` + n8n form workflow (commit `f41b7f9`)
- [x] **Removed** after the deployment decision: personal use + a future
      Windows app don't need an HTTP server or an automation tool.
      Lessons kept in progress.md 8d.

### 8e — Monitoring dashboard ✅
**Concepts:** monitoring vs. tracing; KPIs; reading an observability API;
pure data layer + thin UI; choosing chart forms; validating colors;
render-and-look testing.
- [x] `job_agent/monitoring.py`: fetch Langfuse observations/scores (cursor
      paging, no prompts) + tracker; pure `build_*` tables
- [x] `monitor.py`: KPI tiles, time per step, latency vs tokens, tokens per run,
      tool ok/failed, decisions, fit scores, status funnel, recent runs → Langfuse links
- [x] Filters (time range, cli/web), 60 s cache, works with Langfuse down
- [x] Palette validated (light + dark); blue accent theme (`.streamlit/config.toml`)
- [x] Rendered in a real browser and fixed 4 layout bugs; 6 tests (32 total)

## Phase 9 — Windows desktop app 🚧
**Why:** chosen after comparing deployment costs (see progress.md,
"Deployment decision"): the LLM runs on each user's own PC, so running
costs are **$0**, and no user data is stored on a server.
**Decisions:** native **Qt (PySide6)** UI; Ollama by default + optional
Claude API key; monitoring dashboard included as a tab.
**Concepts:** where desktop apps keep data; Qt widgets/layouts;
signals & slots; keeping the GUI thread free; packaging Python apps.

| Step | What | Status |
|---|---|---|
| 9a | `paths.py` (dev vs installed data folder), `settings.py` (read/write .env), `llm_status()` | ✅ |
| 9b | Qt window + **Settings** tab (model/API key, resumes, options, connection check) | ✅ |
| 9c | **Analyze** tab: agent in a background thread, live log, approve / rewrite / reject | 🚧 |
| 9d | **Tracker** tab: jobs table, details, status changes | ⏳ |
| 9e | **Dashboard** tab: tracker charts + trace charts when Langfuse is up | ⏳ |
| 9f | Package with PyInstaller (folder + `.exe`), docs | ⏳ |
| — | Optional: code-signing certificate (~$100–400/yr) to avoid the SmartScreen warning | not planned |

### Other ideas (not planned)
- Follow-up reminders for jobs applied > 7 days ago
