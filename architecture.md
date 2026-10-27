# Architecture — Job Hunt Assistant

This document explains **how the system is built and why**. For *what* we're
building see [idea.md](idea.md); for *the order we build it in* see
[plan.md](plan.md); for *what's done so far* see [progress.md](progress.md).

---

## 1. The big picture

You paste a job URL. The system runs six steps, pauses for your approval, and
saves the results.

```
                         ┌──────────────────────────────┐
  You ── job URL ──────► │        Interface (CLI)        │ ◄── approve / edit / reject
                         └──────────────┬───────────────┘
                                        │
                         ┌──────────────▼───────────────┐
                         │   Main workflow (LangGraph)   │   fixed order of steps,
                         │   + checkpointer (pause/resume)│   shared state
                         └──────────────┬───────────────┘
        ┌──────────────┬───────────────┼───────────────┬──────────────┐
        ▼              ▼               ▼               ▼              ▼
  ┌───────────┐ ┌────────────┐ ┌──────────────┐ ┌────────────┐ ┌────────────┐
  │ read      │ │ analyze    │ │ research     │ │ save to    │ │ draft +    │
  │ posting   │ │ fit        │ │ company      │ │ tracker    │ │ approve    │
  │           │ │            │ │ (AGENT loop) │ │            │ │ cover note │
  └─────┬─────┘ └─────┬──────┘ └──────┬───────┘ └─────┬──────┘ └─────┬──────┘
        │             │               │               │              │
        ▼             ▼               ▼               ▼              ▼
   requests +     resume PDFs     DuckDuckGo       SQLite        LLM + human
   BeautifulSoup  (pypdf)         web/news         jobs.db       interrupt()
        │             │               │                              │
        └─────────────┴───────┬───────┴──────────────────────────────┘
                              ▼
                    ┌───────────────────┐
                    │  LLM layer        │  get_llm() → Ollama qwen3 (local)
                    │  job_agent/llm.py │  swappable: Claude / OpenAI / Gemini
                    └───────────────────┘
```

---

## 2. Workflow vs. agent — the most important design decision

There are two ways to use an LLM in a multi-step system:

| | **Workflow** | **Agent** |
|---|---|---|
| Who decides the next step? | Our code (fixed path) | The LLM (dynamic) |
| Predictable? | Yes | Less |
| Good for | Steps that always happen in the same order | Open-ended tasks where the path depends on what you find |
| Example here | read → fit → research → save → draft → approve | "Search for X… not enough, search news for Y… done" |

**Our system is a workflow with one agent inside it.**
- The **main pipeline** is a workflow: every job always goes through the same
  six steps, so there's no reason to let the LLM choose the order.
- **Company research** is an agent: we can't know in advance what to search
  for or how many searches are needed, so the LLM decides.

Rule of thumb: *use the simplest thing that works*. Make something an agent
only when the path really can't be known in advance.

---

## 3. Layers

### 3.1 LLM layer — `job_agent/llm.py`  ✅
- One function, `get_llm()`, is the **only** place that knows which model is used.
- Reads `LLM_PROVIDER`, `LLM_MODEL`, `LLM_TEMPERATURE`, `OLLAMA_*` from `.env`.
- Returns a LangChain chat model. All providers share the same interface:
  - `.invoke(messages)` → plain reply
  - `.with_structured_output(Model)` → reply parsed into a Pydantic object
  - `.bind_tools([tools])` → reply may be a tool call
