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
| 7 | Polish | Error handling, observability, LLM-as-judge, tests | ⏳ |
| 8 | Optional extras | n8n, web UI, tracing | ⏳ |

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

## Phase 7 — Polish ⏳
**Goal:** make it robust and trustworthy.
**Concepts:** error handling in agents; observability; LLM-as-judge; testing
non-deterministic systems.
**Tasks**
- [ ] Graceful failures: blocked page → ask for pasted text; search down →
      continue without research; model timeout → retry
- [ ] LLM-as-judge: second call checks each `SkillMatch` evidence really
      supports the requirement
- [ ] Compare `qwen3:8b` vs `qwen3:14b` on 3 jobs (quality vs speed)
- [ ] `pytest` tests for code-only parts (evidence check, URL verify, tracker)
- [ ] README with setup + usage
**Done when:** a broken URL or offline search doesn't crash the run.

## Phase 8 — Optional extras ⏳
Pick any:
- **n8n** trigger: a form/webhook in n8n calls `main.py`, emails you the draft
- **Web UI** with Streamlit: paste URL, see steps live, approve with a button
- **LangSmith** (or Langfuse, self-hosted) tracing to inspect every LLM call
- **Status updates:** `python main.py status <id> applied`
- **Follow-up reminders** for jobs applied > 7 days ago
