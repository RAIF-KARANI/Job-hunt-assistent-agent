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
| 8 — Optional extras | 🚧 In progress | 8a ✅ score in code · 8b web UI · 8c tracing · 8d n8n |

**Progress: all 8 core phases (0–7) complete. 🎉 Phase 8 (extras) in progress.**

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

## Phase 8 — Optional extras 🚧

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