- **Current:** Ollama `qwen3:8b`, local, `num_ctx=16384`, reasoning off.
- **To switch:** edit `.env` only (plus install that provider's package).

### 3.2 Data models — `job_agent/models.py`  ✅
Pydantic classes that define the **shape of data** passing between steps.
Field `description`s are sent to the LLM as instructions.

| Model | Produced by | Contents |
|---|---|---|
| `JobPosting` | LLM (Phase 1) | title, company, location, type, seniority, salary, summary, skills, responsibilities |
| `SkillMatch` | LLM (Phase 2) | requirement + exact quote from the resume as evidence |
| `FitAnalysis` | LLM (Phase 2) | matching skills, missing skills, talking points, score 0–100, verdict |
| `ResumeMatch` | Code (Phase 2) | which resume + its verified FitAnalysis + rejected claims |
| `CompanyBrief` | LLM (Phase 3) | what they do, products, size, news, culture, cover-note hooks, sources |
| `CoverNote` | LLM (Phase 5) | *planned* |

### 3.3 Step modules (the "nodes")

| Module | Step | Uses LLM for | Uses code for | Status |
|---|---|---|---|---|
| `posting.py` | Read posting | extracting fields | download + clean HTML | ✅ |
| `resume.py` | Load resumes | — | PDF → text | ✅ |
| `fit.py` | Analyze fit | judging each resume | verifying evidence, picking the winner | ✅ |
| `research.py` | Research company | deciding searches, summarizing | running searches, verifying URLs | ✅ |
| `tracker.py` | Save job | — | SQLite insert/update | ⏳ Phase 4 |
| `cover_note.py` | Draft + approve | writing the note | approval gate, saving | ⏳ Phase 5 |
| `graph.py` | Main workflow | — | wiring all steps together | ⏳ Phase 6 |

### 3.4 Interface — `main.py`  ⏳ Phase 6
A command-line program: `python main.py <url>`. Prints each step as it runs,
shows the draft, and asks `[a]pprove / [e]dit / [r]eject`.
Until then, each phase has its own test script (`phase1_*.py`, …).

---

## 4. The research agent in detail (Phase 3)

The classic **ReAct loop** (Reason + Act) as a LangGraph graph:

```
        START
          │
          ▼
      ┌───────┐   last message has tool calls   ┌───────┐
      │ agent │ ──────────────────────────────► │ tools │
      │ (LLM) │ ◄────────────────────────────── │       │
      └───────┘        tool results             └───────┘
          │
          │ no tool calls ("I'm done")
          ▼
         END  ──►  summarize into CompanyBrief  ──►  verify source URLs
```

- **State:** `MessagesState` — a list of messages that grows each turn
  (Human → AI tool call → ToolMessage → AI tool call → … → AI final notes).
- **agent node:** calls the LLM with tools bound. The LLM replies either with
  a tool call (`web_search("GitLab layoffs 2026")`) or with plain text (done).
- **tools node:** LangGraph's prebuilt `ToolNode` runs the requested tool and
  adds the result as a `ToolMessage`.
- **Conditional edge:** `tools_condition` routes to `tools` if the last message
  has tool calls, otherwise to `END`.
- **Tools:** `web_search` and `news_search` (DuckDuckGo, no API key).
  Tavily is a commented-out alternative in the code.
- **Safety limit:** after `MAX_TOOL_CALLS = 5`, tools are no longer bound, so
  the model *can't* call more — guaranteed to stop.
- **Verification:** source URLs and news dates in the brief must appear in
  the actual search results; invented URLs are dropped, invented dates are
  replaced with "date unknown".
- **Tool errors:** tools catch exceptions and return the error as text, so a
  failed search becomes information the LLM can react to, not a crash.

---

## 5. The main workflow (Phase 6, planned)

### 5.1 Shared state
Every node reads from and writes to one state object:

```python
class JobHuntState(TypedDict):
    url: str
    posting_text: str
    job: JobPosting
    best_match: ResumeMatch
    all_matches: list[ResumeMatch]
    company: CompanyBrief
    job_id: int                 # row id in SQLite
    cover_note_draft: str
    approval: Literal["approved", "edit", "rejected"]
    feedback: str               # your edit instructions
```

### 5.2 Graph

```
START → read_posting → analyze_fit → research_company → save_to_tracker
                                                              │
                                                       draft_cover_note ◄──┐
                                                              │            │
                                                     human_approval        │
                                                      (interrupt)          │
                                     approved │      edit │     rejected │ │
                                              ▼           └─────────────┼─┘
                                     save_cover_note                    ▼
                                              │                        END
                                              ▼
                                             END
```

### 5.3 Human-in-the-loop
- The `human_approval` node calls LangGraph's `interrupt(draft)`.
- The graph **stops**, and a **checkpointer** saves the whole state.
- The CLI shows you the draft and collects your answer.
- The CLI resumes the graph with `Command(resume=answer)`; it continues
  exactly where it stopped.
- **Guardrail in code:** `save_cover_note` refuses to save unless
  `approval == "approved"`. The rule doesn't depend on the LLM behaving.

---

## 6. Storage

```
data/                      (git-ignored — personal data never leaves your PC)
├── *.pdf                  your resumes (every PDF is a candidate)
├── jobs.db                SQLite tracker              ⏳ Phase 4
└── cover_notes/           approved notes as .md files ⏳ Phase 5
```

### Planned SQLite schema (Phase 4)

```sql
CREATE TABLE jobs (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    url           TEXT UNIQUE NOT NULL,   -- same URL twice = update, not duplicate
    title         TEXT NOT NULL,
    company       TEXT NOT NULL,
    location      TEXT,
    seniority     TEXT,
    salary        TEXT,
    fit_score     INTEGER,
    best_resume   TEXT,
    status        TEXT NOT NULL DEFAULT 'researched',
                  -- researched → cover_note_ready → applied → interviewing → offer / rejected
    job_json      TEXT,   -- full JobPosting
    fit_json      TEXT,   -- full ResumeMatch
    company_json  TEXT,   -- full CompanyBrief
    created_at    TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at    TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE cover_notes (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id     INTEGER NOT NULL REFERENCES jobs(id),
    text       TEXT NOT NULL,
    approved_at TEXT DEFAULT CURRENT_TIMESTAMP
);
```

Why store JSON columns as well as normal columns? Normal columns are for
filtering/sorting (`WHERE fit_score > 70`); JSON keeps every detail without
needing a column per field.

---

## 7. Design principles (the lessons, collected)

1. **Code for facts, LLM for understanding.** Downloading, parsing, saving,
   comparing numbers → code. Reading messy text, judging fit, writing → LLM.
2. **Structured output everywhere.** The LLM fills Pydantic forms; the rest of
   the code works with typed objects, never with free text.
3. **Don't trust, verify.** LLM claims are checked by code where possible
   (resume quotes, source URLs). Unverified claims are dropped and shown.
4. **LLM judges, code decides.** The LLM scores each option separately; plain
   Python picks the winner. Transparent and reproducible.
5. **Guardrails live in code, not prompts.** Tool-call limits, the approval
   gate — enforced by code so a misbehaving model can't bypass them.
6. **Make the agent observable.** Every step prints what it's doing.
7. **Provider-agnostic.** Swap models in `.env`; no code changes.
8. **Local-first and private.** Resumes and the tracker stay on your machine;
   with Ollama, even the LLM runs locally. Only search queries go online.

---

## 8. Folder structure

```
Job-hunt-assistent-agent/
├── idea.md, architecture.md, plan.md, progress.md   ← docs
├── requirements.txt          packages
├── .env.example → .env       settings (.env is git-ignored)
├── hello_llm.py              Phase 0 test
├── phase1_read_posting.py    Phase 1 test
├── phase2_fit.py             Phase 2 test
├── phase3_research.py        Phase 3 test
├── main.py                   ⏳ final CLI (Phase 6)
├── job_agent/
│   ├── llm.py                LLM factory
│   ├── models.py             Pydantic data models
│   ├── posting.py            read job posting
│   ├── resume.py             load resume PDFs
│   ├── fit.py                fit analysis + verification
│   ├── research.py           company research agent (LangGraph)
│   ├── tracker.py            ⏳ SQLite tracker
│   ├── cover_note.py         ⏳ draft + approval
│   └── graph.py              ⏳ main workflow
└── data/                     git-ignored personal data
```

---

## 9. Tech stack

| Concern | Choice | Why |
|---|---|---|
| Language | Python 3.13 | Best agent ecosystem |
| LLM framework | LangChain (`langchain-core`) | Tools, structured output, provider-agnostic models |
| Orchestration | LangGraph | Graphs, loops, checkpointing, `interrupt()` for approval |
| LLM | Ollama `qwen3:8b` (local) | Free, private, supports tool calling |
| Validation | Pydantic v2 | Typed, validated LLM output |
| Web fetching | requests + BeautifulSoup | Simple, transparent |
| PDF | pypdf | Pure Python, no system deps |
| Search | DuckDuckGo (`ddgs`) | Free, no API key (Tavily as alternative) |
| Storage | SQLite (built into Python) | Real database, single file, no server |
| Config | python-dotenv | Settings and keys out of code |

## 10. Known limitations

- **JavaScript-only / login-walled job pages** (e.g. LinkedIn) can't be
  fetched → paste the text into a `.txt` file instead.
- **Small local model accuracy:** evidence verification proves a quote
  *exists*, not that it *supports* the claim. Planned mitigation (Phase 7):
  LLM-as-judge review step and/or `qwen3:14b`.
- **DuckDuckGo** may rate-limit heavy use and returns only short snippets.
- **Speed:** each LLM call on qwen3:8b takes ~20–30 s on CPU/consumer GPU.
