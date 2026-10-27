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
| 4 — Job tracker (SQLite) | ⏳ Next | |
| 5 — Cover note + approval | ⏳ | |
| 6 — Full pipeline + CLI | ⏳ | |
| 7 — Polish | ⏳ | |

**Progress: 4 of 8 core phases complete (~50%).**

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

## Phase 4 — Job tracker (SQLite) ⏳ Next
See [plan.md](plan.md#phase-4--job-tracker-sqlite-).
