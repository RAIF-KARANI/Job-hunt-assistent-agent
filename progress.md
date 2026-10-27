# Progress Log — Job Hunt Assistant

A detailed record of **what was built in each phase, why, what went wrong,
and what it teaches**. Read it top to bottom as a learning journal.
Plan: [plan.md](plan.md) · Design: [architecture.md](architecture.md) · Idea: [idea.md](idea.md)

## Overall status

| Phase | Status | Main result |
|---|---|---|
| 0 — Setup + first LLM call | ✅ Done | Local qwen3:8b answers through LangChain |
| 1 — Read a job posting | ✅ Done | URL → structured `JobPosting` in ~23 s |
| 2 — Resume fit analysis | ✅ Done | Best resume picked with verified evidence (~60 s) |
| 3 — Company research agent | ✅ Done | LLM chooses its own searches; brief with verified sources (~50 s) |
| 4 — Job tracker (SQLite) | ✅ Done | Jobs saved to `data/jobs.db`; re-runs update, never duplicate |
| 5 — Cover note + approval | ✅ Done | Graph pauses for your approve / edit / reject; nothing saved without approval |
| 6 — Full pipeline + CLI | ✅ Done | `python main.py <url>` runs everything; tracked URLs skip to the cover note |
| 7 — Polish | ✅ Done | Retries, paste fallback, LLM-as-judge, 19 tests, README, model comparison |
| 8 — Optional extras | ✅ Done | 8a score in code · 8b web UI · 8c tracing · 8d n8n + API (built, then removed) · 8e monitoring dashboard |
| 9 — Windows desktop app | 🚧 In progress | 9a data folder ✅ · 9b Qt window + Settings ✅ · 9c Analyze ✅ · 9d Tracker ✅ · 9e Dashboard ✅ · 9f packaging next |

**Progress: every phase (0–8, incl. 8e monitoring dashboard) complete. 🎉 Next: a Windows desktop app (Phase 9). See "Deployment decision" and "Where to go next" at the end.**

---

## Phase 0 — Setup + first LLM call ✅

### Goal
Get Python talking to the local Qwen model through LangChain, in a way that
lets us switch models later without touching code.

### What was done
1. **Checked the machine:** Python 3.13.1, Ollama 0.40 with `qwen3:8b`,
   `qwen3:14b`, `llama3.2`, `qwen3-embedding`. Chose `qwen3:8b` (supports tool
   calling, fast enough).
2. **Virtual environment** `.venv/` — a private Python install for this project
   so its packages never clash with other projects.
3. **`requirements.txt`** — every package with a comment saying why it's there.
   Alternate providers (Claude, OpenAI, Gemini) are listed but commented out.
4. **`.gitignore`** — added `.venv/`, `__pycache__/`, `.env` (secrets) and
   `data/` (resumes, database) so private files never reach GitHub.
5. **`.env.example` → `.env`** — settings live outside the code:
   `LLM_PROVIDER`, `LLM_MODEL`, `LLM_TEMPERATURE`, `OLLAMA_BASE_URL`,
   `OLLAMA_REASONING`.
6. **`job_agent/llm.py`** — `get_llm()` factory. Reads `.env`, returns a
   LangChain chat model. Ollama is active; Claude/OpenAI/Gemini branches are
   ready (imports happen inside each branch, so you only need the package
   for the provider you use).
7. **`hello_llm.py`** — sends a `SystemMessage` + `HumanMessage`, prints the reply.

### Problems hit
- **pip download timed out** (slow connection to PyPI) → retried with
  `--default-timeout=120 --retries 5`. Worked.

### Concepts learned
- **Messages:** `SystemMessage` (instructions), `HumanMessage` (user),
  `AIMessage` (model reply), later `ToolMessage` (tool result). An agent
  is basically this list growing.
- **Provider-agnostic design:** all LangChain chat models share `.invoke()`,
  `.with_structured_output()`, `.bind_tools()`. Only `llm.py` knows which one.
- **Qwen3 thinking mode:** `reasoning=True` makes it think step by step first
  (slower, inspectable); we keep it `False` for speed.

### Try it
```powershell
.venv\Scripts\activate
python hello_llm.py
```

---

## Phase 1 — Read a job posting ✅

### Goal
Turn a job posting URL into a clean, typed Python object.

### What was done
1. **`job_agent/models.py` → `JobPosting`** — Pydantic model with title,
   company, location, employment_type, seniority, salary, summary,
   required_skills, nice_to_have_skills, responsibilities. Each field has a
   `description` that the LLM reads as an instruction.
