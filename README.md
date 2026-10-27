# Job Hunt Assistant 🧭

An AI agent that helps with job applications. Paste a job posting link and it:

1. **reads the posting** and extracts the key facts,
2. **compares it with your resumes** and picks the best one, with verified evidence,
3. **researches the company** on the web (an agent that chooses its own searches),
4. **saves the job** to a local SQLite tracker,
5. **drafts a tailored cover note**, and
6. **waits for your approval** before saving anything.

It runs **fully locally** by default (Ollama + Qwen3), so your resumes and
tracker never leave your machine. Only search queries go online.

Built with **LangChain + LangGraph** as a learning project. Every file is
heavily commented, and the docs explain each step:

| Doc | What's in it |
|---|---|
| [idea.md](idea.md) | What and why |
| [architecture.md](architecture.md) | How it's built: graphs, state, design principles |
| [plan.md](plan.md) | The phase-by-phase build plan |
| [progress.md](progress.md) | Learning journal: what was done in each phase, problems hit, lessons |

---

## Setup (Windows)

**Requirements:** Python 3.11+, [Ollama](https://ollama.com) running locally.

```powershell
# 1. Get a model that supports tool calling
ollama pull qwen3:8b

# 2. Create the virtual environment and install packages
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# 3. Settings
copy .env.example .env          # then edit if you want another model

# 4. Your resumes: put one or more PDFs in data\
mkdir data
#    e.g. data\My_Name_AI_Engineer.pdf, data\My_Name_Software_Engineer.pdf
```

`data/` and `.env` are git-ignored, so your personal files and keys are never committed.

> **Every new terminal:** activate the venv first, or you'll get
> `No module named 'langgraph'` (the system Python doesn't have the packages).
> cmd: `.venv\Scripts\activate.bat` · PowerShell: `.venv\Scripts\Activate.ps1`.
> Your prompt then starts with `(.venv)`. Alternatively, run
> `.venv\Scripts\python main.py ...` directly.

## Usage

```powershell
python main.py <job-url>              # full run (~3 min), ends with the approval step
python main.py <job-url> --fresh      # re-analyze a job that's already tracked
python main.py path\to\job.txt        # use pasted job text
python main.py list                   # tracked jobs, best fit first
python main.py show 3                 # details of one job (fit, gaps, company)
python main.py status 3 applied       # researched → cover_note_ready → applied → interviewing → offer / rejected
python main.py graph                  # workflow diagram (paste into https://mermaid.live)
python main.py rescore                # recompute all fit scores in code (no LLM)
```

### Web UI

```powershell
streamlit run app.py          # opens http://localhost:8501
```

Paste a URL, watch the agent's steps live, then edit the draft yourself
and **Approve**, ask for a rewrite, or **Reject**. The **Tracker** tab shows
all jobs, their score breakdown and status. A paused run is saved to
`data/checkpoints.db`, so you can reload the page or come back later with
the same URL.

### Tracing (optional)

See every LLM call, prompt, token count and timing in a dashboard. The
default is **self-hosted Langfuse**, so your resume never leaves your PC.

```powershell
cd infra\langfuse
docker compose up -d            # first time: ~5 GB of images
```
Generate secrets into `infra\langfuse\.env` (see the comments in
`infra\langfuse\docker-compose.override.yml`), then in the project `.env`
set `TRACING=langfuse` and the `LANGFUSE_*` keys. Open
http://localhost:3000. Every run appears as a session, tagged `cli`/`web`
and with the model name, and your approve/edit/reject decision is attached
as a score. `TRACING=langsmith` (cloud) and `TRACING=off` also work.

### Monitoring dashboard

```powershell
streamlit run monitor.py --server.port 8502   # http://localhost:8502
```

One page combining **Langfuse traces** (runs, LLM calls, tokens, latency
per step, search tool success, your approve/reject decisions) with **your
tracker** (fit scores, application status). Filter by time range and by
where a run started (cli/web). Needs Langfuse running for the trace part.

### CLI approval

At the approval step you can **[a]pprove** (saves to the tracker and
`data/cover_notes/`), **[e]dit** (describe changes and get a new draft), or
**[r]eject** (nothing is saved).

If a site blocks fetching (e.g. LinkedIn), the run **pauses and asks you to
paste** the job description. Type `END` on its own line when you're done.

## Configuration (`.env`)

| Setting | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` | `ollama` | `ollama`, `anthropic`, `openai`, `google` |
| `LLM_MODEL` | `qwen3:8b` | e.g. `qwen3:14b`, `claude-sonnet-5-5`, `gpt-4o-mini` |
| `LLM_TEMPERATURE` | `0.2` | lower = more focused |
| `OLLAMA_NUM_CTX` | `16384` | context window; too small silently truncates text |
| `OLLAMA_REASONING` | `false` | Qwen3 "thinking" mode |
| `JUDGE_EVIDENCE` | `true` | second LLM call double-checks skill evidence |
| `TRACING` | `off` | `off`, `langfuse` (self-hosted), `langsmith` (cloud) |

To use a cloud model, `pip install` its LangChain package (see
`requirements.txt`) and add its API key to `.env`. No code changes needed.

## Tests

```powershell
python -m pytest
```

These tests cover the code-only safety nets (evidence and URL/date
verification, number checks, the tracker, the approval guardrail). They use
a temporary database and need no LLM, so they run in about a second.

To compare models on a tracked job:
```powershell
python compare_models.py 1 qwen3:8b qwen3:14b
```

## How it works (short version)

```
check_tracker ─(already tracked)──────────────────────────────┐
     │                                                         ▼
read_posting → analyze_fit → research_company → save → cover_note (subgraph)
                 (+ judge)     (ReAct agent:              draft → review ⏸ → save
                               LLM picks searches)               ↑ edit ┘
```

- **A workflow with one agent inside:** the step order is fixed in code, and
  only company research lets the LLM decide what to do.
- **Don't trust, verify:** resume quotes, source URLs, news dates and numbers
  are checked by code, and an LLM judge reviews the skill evidence.
- **Human-in-the-loop:** LangGraph `interrupt()` pauses the graph. Saving is
  blocked in code unless you approve.

See [architecture.md](architecture.md) for the full picture.

## Project layout

```
main.py               CLI: start here
app.py                web UI (Streamlit)
monitor.py            monitoring dashboard (Streamlit + Altair)
compare_models.py     run the same task on several models
phaseN_*.py           the learning steps, each runnable on its own
job_agent/
  llm.py              model factory, retries, Ollama check
  models.py           Pydantic data models
  posting.py          read job posting
  resume.py           load resume PDFs
  fit.py              fit analysis, evidence check, LLM judge
  research.py         company research agent (LangGraph ReAct)
  tracker.py          SQLite tracker
  cover_note.py       draft + approval subgraph
  graph.py            the main workflow
  tracing.py          Langfuse / LangSmith switch
  monitoring.py       data layer for the dashboard (Langfuse API + tracker)
infra/langfuse/       self-hosted Langfuse (Docker Compose + our override)
tests/                pytest suite
```

## Using it / deployment

This is a personal, open-source project: clone the repo and run it locally,
for **$0** (local Ollama model, local SQLite, self-hosted tracing). A
Windows desktop app is the planned next step; see the "Deployment
decision" section at the end of [progress.md](progress.md) for the cost
comparison of website vs. desktop app.