2. **`job_agent/posting.py` → `fetch_page_text(url)`** (no AI):
   - `requests.get` with a browser `User-Agent` (some sites block scripts)
   - `raise_for_status()` turns 403/404 into errors
   - BeautifulSoup removes `<script>`, `<style>`, `<nav>`, `<header>`,
     `<footer>`, `<svg>` and keeps visible text
   - < 200 chars of text → clear error ("JavaScript-only or login page —
     paste the text into a .txt file instead")
   - Cut to 30,000 chars so it fits in the model's context
3. **`extract_job_posting(text)`** (AI): `get_llm().with_structured_output(JobPosting)`
   with a system prompt: *use only information in the text, never invent,
   'Not specified' if missing*.
4. **Context window fix:** added `OLLAMA_NUM_CTX=16384` to `.env` and
   `llm.py`. Ollama's default is small, and text beyond it is **silently cut
   off** — the model would never see the end of the posting.
5. **`phase1_read_posting.py`** — accepts a URL or a `.txt` file.

### Result
GitLab "Backend Engineer (Python), AI Engineering: Agent Foundations":
10,626 chars of page text → correct title, company, remote locations,
"Intermediate" seniority (inferred), 6 required skills, 8 responsibilities.
~23 s.

### Concepts learned
- **Structured output:** LangChain converts the Pydantic class into a JSON
  schema, the model answers in JSON, Pydantic validates it. The rest of the
  program never deals with free text.
- **Field descriptions are prompts.** "Infer from title/years" is why
  seniority was filled even though the page had no "seniority" label.
- **Code for facts, LLM for understanding.** Downloading and cleaning are
  deterministic → plain code. Only "understanding the text" uses the LLM.

### Try it
```powershell
python phase1_read_posting.py https://job-boards.greenhouse.io/gitlab/jobs/8704363002
python phase1_read_posting.py data\job.txt      # when a site blocks fetching
```

---

## Phase 2 — Resume fit analysis ✅

### Goal
Compare your resumes with the job, pick the better one, and produce
honest, evidence-backed talking points.

### What was done
1. **`job_agent/resume.py` → `load_resumes()`** — reads every PDF in `data/`
   with pypdf → `{name: text}`. Your two resumes (AI Engineer, Software
   Engineer) extract cleanly (~5,000 chars each, 1 page). Image-only PDFs are
   skipped with a warning.
2. **Models:** `SkillMatch` (requirement + exact resume quote),
   `FitAnalysis` (matching skills, missing skills, talking points, score,
   verdict), `ResumeMatch` (resume name + verified analysis + rejected claims).
3. **`job_agent/fit.py`:**
   - `analyze_fit(job, resume_text)` — one focused LLM call **per resume**.
     The job is sent as clean JSON from Phase 1, not the raw web page.
   - `is_evidence_in_resume()` — code check: ≥ 80 % of the quote's words must
     appear in the resume.
   - `verify_analysis()` — splits claims into verified / rejected.
   - `pick_best_resume()` — code picks the highest score; tie → more verified
     matches wins.
4. **`phase2_fit.py`** — prints scores, verified matches with their quotes,
   rejected claims, gaps and talking points.

### Problems hit (the most important part of this phase)
First version output had:
| Problem | Example |
|---|---|
| **Hallucination** | "GraphQL in the my-rag project" — GraphQL is in **neither** resume (checked with code) |
| **Copied from the job, not the resume** | "collaborated with Product Management, UX…" |
| **Contradiction** | "LangGraph: **No**" listed under *matching* skills |
| **Tie** | both resumes 85/100 → `max()` just took the first |

Fixes:
- Evidence must be a **quote** from the resume, checked by code.
- Prompt: "the job posting is never evidence", "if unsure, treat it as missing",
  clear `=== RESUME ===` markers so the model doesn't mix the documents.
- Field description: "never list a missing skill here".
- Tie-break in code.

Result after fixes: AI Engineer **85**, Software Engineer **80**; 6 verified
matches each, fake GraphQL/PM-UX claims gone.

### Remaining limitation
The check proves a quote **exists**, not that it **supports** the claim
(e.g. the RAG project quote was used as evidence for "LangGraph"; the
installer quote for "communication"). That needs judgment → planned
**LLM-as-judge** step or `qwen3:14b` in Phase 7.

### Concepts learned
- **Field order steers reasoning:** evidence fields come before `fit_score`,
  so the model writes evidence first and scores based on it.
- **LLM judges, code decides:** separate focused calls + `max()` in Python.
- **Don't trust, verify:** whenever an LLM claim can be checked by code, check it.
- **Small models mix up long, similar documents** → one document per call.

### Try it
```powershell
python phase2_fit.py https://job-boards.greenhouse.io/gitlab/jobs/8704363002
```

---

## Phase 3 — Company research agent ✅

### Goal
The first **real agent**: the LLM decides which searches to run and when it
knows enough. Built as a **LangGraph** graph.

### What was done
1. **Installed `ddgs`** (DuckDuckGo search, free, no API key).
2. **Tools** in `job_agent/research.py`, made with `@tool`:
   - `web_search(query)` — general facts (products, size, culture)
   - `news_search(query)` — recent events with dates
   - The function name + type hints + docstring are sent to the LLM as the
     tool description, so the docstring tells the model *when* to use it.
   - **Tavily** alternative left in comments (better results, needs a key).
3. **The graph** (`build_research_graph()`):
   ```
   START → agent ⇄ tools
             └──► END (when no tool call)
   ```
   - State: `MessagesState` (a growing message list)
   - `agent` node: `llm.bind_tools(TOOLS).invoke(...)` → either a tool call or text
   - `tools` node: prebuilt `ToolNode` runs the tool, returns a `ToolMessage`
   - `tools_condition`: tool call → `tools`, otherwise → `END`
   - `tools → agent` edge: results always go back to the LLM
4. **Hard limit in code:** after `MAX_TOOL_CALLS = 5` results, tools are no
   longer bound → the model *cannot* call more → the loop is guaranteed to end.
5. **Visible steps:** `graph.stream(stream_mode="updates")` prints each
   decision (`[agent] decides to call web_search({...})`, `[tools] ... returned 5 results`).
6. **Structured result:** after the loop, one more call turns all search
   results + agent notes into a `CompanyBrief` (what they do, products,
   size/stage, recent news, culture, cover-note hooks, sources).
7. **Verification in code:**
   - Source URLs must appear in the real search results → invented ones dropped.
   - Dates in news items must appear in the search results → invented dates
     replaced with "date unknown".
8. **`phase3_research.py`** — also prints the graph as a Mermaid diagram
   (paste into https://mermaid.live to see it).

### Problems hit
| Problem | Cause | Fix |
|---|---|---|
| News dated **2025-10-27** and **2024-10-27** | Model invented dates = today minus 1 and 2 years | Date verification in code + prompt "never guess a date" |
| Hooks were marketing slogans | Vague field description | Description now asks for concrete facts connected to the role; role passed to the summarizer |
| **Agent crashed** with `DDGSException: No results found` | A tool raised an exception | Tools now catch errors and **return them as text**, so the LLM can try another query |

### Result (GitLab, ~48 s)
Agent chose 2 searches by itself (overview + 2026 news) and ran them in
parallel, then decided it had enough. Brief included Q2 FY2027 revenue
(+21.3 %, $286M), a recent analyst target raise, the Oct 21 2026 outage,
remote/transparency culture, 5 verified sources, no invented dates.

### Remaining limitations
- Facts *without* a URL or date (e.g. "1,500 employees") aren't verified.
- Hooks still include items unsuitable for a cover note (stock target,
  outage) — Phase 5 will select which to use.
- Runs are **non-deterministic**: one run made 3 searches, another 2.
  That's normal for agents — the path depends on the model's choices.

### Concepts learned
- **Workflow vs agent:** our pipeline is a fixed workflow; only research is
  an agent, because its path can't be known in advance.
- **Tool calling:** the LLM never runs code. It *asks* for a tool; our code
  runs it and sends back a `ToolMessage`.
- **ReAct loop** = Reason → Act (tool) → Observe (result) → repeat.
- **LangGraph basics:** `StateGraph`, nodes, edges, conditional edges,
  `ToolNode`, `tools_condition`, `compile()`, `stream()`.
- **Guardrails in code:** the tool-call limit is enforced by not binding
  tools, not by asking nicely in the prompt.
- **Tools must fail gracefully:** errors become information for the model.

### Try it
```powershell
python phase3_research.py "GitLab" "Backend Engineer (Python), AI Engineering"
python phase3_research.py "Anthropic"
```

---

## Phase 4 — Job tracker (SQLite) ✅

### Goal
Give the agent **persistent memory**: everything learned about a job is saved
to disk and survives after the program exits.

### What was done
1. **`job_agent/tracker.py`** — pure code, **no LLM**. SQLite is built into
   Python (`import sqlite3`), the whole database is one file: `data/jobs.db`
   (git-ignored, stays on your PC).
2. **Schema** (`CREATE TABLE IF NOT EXISTS`, so it's safe to run every time):
   - `jobs` — normal columns for filtering/sorting (`title`, `company`,
     `fit_score`, `best_resume`, `status`, timestamps…) **plus** JSON columns
     (`job_json`, `fit_json`, `company_json`) holding the complete Pydantic
     objects so no detail is lost.
   - `cover_notes` — linked to `jobs` by `job_id` (foreign key); used in Phase 5.
3. **`_db()` context manager** — opens a connection, commits on success,
   always closes. Turns on `PRAGMA foreign_keys` (SQLite has it off by default)
   and `row_factory = sqlite3.Row` so rows work like dicts.
4. **Functions:**
   - `init_db()` — create tables if missing
   - `save_job(url, job, best, company)` — **upsert** with
     `INSERT … ON CONFLICT(url) DO UPDATE … RETURNING id`
   - `list_jobs()` — best fit first
   - `get_job(id)` — rebuilds `JobPosting` / `ResumeMatch` / `CompanyBrief`
     from JSON with `model_validate_json()`
   - `update_status(id, status)` — only allows the 6 known statuses
5. **Status lifecycle:** `researched → cover_note_ready → applied →
   interviewing → offer / rejected`.
6. **`phase4_tracker.py`** — a small CLI: `add <url>`, `list`, `show <id>`,
   `status <id> <status>`. `add` runs phases 1→3, then saves.
7. **Graceful degradation:** if company research fails, the job is still
   saved (with `company_json = NULL`) — research is nice-to-have, the job
   itself is essential.

### Tests run
| Test | Expected | Result |
|---|---|---|
| `add` GitLab URL | job #1 created | ✅ ~120 s total |
| `list` | 1 row, status `researched` | ✅ |
| `status 1 applied` | status changes | ✅ |
| `status 1 hired` | rejected (unknown status) | ✅ `ValueError` |
| save same URL again | same id, still 1 row | ✅ id 1 returned |
| status after re-save | still `applied` (not reset) | ✅ |
| `show 1` | JSON rebuilt into objects | ✅ |

(Test status was reset to `researched` afterwards — you haven't applied yet!)

### Bonus: Phase 3 error handling proved itself live
During `add`, DuckDuckGo failed on the first `web_search`. The error came
back to Qwen as text, and **Qwen retried the search by itself** — exactly the
behavior the Phase 3 fix was designed for. Before the fix, this would have
crashed the whole run.

### Concepts learned
- **Persistence = agent memory across runs.** (Different from the
  *conversation* memory inside a single run, which is the message list.)
- **Idempotency:** running the same thing twice gives the same result, not
  a duplicate. Crucial for agents, which get re-run often. Implemented with
  `UNIQUE(url)` + upsert.
- **Don't clobber user data:** the upsert updates analysis fields but
  deliberately **not** `status` — re-analysing a job you applied to must not
  reset it to "researched".
- **Parameterized queries (`?`, `:name`)** — never build SQL with f-strings
  from outside data (job titles come from the web!) → prevents SQL injection.
- **Validate at the boundary:** `update_status()` rejects unknown statuses
  so bad values never reach the database.
- **Normal columns + JSON columns:** query what you filter on, keep the rest
  as JSON.

### Notes
- Timestamps use SQLite's `CURRENT_TIMESTAMP`, which is **UTC** (India is
  UTC+5:30).
- To browse the database visually, install
  [DB Browser for SQLite](https://sqlitebrowser.org/) and open `data/jobs.db`.

### Try it
```powershell
python phase4_tracker.py add https://job-boards.greenhouse.io/gitlab/jobs/8704363002
python phase4_tracker.py list
python phase4_tracker.py show 1
python phase4_tracker.py status 1 applied
```

---

## Phase 5 — Cover note + human approval ✅

### Goal
Draft a tailored cover note and make it **impossible** to save without your
explicit approval. You can also ask for changes as many times as you like.

### What was done
1. **`CoverNote` model** — `hooks_used` + `text`. Structured output stops the
   model from wrapping the note in chatter ("Sure! Here's your note:").
2. **`draft_cover_note()`** (LLM) in `job_agent/cover_note.py`. The prompt
   gets: the job, the **verified** skill matches with their resume quotes,
   talking points, company research, and the full resume. Writing rules:
   150–220 words, 3 paragraphs, one genuine company hook (never stock prices,
   outages or lawsuits), achievements only from the resume, no clichés,
   no `[placeholders]`.
3. **`unverified_numbers()`** (code) — every number in the draft must appear
   in the resume / job / research. Unknown numbers are **shown to you as
   warnings** ("flag, don't fix" — you can't safely delete words from prose,
   so the human decides).
4. **`save_cover_note(..., approved)`** (code) — **the guardrail**: raises
   `PermissionError` unless `approved is True`. Then saves to the
   `cover_notes` table, sets the job status to `cover_note_ready`, and writes
   `data/cover_notes/<id>_<company-title>.md`.
5. **`tracker.add_cover_note()`** — plain DB insert; only `save_cover_note`
   calls it.
6. **The graph** with a **checkpointer**:
   ```
   START → draft → review ──approve──► save → END
             ▲       │ (interrupt)
             └─edit──┤
                     └─reject──► END   (nothing saved)
   ```
   - `review_node` calls `interrupt({...draft, warnings, word count...})` →
     the graph **pauses** and returns to the program.
   - The program shows the draft, asks `[a]pprove / [e]dit / [r]eject`.
   - `graph.invoke(Command(resume=answer), config)` → the graph continues;
     `interrupt()` returns your answer.
   - `route_after_review` turns your decision into the next node.
   - `thread_id` in `config` identifies this run so the checkpointer can find
     the paused state.
7. **`phase5_cover_note.py <job-id>`** — loads a tracked job, runs the graph,
   handles the pause/resume loop.

### Tests run
| Test | Result |
|---|---|
| Draft → edit ("shorter + mention LangGraph") → reject | ✅ paused twice, resumed twice, **nothing saved** |
| Number check | ✅ 0 warnings — 8B, 40 s, 12 endpoints, 1.2 s → 9 ms are all in the resume |
| `save_cover_note(approved=False)` called directly | ✅ `PermissionError` |
| DB after reject | ✅ 0 cover notes, status still `researched`, no files |
| **Approve path** | ⏳ **left for you** — approving means *you* read and accept the note, so it shouldn't be done on your behalf |

### Problems hit
| Problem | Cause | Fix |
|---|---|---|
| `Deserializing unregistered type job_agent.models.JobPosting from checkpoint…` | LangGraph security: the checkpointer won't rebuild arbitrary classes from stored data without permission (a tampered checkpoint could abuse that) | `JsonPlusSerializer(allowed_msgpack_modules=[...])` allow-list of our models |
| "Make it shorter" ignored (draft 2 ≈ draft 1) | Feedback buried at the end of a long user message, conflicting with "150–220 words" | Feedback moved into the **system** message and marked as overriding defaults → 166 → 114 words. Word count now shown to you |

### Concepts learned
- **Human-in-the-loop:** the agent proposes, the human disposes. For
  anything outward-facing (emails, applications, payments) this is essential.
- **`interrupt()` + `Command(resume=…)`:** pause a graph mid-run and continue
  it with the human's answer.
- **Checkpointer + `thread_id`:** LangGraph saves state after every node;
  that's what makes pausing possible. (`InMemorySaver` now; a SQLite saver
  would let a paused run survive closing the program.)
- **Gotcha:** on resume, the interrupted node **re-runs from the top**. Never
  put side effects (saving, sending) *before* `interrupt()` in a node.
- **Guardrails in code, not prompts:** the approval check is a Python `if`,
  not an instruction to the model.
- **Prompt placement matters:** for small models, put high-priority,
  rule-overriding instructions in the system message.
- **Serialization safety:** stored state is data, and loading data into
  objects needs an allow-list.

### Try it (your turn — approve one!)
```powershell
python phase5_cover_note.py 1
```
Try `e` with feedback like *"more confident tone"* or *"mention remote
async work"*, then `a` when you're happy. Afterwards:
`python phase4_tracker.py list` shows `cover_note_ready`, and the note is in
`data/cover_notes/`. Check the `cover_notes` table in the SQLite viewer too.

---

## Phase 6 — Full pipeline + CLI ✅

### Goal
One command — `python main.py <url>` — runs every step, in one LangGraph
workflow, and pauses only for your approval.

### What was done
1. **`job_agent/graph.py`** — the main workflow:
   ```
   START → check_tracker ─(already tracked)──────────────────────┐
              │                                                  │
           read_posting → analyze_fit → research_company → save_to_tracker
                                                              │  │
                                                              ▼  ▼
                                          cover_note (SUBGRAPH: draft → review → save)
                                                              │
                                                             END
   ```
   - **`JobHuntState`** inherits all keys of `CoverNoteState` and adds
     `url`, `fresh`, `reused`, `all_matches`.
   - Each node is a **thin wrapper** around an earlier phase: it reads what it
     needs from the state, calls the phase's function, prints a step line,
     returns only the keys it changed.
   - **Subgraph:** the Phase 5 graph is one node:
     `add_node("cover_note", build_cover_note_graph(as_subgraph=True))`.
     It's compiled without its own checkpointer and uses the parent's.
   - **Nested agent:** `research_company` runs the Phase 3 agent graph inside
     a normal node.
   - **Conditional entry:** `check_tracker` looks the URL up (new
     `tracker.find_job_id()`); if found (and no `--fresh`), it loads the saved
     job/fit/research and jumps straight to `cover_note`.
   - **Graceful degradation:** research failure → continue with
     `company_brief = None`.
2. **`main.py`** — the real CLI. Only user interaction lives here:
   run (`<url>`, `<url> --fresh`, `job.txt`), `list`, `show`, `status`,
   `graph`. A new `thread_id` (UUID) per run.
3. `cover_note.build_cover_note_graph()` got an `as_subgraph` flag — the only
   change to earlier code.

### Tests run
| Test | Result |
|---|---|
| `main.py graph` | ✅ Mermaid shows `cover_note` as a nested subgraph |
| New job: GitLab *Knowledge Graph (Rust)* → reject | ✅ 176 s, saved as job #3, fit 70 (AI resume) with the real gap "no Rust"; nothing saved for the note |
| Tracked job #1 again → reject | ✅ **13 s** — analysis skipped, straight to draft |
| DB afterwards | ✅ 2 jobs, both `researched`, 0 cover notes |

### Observations
- **Tailoring works:** for the Knowledge Graph role, the draft chose your
  *tree-sitter code graph* and *Neo4j* work — the most relevant parts of
  your resume for a graph role — instead of repeating the Python-role note.
- **Self-recovery again:** DuckDuckGo failed once more; the agent retried
  with a new query on its own.
- **Job id is #3, not #2:** SQLite's `AUTOINCREMENT` consumed an id during
  the earlier upsert test. Gaps in ids are normal and harmless.
- **`InMemorySaver`:** a paused run lives only while `main.py` is running.
  Fine for a CLI; a web UI would need a persistent (SQLite) checkpointer.

### Concepts learned
- **Workflow with an agent inside:** fixed edges for the steps that never
  change; an agent only where the path is unknown (research).
- **Shared state:** nodes communicate *only* through the state, never by
  calling each other → each node is small and testable on its own.
- **Subgraphs = reuse:** a compiled graph is just a node. State flows in/out
  through shared keys; an `interrupt()` inside pauses the whole parent.
- **Conditional entry / caching:** don't redo expensive LLM work you already
  have — check stored results first.
- **Separation of concerns:** `main.py` talks to the user, `graph.py` wires
  steps, the phase modules do the work, `tracker.py` stores.

### Try it
```powershell
python main.py https://job-boards.greenhouse.io/gitlab/jobs/8704363002   # tracked → fast
python main.py <any new job URL>                                          # full run
python main.py list
python main.py graph        # paste output into https://mermaid.live
```

---

## Phase 7 — Polish ✅

### Goal
Make the assistant **robust** (doesn't crash on real-world problems) and
**trustworthy** (catches more of the model's mistakes), and prove it with
tests and measurements.

### What was done

**1. Reliability (`job_agent/llm.py`)**
- `structured_llm(Schema)` = `with_structured_output(Schema).with_retry(stop_after_attempt=3)`.
  All 5 structured calls (posting, fit, judge, company brief, cover note) use
  it. Malformed JSON from the model gets retried instead of crashing.
- `check_llm_ready()` — `main.py` calls it first: Ollama not running →
  *"Can't reach Ollama… start the Ollama app"*; model not pulled →
  *"Run `ollama pull …`"* with the list of installed models.

**2. Human as the fallback (`graph.py` + `main.py`)**
- If the posting can't be read (403, login wall, JS-only page, missing file),
  `read_posting` calls `interrupt({"kind": "paste_posting", ...})`.
  The graph pauses; `main.py` asks you to paste the description and type
  `END`; the run continues with your text.
- Every interrupt payload now has a **`kind`** (`paste_posting` /
  `approval`), so `main.py` knows which question it's answering.
- Gotcha reminder: on resume the node re-runs from the top, so the fetch is
  tried (and fails) once more before `interrupt()` returns your text.
  Harmless here because fetching has no side effects.

**3. LLM-as-judge (`job_agent/fit.py`)**
- Fixes the Phase 2 limitation: code proves a quote *exists*, but not that it
  *proves the skill*.
- After the code check, **one extra LLM call per resume** gets all claims as
  a numbered list: *"Is this quote real PROOF of this specific requirement?
  Related-but-different is NOT proof."* It returns `SkillJudgment(id,
  supported, reason)` for each one.
- `apply_judgments()` (plain code) moves rejected claims to
  `missing_skills` and records the reason in `ResumeMatch.unsupported_matches`.
  Claims the judge skipped are kept, so only explicit rejections are removed.
  A gap the model already listed isn't added twice.
- Toggle with `JUDGE_EVIDENCE=true/false` in `.env`.
- Why it works: the judge has a **narrower job** (yes/no per claim) than the
  writer (analyze everything), the same reason code reviews catch bugs the
  author missed.

**4. Tests (`tests/`, `python -m pytest`)** — 19 tests, ~2 s, no LLM, temp DB
- Verification: real quote ✓, reworded quote ✓, **the fake GraphQL quote
  from Phase 2** ✗, invented URLs dropped, **the invented "today minus one
  year" date from Phase 3** replaced, invented numbers flagged.
- Judge: rejections move to gaps; skipped claims kept; no duplicate gaps.
- Tracker: save/load roundtrip, upsert idempotency, status preserved on
  re-save, unknown status rejected, `find_job_id`.
- Guardrail: unapproved note → `PermissionError`, no DB change, no file;
  approved → file + status `cover_note_ready`; review routing.
- Small refactors to make code testable: URL/date checks pulled out into
  pure functions `verify_sources()` / `remove_invented_dates()`; `_db()`
  reads `DB_PATH` at call time so tests can point it at a temp file.

**5. `compare_models.py` + README**
- `python compare_models.py <job-id> qwen3:8b qwen3:14b` runs the fit
  analysis (with judge) on a tracked job with each model, side by side.
- `README.md`: setup, usage, configuration, tests, layout.

### Results

**LLM-as-judge on job #1 (qwen3:8b)** — it caught **exactly** the two weak
claims we spotted by hand in Phase 2:
| Claim | Quote used | Judge's reason |
|---|---|---|
| LangGraph experience | the RAG assistant project | "describes a RAG assistant with Streamlit… unrelated to LangGraph" |
| Remote/async communication | the CodeLens Desktop installer | "describes a technical product release… doesn't mention collaboration or communication" |

Both moved to gaps; 4 genuinely proven matches remain.

**qwen3:8b vs qwen3:14b (job #1, fit analysis + judge, both resumes)**
| | qwen3:8b | qwen3:14b |
|---|---|---|
| Time | **76 s** | 291 s (**3.8× slower**) |
| AI Engineer resume | 85/100, 4 proven | 90/100, 4 proven |
| Software Engineer resume | 65/100 | **4/100** ← with 4 proven matches?! |
| Best resume | AI Engineer | AI Engineer |
| Judge caught LangGraph + communication | ✅ | ✅ |
| Fake quotes caught by code | 0 | 1 |

**Verdict: stay on `qwen3:8b` + judge.** The bigger model reached the same
conclusions, took almost 4× longer, and produced a nonsensical score
(4/100) for a resume it rated as matching 4 requirements. Bigger is not
automatically better, and **verification (code + judge) improved quality
more than a bigger model did**. One job isn't enough for a final decision,
so run `compare_models.py` on a couple more before switching.

### Problems hit
| Problem | Fix |
|---|---|
| Judge + model both listed "LangGraph" → duplicate gap | `apply_judgments` skips gaps already listed (even reworded) + test |
| `_db(path=DB_PATH)` default arg bound at import → tests couldn't redirect the DB | read `DB_PATH` at call time |

### Remaining limitations (honest list)
- `fit_score` comes from the first LLM and isn't recalculated after the
  judge. It's also the least stable output (see the 4/100). Idea: compute
  it in code from proven vs missing requirements.
- The judge is an LLM too — more reliable in tests, but not infallible.
- Research facts without a URL/date (e.g. employee counts) aren't verified.

### Concepts learned
- **Graceful degradation:** decide which steps are essential (posting, fit)
  and which are nice-to-have (research), and fail accordingly.
- **The human is the best fallback tool:** `interrupt()` isn't only for
  approval; it works for any "I'm stuck, help me" moment.
- **Retries for flaky outputs:** LLM output is probabilistic; one retry
  often fixes a malformed answer.
- **LLM-as-judge:** use a second, narrowly-scoped LLM call to check work
  that code can't check.
- **Test the deterministic parts:** you can't unit-test what the model says,
  but you can test every safety net around it, including regression tests
  for real bugs you've seen.
- **Measure, don't guess:** model choice is an experiment with numbers.

### Try it
```powershell
python -m pytest -v                                  # see every test by name
python compare_models.py 1 qwen3:8b qwen3:14b        # ~6 min
python main.py https://www.linkedin.com/jobs/view/123  # blocked → paste fallback
```

---

## Phase 8 — Optional extras ✅

You chose all four extras, built in this order: **8a** fit score in code →
**8b** Streamlit web UI → **8c** tracing → **8d** n8n.

### 8a — Fit score computed in code ✅

#### Goal
Stop trusting the LLM's made-up 0–100 number (qwen3:14b gave **4/100** to a
resume with 4 proven matches). Compute the score from the **verified facts**.

#### What was done
1. **Removed `fit_score` from `FitAnalysis`** (what the LLM fills in). The LLM
   now only lists facts: proven matches (with quotes), gaps, talking points,
   verdict. `missing_skills` now asks for nice-to-have gaps too.
2. **`compute_fit_score(analysis, job)`** in `job_agent/fit.py`:
   ```
   score = proven / (proven + required gaps + 0.3 × nice-to-have gaps)
   ```
   A gap counts as nice-to-have if ≥ 50 % of its words appear in one of the
   job's `nice_to_have_skills` (the wording is usually different).
3. **`ResumeMatch.fit_score` + `score_breakdown`** — set by `score_match()`
   **after** the code check and the judge, so the score uses only facts that
   survived every check. The breakdown is printed during a run and in
   `main.py show`, e.g.
   `4 proven / (4 proven + 2 required gaps + 0.3 x 1 nice-to-have gaps) = 63`.
4. **`python main.py rescore`** — recomputes every tracked job's score from
   the stored JSON with **zero LLM calls**. That's possible only because
   Phase 4 kept the full analysis as JSON.
5. Old rows still load: the old LLM `fit_score` inside the stored JSON is
   ignored, and the computed score defaults to 0 until `rescore`.
6. **7 new tests** (`tests/test_fit_score.py`): 100 / 0 / empty edge cases,
   required vs nice-to-have weighting, Job #1's real situation (= 63),
   determinism, loading pre-8a rows. **26 tests total.**

#### Results
| Job | LLM's number | Code score on old facts | Code score after `--fresh` (judge applied) |
|---|---|---|---|
| #1 GitLab Python AI | 85 | 95 | **63** |
| #3 GitLab Rust | 70 | **50** | — |
| #4 ByteDance (yours!) | 95 | **90** | — |

#### Lessons from the results
- **The score can only be as good as its facts.** Job #1 first went *up*
  (85 → 95) because its stored analysis was from before the Phase 7 judge and
  still counted the two weak claims. After `--fresh` ran the judge, the score
  dropped to the honest **63**, exactly what the unit test predicted.
- **Stale free text:** the LLM's *verdict* for job #1 still says "worked in a
  remote, cross-functional environment… only missing Ruby/Vue", because it
  was written **before** the judge removed those claims. A summary generated
  before a check isn't updated by the check. **Next fix:** generate the
  verdict from the final facts (after the judge), or in code.
- **The Rust job dropped 70 → 50.** The new number reflects the 5 real
  required gaps (Rust among them) that the LLM's optimistic 70 glossed over.

#### Concepts learned
- **Don't ask an LLM for what code can compute.** LLMs are good at reading
  and judging text, but unreliable at producing consistent numbers.
- **Separate facts from judgments from numbers:** LLM lists facts → code and
  the judge verify them → code turns them into a score.
- **Explainability:** a score with a visible formula can be argued with and
  improved; an LLM's "85" can't.
- **Store raw results, derive the rest:** keeping the JSON let us re-score
  history instantly when the formula changed.

#### Try it
```powershell
python main.py rescore
python main.py show 1          # see "Score:" with the breakdown
python -m pytest tests/test_fit_score.py -v
```

### 8b — Streamlit web UI ✅

#### Goal
Use the assistant from a browser: paste a URL, watch the agent work, edit
and approve the cover note with buttons, manage the tracker.

#### The design problem
Streamlit **re-runs the whole script on every click**. In `main.py`, the
paused graph simply waits inside a `while` loop; in Streamlit, there is no
loop to wait in, and normal variables are wiped on every click.

**Solution: make the pause durable.**
1. **SQLite checkpointer** (`langgraph-checkpoint-sqlite`): every step,
   including the pause at `interrupt()`, is saved to `data/checkpoints.db`
   (git-ignored, separate from `jobs.db`).
2. **The `thread_id` lives in the page URL** (`?thread=...`).
3. On every rerun, `graph.get_state(config)` tells us where the run is, and we
   draw the matching screen:
   | State | Screen |
   |---|---|
   | no thread in URL | start form |
   | `interrupts` with `kind == "paste_posting"` | paste the job description |
   | `interrupts` with `kind == "approval"` | draft + Approve / Rewrite / Reject |
   | `next == ()` | done (saved or rejected) |
   | `next` not empty, no interrupt | "stopped unexpectedly → Resume" |

   This is the same `interrupt()` / `Command(resume=…)` mechanism as the CLI.
   Only the "waiting" moved from a Python loop to a database.

#### What was done
1. **`app.py`** — two tabs:
   - **Analyze a job:** URL form (+ "re-analyze" checkbox) → live log of the
     agent's steps in an `st.status` box → approval screen with the fit score
     (breakdown on hover), proven matches, gaps, company research, number
     warnings, and an **editable** draft.
   - **Tracker:** table of all jobs, details per job, status dropdown,
     "Draft a cover note for this job" button.
2. **Live progress:** `LogBuffer` temporarily replaces `sys.stdout`, so the
   `print()`s our nodes already make show up in the browser. The graph runs
   with `stream(stream_mode="updates")`, and the log is redrawn after each
   node. Prints can come from worker threads, so the buffer only appends and
   the main thread draws.
3. **Edit before approving:** `review_node` now accepts an optional `text` in
   the resume value. If present, your edited text replaces the draft, so
   **your words** are what gets saved. The guardrail is unchanged.
4. `@st.cache_resource` builds the graph and DB connection once per server
   (`check_same_thread=False` because Streamlit uses several threads).
5. `check_llm_ready()` errors are shown as a red message, not a crash.
6. Switched to Streamlit's current `width="stretch"` (old
   `use_container_width` is being phased out).

#### Tests run (headless, with `streamlit.testing.v1.AppTest`)
| Test | Result |
|---|---|
| Page loads, tabs, start form, no exceptions | ✅ |
| Tracker: 3 jobs, columns, score 90/100 for #4, status loaded | ✅ |
| Start job #1 → paused at approval: title, 63/100, 170-word draft, 3 buttons | ✅ |
| **Reload:** new session with only `?thread=` → **same draft** shown | ✅ |
| Reject → "nothing was saved"; tracker unchanged | ✅ |
| Verified first with a toy graph: parent `get_state().interrupts` includes **subgraph** interrupts | ✅ |

#### Problems hit
| Problem | Fix |
|---|---|
| `pip install` kept timing out (slow PyPI connection) | Stopped the background install (two pips in one venv can corrupt it); you ran it in your own terminal with `--default-timeout=300 --retries 10` ✅ |

#### Concepts learned
- **UIs re-run; agents pause.** A web UI can't "wait" inside a Python loop,
  so the agent's state must be **persisted** and looked up on every request.
  That's the main reason checkpointers exist.
- **`thread_id` = a resumable conversation.** Put it in the URL and any
  page load can continue the same run.
- **`get_state()` drives the UI:** `interrupts`, `next` and `values` tell
  you exactly which screen to show.
- **Human edits beat LLM rewrites** for small changes; offer both.
- **Test UIs headlessly** (`AppTest`) instead of only clicking around.

#### Try it
```cmd
.venv\Scripts\activate.bat
streamlit run app.py
```
Then try: reload the page while the draft is showing (it's still there), edit
a sentence yourself and Approve, or use "Draft a cover note" in the Tracker tab.

### 8c — Tracing with self-hosted Langfuse ✅

#### Goal
See **inside** every run: each node, LLM call, tool call, the exact prompts
and outputs, token counts and timings, without sending your resume to a
cloud service.

#### Concepts (from the temporary tracing guide)
- **Trace** = one run; **span** = one step; **generation** = one LLM call
  (prompt, output, model, tokens); spans nest into a tree.
- **Session** = several traces that belong together. Our run is 2+ graph
  calls (start → pause → resume), grouped by `thread_id`.
- **Score** = a rating attached to a run (we record your decision).
- **Callbacks:** LangChain fires start/end/error events for every runnable.
  A tracing tool is a callback handler; pass it once in the graph config and
  LangChain propagates it to every nested call. No node had to change.
- **LangSmith vs Langfuse:** LangSmith = LangChain's cloud, zero-code setup,
  best LangGraph integration, but data leaves your PC. Langfuse = open
  source, self-hostable (private), framework-agnostic, needs Docker.
  We chose **self-hosted Langfuse**; LangSmith stays one `.env` switch away.

#### What was done
1. **`infra/langfuse/`**
   - `docker-compose.yml`: Langfuse's **official** file, read in full before
     running, kept unmodified.
   - `docker-compose.override.yml`: our changes, merged automatically:
     - your PC already uses **5432** (local PostgreSQL) and **6379**
       (`billing-redis`) → internal services get **no host ports**
       (`!reset []`); they talk over Docker's private network
     - dashboard (3000) and MinIO (9090) bound to **127.0.0.1 only**
       (the default exposed them to your whole Wi-Fi network)
     - `TELEMETRY_ENABLED=false`
   - `.env` (git-ignored): random secrets + `LANGFUSE_INIT_*` →
     your user, org, project and API keys are created automatically.
   - 6 containers: `langfuse-web`, `langfuse-worker`, `postgres`,
     `clickhouse`, `redis`, `minio` (~5.5 GB of images).
2. **`job_agent/tracing.py`** — one switch, `TRACING=off|langfuse|langsmith`:
   - `tracing_config(session_id, interface)` → `callbacks` + `metadata`
     (`langfuse_session_id`, `langfuse_tags`, `langfuse_trace_name`)
   - `record_decision()` → `create_score("cover_note_decision", "approve"|"edit"|"reject")`
   - `flush()` → send buffered events before the CLI exits
   - `check_tracing_ready()` → only **warns**; tracing never blocks a run
3. **Wired into `main.py` and `app.py`**: tracing config merged into the
   graph config, decisions recorded, flush in `finally`.
4. **API discovery instead of guessing:** the SDK turned out to be **v5**
   and the server **v4**. Langfuse v4 removed the old `/api/public/traces`
   read endpoint (now OpenTelemetry-based ingestion), so the trace was read
   back via `/api/public/v2/observations` (with `fields=` groups) and
   `/api/public/v3/scores`, found by searching the installed SDK.

#### Result: one traced run (job #3, `--fresh`, rejected)
| Metric | Value |
|---|---|
| Observations | 54, in 2 traces (run + resume), 1 session |
| Tags / name | `cli`, `qwen3:8b` / `job-hunt-run` |
| LLM calls | 9 |
| Tokens | 15,431 in / 5,260 out |
| Time in LLM calls | 175 of 186 s (**94 %**) |
| Slowest node | `analyze_fit` 85 s (2 analyses + 2 judge calls) |
| Score | `cover_note_decision = reject` ✅ |

**Insight only tracing could give:** an LLM call with 2,571 input / 819
output tokens took **34 s**; one with 3,734 input / 239 output took **11 s**.
On a local model, **output tokens dominate latency** (~25–30 tokens/s). To
speed the agent up, ask for **shorter structured outputs** (e.g. fewer,
shorter talking points); shrinking the prompts matters much less.

#### Problems hit
| Problem | Fix |
|---|---|
| Ports 5432 and 6379 already in use | Internal services get no host ports (`!reset []`) |
| Default compose exposed dashboard + MinIO to the LAN | Bound to 127.0.0.1 |
| Quick test said "client initialized without public_key" | The SDK doesn't read `.env` files; `tracing.py` now calls `load_dotenv()` itself |
| `/api/public/traces` → 404 on Langfuse v4 | Found the v2/v3 endpoints in the installed SDK |

#### Concepts learned
- **Observability for agents:** you can't improve what you can't see.
- **Callbacks / instrumentation:** one handler at the top observes everything.
- **Sessions group multi-step runs** (interrupt → resume).
- **Human decisions are evaluation data**: store them next to the trace.
- **Self-hosting trade-offs:** privacy and no limits vs. setup, disk, RAM.
- **Read before you run:** downloaded compose files are code; we reviewed
  it, kept it unmodified and put our changes in an override.
- **Verify APIs against the installed version:** major versions change
  endpoints and parameters.

#### Try it
1. Open http://localhost:3000 and log in with **karaniraif@gmail.com** and the
   password in `infra\langfuse\.env` (`LANGFUSE_INIT_USER_PASSWORD`).
2. **Tracing → Sessions:** open the latest session and expand the tree:
   `analyze_fit` → the judge's `ChatOllama` call → read its exact prompt.
3. **Scores:** filter runs by `cover_note_decision`.
4. Docker: `cd infra\langfuse` then `docker compose stop` (keep data) /
   `docker compose up -d` (start) / `docker compose down -v` (delete all).

### 8d — n8n + an HTTP API around the agent ↩️ (built, tested, then removed)

> **Status:** everything below was built and tested end to end (commit
> `f41b7f9`), then **removed on purpose** (see "Why it was removed" at the
> end of this section). The notes stay because the lessons apply to any
> future website or integration.

#### Goal
Let an **automation tool** use the agent: n8n shows a form, runs the agent,
shows you the draft for approval, and records your decision. Same agent,
same tracker, same traces; just a different "front door".

#### Concepts (from the temporary n8n guide)
- **n8n** = open-source, self-hostable workflow automation (like Zapier):
  trigger nodes, action nodes, logic nodes, `{{ expressions }}`, 400+ integrations.
- **Keep the brain in code, use n8n for the plumbing.** We didn't rebuild the
  agent in n8n's AI Agent node; our Python agent has verification, a judge,
  guardrails and tests. n8n calls it over HTTP.
- **Long jobs over HTTP:** answer `202 Accepted` + an id immediately, run in
  the background, then report back by **polling** or a **callback/webhook**.
- **Human-in-the-loop exists in both tools, with the same idea:**

  | | LangGraph | n8n |
  |---|---|---|
  | pause | `interrupt()` | Wait node (resume on webhook) |
  | state saved in | checkpointer | n8n's database |
  | continue with | `Command(resume=…)` + `thread_id` | POST to `$execution.resumeUrl` |

#### What was done
1. **`api.py`** (FastAPI + Uvicorn, `python api.py`, docs at `/docs`):
   - `POST /runs` → `202` + `thread_id`; the graph runs in a background
     thread; when it pauses or ends, the API **POSTs the status to
     `callback_url`**.
   - `GET /runs/{id}` → `running` / `awaiting_approval` (draft, warnings,
     score) / `needs_posting_text` / `done` / `error`, built from
     `graph.get_state()`, the same idea as the web UI.
   - `POST /runs/{id}/decision` → the HTTP version of `Command(resume=…)`;
     `409` unless the run is actually awaiting approval.
   - `GET /jobs`, `GET /health`.
   - **Security:** `X-API-Key` header (FastAPI dependency) on everything but
     `/health`; listens on **127.0.0.1** only.
   - Same **SQLite checkpointer** as the web UI, so runs are shared;
     **one run at a time** (lock) since there's one local Ollama; errors
     are reported, never crash the server; traced as `api` in Langfuse.
2. **`infra/n8n/docker-compose.yml`**: n8n 2.45 in Docker, `127.0.0.1:5678`
   only, telemetry off, `AGENT_API_KEY` passed in from the git-ignored
   `infra/n8n/.env` (read in the workflow as `{{ $env.AGENT_API_KEY }}`), so
   **no secret inside the committed workflow JSON**.
3. **`infra/n8n/job-hunt-workflow.json`** (8 nodes):
   ```
   Job URL form → Start agent run (POST /runs, callback_url = $execution.resumeUrl)
     → Wait for the agent (resume on webhook, 20 min limit) → Draft ready? (IF)
         yes → Review the draft (form page: score + draft + Approve/Reject)
                 → Send decision (POST /runs/{id}/decision) → Show result (form ending)
         no  → Show problem (form ending)
   ```
   Imported and published with the n8n CLI:
   `n8n import:workflow --input=/files/job-hunt-workflow.json` and
   `n8n publish:workflow --id=JobHuntAssist001`, then a restart.
4. **Node settings were read from the n8n container's own node definitions**
   (not written from memory): Form v2.5 introduced a new field format, so the
   form nodes are pinned to v2.3 with the classic `formFields.values`.
5. **6 API tests** (`tests/test_api.py`): health without key, 401 without /
   with a wrong key, 404 unknown run, 422 invalid decision, 409 decision when
   not awaiting approval. **32 tests total.**

#### Tests run
| Test | Result |
|---|---|
| API health, 401 without key, data with key | ✅ |
| n8n container → API on the host's 127.0.0.1 via `host.docker.internal` | ✅ |
| Form live at `/form/job-hunt` | ✅ |
| **End to end** (script driving the form like a browser): submit job #1 URL → agent → callback → review page with title, **63/100**, draft, Approve/Reject → Reject → "Nothing was saved" | ✅ in 37 s |
| Draft keeps its paragraphs on the review page | ✅ after fix |
| Approve path | ⏳ yours to try |

#### Problems hit
| Problem | Cause | Fix |
|---|---|---|
| `ENOENT … C:/Program Files/Git/files/job-hunt-workflow.json` | **Git Bash rewrites** `/files/...` into a Windows path before calling Docker | `MSYS_NO_PATHCONV=1` |
| Draft shown as one block of text | n8n **sanitizes custom HTML** and strips `style` attributes (`white-space: pre-wrap` removed) | turn line breaks into `<br>` |
| `.replace(/\n/g, '<br>')` did nothing | the `\n` escape didn't survive JSON → n8n expression | escape-free: `.split(String.fromCharCode(10)).join('<br>')` |

#### Concepts learned
- **Agents as services:** an HTTP API turns the agent into a building block
  any tool can use.
- **Async APIs:** `202` + id + callback for long jobs; never hold a request
  open for minutes.
- **Webhooks / resume URLs:** "call me back here when you're done".
- **Pausing for a human is a universal pattern:** LangGraph, n8n, workflow
  engines all do it the same way: persist state, hand out an id, resume.
- **Secrets stay out of shareable artifacts** (workflow JSON uses `$env`).
- **Containers and localhost:** inside a container, `localhost` is the
  container; use `host.docker.internal` to reach your PC.
- **Platform quirks are real:** Git Bash path rewriting, HTML sanitizing,
  escaping layers. Test the real thing end to end.

#### Why it was removed
- **"Do we even need n8n?"** For a personal tool, no: the web UI already
  does everything the n8n form did, with fewer moving parts. n8n earns its
  place only when you connect the agent to *other apps* (Telegram, Gmail,
  Sheets, schedules).
- **The deployment decision** (next section) picked a **Windows desktop app**,
  which runs the agent directly on the user's PC, so there is no need for
  an HTTP server (`api.py`) either.
- **Removed:** `api.py`, `tests/test_api.py`, `infra/n8n/`, `fastapi` and
  `uvicorn`, the `AGENT_API_KEY` setting, and the project's n8n container
  and data volume. (An older, unrelated n8n container/volume on this PC was
  left untouched.)
- **Recoverable:** `git show f41b7f9` has the full working version.
- **Lesson:** building something and then deliberately removing it is
  normal engineering. **Every extra component is something to run, secure
  and maintain**, so keep only what the real use case needs.

---

### 8e — Monitoring dashboard ✅

#### Goal
Answer "where can I see how my agent is doing?" with our own dashboard,
combining Langfuse traces with the job tracker.

#### Where things live in Langfuse (http://localhost:3000)
| What | Where |
|---|---|
| One run step by step | Tracing → Sessions → open a session |
| Each LLM call | Tracing → Observations (type Generation) |
| Your approve/edit/reject | Scores → `cover_note_decision` |
| Generic charts | Dashboards |
| Evals | Evaluators / Datasets (not set up yet; our "evals" are your decisions + the in-agent checks + the judge) |

#### Tracing vs monitoring
- **Tracing** = one run in full detail (every prompt, every step).
- **Monitoring** = many runs boiled down to a few numbers you watch over
  time: how many runs, how slow, how many tokens, how often searches
  fail, how often you approve.
Langfuse is great at tracing; our dashboard adds **our domain** (fit
scores, job status, cli/web) that Langfuse knows nothing about.

#### What was done
1. **`job_agent/monitoring.py`** (data layer, no UI code):
   - fetches observations via `/api/public/v2/observations` with `fields=`
     groups **without `io`** (prompts contain your resume; skipping them keeps
     refreshes light), following the **cursor** pages; tool calls separately
     *with* outputs (small) to detect failed searches; scores via
     `/api/public/v3/scores` (max page size 100, larger returns 400);
     tracker via `list_jobs()`.
   - pure `build_*` functions → DataFrames: runs, LLM calls, node latency,
     tool stats, decisions, status funnel.
   - **agent time** per run = sum of root spans, so the time a run sat paused
     waiting for you doesn't count as "slow".
2. **`monitor.py`** (Streamlit + Altair, port 8502): filters row (time
   range, started from cli/web) → 5 KPI tiles → time per pipeline step →
   latency vs output tokens / vs input tokens (side by side, same axis) →
   tokens per run → search tool ok/failed → your decisions → fit score per
   job → application status → recent runs with "open ↗" links into Langfuse.
   60 s cache + Refresh button. If Langfuse is down, tracker charts still show.
3. **Chart design** followed the dataviz guidelines: chart form chosen by
   the data's job; one color for single series; blue + orange for two
   series, **validated with the palette script** (colorblind ΔE 24.7 light /
   31.8 dark, all checks PASS); ok/failed in reserved status colors *with*
   text labels; tooltips on every chart; whole-number ticks for counts.
4. **`.streamlit/config.toml`**: accent color blue instead of Streamlit's
   default red (red reads as "error" on a monitoring page). Affects app.py too.
5. **6 tests** (`tests/test_monitoring.py`) with fake Langfuse records. **32 total.**

#### Render-and-look found 4 bugs the tests couldn't
Screenshots were taken with Playwright driving your installed Edge
(headless, separate profile, nothing downloaded):

| Bug seen in the screenshot | Cause | Fix |
|---|---|---|
| Step bars overlapping, half the labels missing | Altair silently **drops axis labels that would overlap** | more height per row, band padding, `labelOverlap=False` |
| "vs input tokens" chart cut off | `alt.hconcat` charts don't shrink to the column | two Streamlit columns, one chart each |
| Small charts squashed (rows on top of each other) | Streamlit fits the **whole** chart (title + axes + legend) into `height`; bars get only what's left | `rows_height()` budgets 36 px/row + chrome + legend |
| Black outlines around stacked bars | `st.context.theme` said "dark" while the page rendered light, so the "surface-colored" separator was black | dropped theme-guessed separators |

Plus: a plain headless-Edge screenshot only captured Streamlit's **loading
skeleton** (Streamlit draws over a websocket), hence Playwright, which waits
for the charts.

#### A mistake from the n8n revert, caught here
Uninstalling `uvicorn` with FastAPI **broke `streamlit run`**: Streamlit
1.66 runs its server on uvicorn. Headless tests don't start a real server,
so nothing noticed until the dashboard was launched. Fixed by reinstalling;
`pip check` now reports no broken requirements.
**Lesson: after uninstalling a package, run `pip check`**, and test the
real thing, not only the headless version.

#### What the first data already says
- Correlation with LLM latency: **output tokens 0.90, input tokens 0.16**,
  the 8c insight confirmed as a number.
- `analyze_fit` is the slowest step (~85 s: two analyses + two judge calls).
- Approval rate 17 % (1 of 6), most decisions so far were test rejects.

#### Concepts learned
- Tracing vs monitoring; KPIs; observability APIs and pagination.
- Separate the data layer (pure, tested) from the UI (thin).
- Don't fetch what you don't need (`io` excluded).
- Measure what the user experiences (agent time, not wall-clock with waits).
- Charts: pick the form first, color last, validate colors, label state.
- **Always look at the rendered result:** layout bugs are invisible to code tests.

#### Try it
```cmd
.venv\Scripts\activate.bat
streamlit run monitor.py --server.port 8502
```
Run a few jobs (`python main.py <url>` or the web UI), press **Refresh now**,
and watch the numbers move.

---

## Phase 9 — Windows desktop app (Qt) 🚧

**Goal:** double-click an icon and use the assistant in a native window,
on a PC without Python. **Your choices:** native Qt (PySide6) rewrite of
the UI; Ollama by default plus an optional Claude API key; the monitoring
dashboard as a tab. The agent (`job_agent/`) doesn't change; only a new
front end is built on top of it. The Streamlit app stays as a dev tool.

**Download-size choice:** full PySide6 is ~230 MB; `PySide6-Essentials`
(~80 MB) has all the widgets we need, and charts use `matplotlib` (~10 MB)
instead of Qt's chart module (which needs the other ~150 MB).

### 9a — App data folder + settings ✅
- **`job_agent/paths.py`**, the one place that decides where files live:
  | | Developer mode (from the repo) | Installed mode (packaged `.exe`) |
  |---|---|---|
  | settings | `<repo>/.env` | `%LOCALAPPDATA%\JobHuntAssistant\.env` |
  | data | `<repo>/data/` | `%LOCALAPPDATA%\JobHuntAssistant\data\` |
  Installed mode is detected by `sys.frozen` (set by PyInstaller);
  `JOB_HUNT_HOME` overrides both (used for tests / a second profile).
  **Why:** an installed app's code folder may not be writable and it can be
  started from anywhere, so "the current folder" means nothing.
  `%LOCALAPPDATA%` is Windows' per-user, writable, not-synced place, right
  for private resumes and databases.
- `resume.py`, `tracker.py`, `cover_note.py`, `app.py` now import their
  paths from `paths.py`; the tracker creates the full folder on first use
  (`parents=True`, a fresh install has nothing yet).
- **`job_agent/settings.py`**: `load_settings()` (defaults → .env → real env
  vars win), `read_settings()`, `save_settings()` (writes .env **and**
  updates `os.environ`, so `get_llm()` picks it up immediately, no restart).
  `llm.py` / `tracing.py` load settings from `paths.ENV_FILE` instead of
  "whatever .env is in the current folder".
- **`llm_status()`** returns `(ok, message)` instead of exiting, so a GUI
  can show it; `check_llm_ready()` wraps it for the CLI. Also checks that an
  Anthropic key exists when Claude is selected.
- 5 tests (`tests/test_paths_settings.py`): dev mode, installed mode
  (fake `sys.frozen`), override, save → applied + written, defaults.
  **37 tests total.** Developer mode verified: still finds your 4 jobs.

### 9b — Qt window + Settings tab ✅
- **`desktop_app.py`**: entry point (`python desktop_app.py`): creates
  `QApplication`, shows the window, runs Qt's **event loop**.
- **`desktop/main_window.py`**: `QMainWindow` with 4 tabs (Analyze,
  Tracker, Dashboard = placeholders for now; Settings); a small stylesheet
  (blue default button, ok/error label colors); status bar shows mode +
  data folder. **First run** (no resumes) opens on Settings.
- **`desktop/settings_tab.py`**: three groups in the order a new user needs
  them: **AI model** (provider dropdown; the API-key field appears only for
  Claude; "Check connection"), **Resumes** (list, Add PDF… copies the file,
  Remove asks first and only deletes the app's copy, Open folder),
  **Options** (evidence double-check, tracing). Save → `save_settings()`.
- **`desktop/threads.py`**: `run_in_background(fn, on_done=...)` using Qt's
  thread pool. The connection check can wait 5 s on the network, so it must
  not run on the GUI thread or the window freezes ("Not responding").
  Results come back via a **signal**, because widgets may only be touched
  from the GUI thread.

**Tested offscreen** (Qt renders into memory, no window on your screen):
first run with an empty temp profile → Settings tab, "no resumes yet",
✔ Ollama check; your setup → both resumes listed. Two test-renderer
quirks (not app bugs): offscreen Qt on Windows needs `QT_QPA_FONTDIR` to
find fonts, and then must be told to use Segoe UI.

**Qt concepts learned:** widgets & layouts (no pixel positions); signals &
slots (`clicked.connect(...)`); the event loop; one GUI thread, slow work in
background threads, results via queued signals; combo boxes with a visible
label + hidden value; password echo mode.

**Try it:** `python desktop_app.py` → Settings tab.

### 9c — Analyze tab ✅
**The problem:** a full analysis takes ~3 minutes. On the GUI thread the
window would freeze ("Not responding") for 3 minutes.
**The solution:** the Qt **worker-object pattern**:
```
GUI thread                                   worker QThread
[Analyze] ── start_requested(url) ─────────► AgentWorker.start()  → graph.invoke()
log panel ◄─ log("[2/5] ...") ─────────────  every print() from the nodes
review    ◄─ paused(payload, summary) ─────  interrupt() → graph pauses
[Approve] ── resume_requested(answer) ─────► AgentWorker.resume() → Command(resume=…)
"Saved ✔" ◄─ finished(result) ─────────────  run complete
```
- `worker.moveToThread(thread)`: the worker's slots now run on that thread.
  Signals across threads are **queued**, so the GUI never runs the graph and
  the worker never touches a widget.
- **`desktop/agent_worker.py`**: builds the graph with the **SQLite
  checkpointer** (same `checkpoints.db` as the web UI); temporarily swaps
  `sys.stdout` for a writer that turns each `print()` into a `log` signal;
  after each run reads `get_state()` → `paused` (with a plain-data summary:
  title, fit score, breakdown, matches, gaps) or `finished`. Separate slots
  for decisions (`resume`) and pasted job text (`resume_with_text`, because the
  paste interrupt expects the text itself). Traces are tagged `desktop`.
- **`desktop/analyze_tab.py`**: URL + "re-analyze" + Analyze; progress bar
  driven by the `[n/5]` log lines; agent log; review panel (title, **Fit
  x/100**, breakdown, proven matches with quotes, gaps, number warnings,
  **editable draft** + word count, Approve & save / Reject / feedback +
  Rewrite). Unreadable page → **paste dialog**.
- **Closing during a run** asks first, then exits immediately (a thread
  stuck in an LLM call can't be stopped politely; the checkpointer has
  already saved every finished step).
- The monitoring dashboard's "Started from" filter now includes `desktop`.

**Tests:**
| Test | Result |
|---|---|
| Driven like a user (offscreen script): unreadable source → paste step | ✅ |
| Job #1 → window stays responsive while running | ✅ |
| Review panel after 51 s: title, Fit 63/100, 153-word draft | ✅ screenshot checked |
| Reject → "nothing was saved", job #1 still `researched` | ✅ |
| 5 GUI unit tests (`tests/test_desktop.py`): fake worker signals → progress, review panel, approve sends *your edited* text, finished messages, rewrite needs feedback | ✅ **42 tests total** |

**Qt concepts learned:** `QThread` + worker objects; queued cross-thread
signals; never touch widgets off the GUI thread; testing GUIs by calling
slots with fake signals.

### 9d — Tracker tab ✅
**Qt's model/view architecture:**
```
SQLite ─► JobsModel ─► QSortFilterProxyModel ─► QTableView
          (the data)   (search + click-to-sort)  (what you see)
```
The view never holds data; it asks the model ("how many rows? what's in
row 3, column 2?"). The proxy re-orders and hides rows **without changing
the model**. `model.load()` → `beginResetModel/endResetModel` → every view
updates.

- **`desktop/tracker_tab.py`**:
  - `JobsModel(QAbstractTableModel)` answers `rowCount`, `columnCount`,
    `headerData`, `data(role)`. Two roles per cell: `DisplayRole` = text to
    show, `UserRole` = **raw value for sorting** (so fit 80 sorts above 9;
    as text, "9" > "80").
  - Proxy: search box filters all columns (case-insensitive); clicking a
    header sorts; best fit first by default.
  - **Proxy rows ≠ model rows:** the view's row number belongs to the
    proxy; `proxy.mapToSource()` translates it back.
  - Details panel (HTML): location, fit + breakdown, verdict, proven matches
    with quotes, gaps, company summary, the latest **approved cover note**.
    Every value is `html.escape`d: job text comes from the web and must be
    shown, never executed.
  - Actions: status dropdown (saved on change; `activated` fires only for
    user changes, not when code sets it), Open posting, **Copy cover note**
    (clipboard), **Draft a cover note** → switches to Analyze and starts.
- **`tracker.get_cover_notes(job_id)`**, newest first.
- **Tabs talk through signals:** Analyze `jobs_changed` → Tracker
  `refresh`; Tracker `draft_requested(url)` → main window → Analyze.
  No tab reaches into another.
- **8 tests** (`tests/test_desktop_tracker.py`, temp DB): numeric sort,
  search, escaped details (`<script>` title shown as text), status saved,
  approved note shown + copied to clipboard, draft button sends the URL,
  notes newest first, sort role returns numbers. **50 tests total.**
- Screenshot with your real tracker checked: 4 jobs sorted 90 / 84 / 63 / 42,
  ByteDance details with breakdown and evidence.

**Qt concepts learned:** model/view; item roles; proxy models for sorting
and filtering; mapping proxy ↔ source rows; escaping untrusted text in
rich-text widgets; tabs decoupled through signals.

### 9e — Dashboard tab ✅
- **Reused the 8e data layer** (`job_agent/monitoring.py`) unchanged: the
  payoff of keeping it free of UI code. The desktop tab only draws.
- **One KPI calculation for both dashboards:** the headline numbers moved
  from `monitor.py` into `monitoring.build_kpis()`; the Streamlit page and
  the desktop tab both call it (one tested version instead of two copies
  that could drift apart).
- **`desktop/dashboard_tab.py`**:
  - 5 KPI tiles (runs, LLM calls, tokens, median full run, approval rate)
    + Refresh.
  - 4 charts in a 2×2 grid, **matplotlib embedded in Qt**
    (`FigureCanvasQTAgg`): fit score per job (top 10), where your
    applications are, seconds per pipeline step, LLM call time vs output
    tokens (correlation in the title).
  - **Two speeds of data:** tracker charts from local SQLite draw instantly;
    Langfuse data loads on a **background thread** (network). If Langfuse
    is off, those panels say "Needs Langfuse" with how to start it; the
    tracker charts still work.
  - Chart colors read the **Qt palette**, so charts follow the app's light /
    dark theme; same styling rules as 8e (one blue series, values at bar
    ends, light gridlines, whole-number ticks for counts).
  - Loads **lazily**: only when the tab is first opened, not at app start.
  - Analyze → `jobs_changed` → dashboard redraws the tracker charts.
- Bug caught while writing: the status chart was built from the top-10
  list used for the fit chart (would under-count with more than 10 jobs);
  now each chart gets the data it needs.
- Removed the placeholder helper: all four tabs are real.
- **4 tests** (`tests/test_desktop_dashboard.py`): KPIs (re-drafts excluded
  from the median, approval rate), KPIs with no data, tab without Langfuse
  (tracker charts + message), tab with trace data (tiles filled).
  **54 tests total.** Screenshot with real data matches the web dashboard
  (6 runs, 13 calls, 34,939 tokens, 186 s, 17 %, correlation 0.90).

**Concepts learned:** reusing a data layer across UIs; one source of truth
for metrics; embedding matplotlib in Qt; lazy loading; degrading
gracefully when an optional service is down.

---

## Deployment decision

Asked: *"If I turned this into a website or a Windows app, what would I pay?"*

**Usage per full run** (measured with Langfuse in 8c): ~15,000 input +
~5,000 output tokens. With a cloud LLM (prices checked October 2026; Claude
counts tokens a bit differently and its thinking adds output, so ~1.5× buffer):

| Model | $ per 1M tokens (in / out) | One run | 2,000 runs/month (100 users × 20) |
|---|---|---|---|
| Claude Haiku 5.5 | 0.10 / 0.50 | ~$0.004–0.006 | ~$8–12 |
| Claude Sonnet 5.5 | 2 / 10 | ~$0.08–0.12 | ~$160–240 |
| Claude Opus 5.5 | 4 / 20 | ~$0.16–0.24 | ~$320–480 |

| | **Website** | **Windows app** | **Open-source repo (now)** |
|---|---|---|---|
| LLM | the table above (or a GPU server ~$150–700+/month to self-host Qwen) | **$0 to you**: user's own Ollama or API key | $0 |
| Hosting | free tier (Streamlit Cloud / HF Spaces) or ~$5–12/month server | none (GitHub Releases) | none |
| Extras | domain ~$10–15/yr; paid search API at scale | code signing ~$100–400/yr (optional, avoids SmartScreen warning) | — |
| Hidden work | logins, per-user data separation, **privacy law for stored resumes** (India DPDP Act / GDPR), spending limits, abuse protection | installer, first-run setup, users need ~16 GB RAM for a local model | none |

*(Hosting and certificate prices are rough ranges; check current provider pricing.)*

**Decision:** keep it a **personal, open-source project** for now ($0), with
a **Windows desktop app** as the next step: no server costs, no LLM bill,
and nobody's resume stored on a server. See plan.md, Phase 9.

---

## Where to go next

- **Phase 9 — Windows desktop app** (plan.md): package with PyInstaller,
  first-run setup that checks Ollama, data in the user's AppData folder.
- **Write the verdict from the final facts** (after the judge), the last
  open item from 8a.
- **Evaluation:** build a small dataset of jobs with the "right" answers
  and use Langfuse datasets to measure prompt changes.
- **Shorter outputs for speed:** tracing showed output tokens dominate
  latency, so trim talking points and descriptions and measure the gain.
