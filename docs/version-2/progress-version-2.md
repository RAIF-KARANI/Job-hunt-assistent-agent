# Progress Log — JobLens version 2

What was built in each version-2 step, what went wrong, and what it
teaches. Plan: [plan-version-2.md](plan-version-2.md) · Decisions:
[decisions-version-2.md](decisions-version-2.md)

| Step | Status | Result |
|---|---|---|
| 12a Spike | ✅ | pywebview + WebView2 + three.js works; 134 MB build; 3D capped/paused ([results](spike-12a-results-version-2.md)) |
| 12b Bridge | ✅ | `desktop_web/` runner + API, 20 tests, real agent driven end to end |

---

## 12b — Bridge between the page and the agent ✅ (30 Oct 2026)

### Goal
The Python side of the new UI, before any React exists: everything the
page will call, and every event it will receive. Testable with no window
and no LLM.

### What was done
- **`desktop_web/runner.py` — `AgentRunner`**: the Qt-free version of
  `desktop/agent_worker.py`.
  - Runs the graph on a background thread and reports **events** (plain
    JSON dicts):

    | Event | Fields |
    |---|---|
    | `busy` | `busy` |
    | `log` | `text` |
    | `paused` | `kind` (`review` / `paste_posting`), `payload`, `summary` |
    | `finished` | `saved_path`, `job_id`, `decision`, `suggested_rating` |
    | `failed` | `error` |

  - **One run at a time**, guarded by a lock: two quick clicks can't start
    two runs.
  - **Answers are checked before resuming.** The decision must be
    approve / edit / reject; an approved note can't be empty; an edit needs
    feedback; pasted text only when the agent asked for it.
  - `last_pause` lets a reloaded page show the waiting review again.
  - The suggested cover-note rating (Phase 11c) comes with `finished`.
- **`desktop_web/bridge.py` — `Api`**: what the page calls through
  `window.pywebview.api`:

  | Area | Calls |
  |---|---|
  | App | `app_info`, `llm_status` |
  | Agent run | `start_run`, `resume`, `paste_text`, `run_state` |
  | Feedback | `save_feedback`, `feedback_options` |
  | Tracker | `list_jobs`, `get_job`, `set_status`, `statuses` |
  | Settings | `get_settings`, `save_settings`, `set_api_key` |

  - Everything returns JSON (Pydantic → dict).
  - Errors become rejected JS promises.
- **Security:**
  - The API key is **write-only**: the page only learns *whether* one is set.
  - Settings writes go through an **allow-list** (`UI_3D` from D14 is on it).
  - The Ollama URL can't be changed from the page.
- `requirements.txt`: `pywebview>=6.0`.
- `tests/test_bridge.py`: **20 tests** with a tiny real LangGraph graph that
  pauses exactly like the agent: review → approve / edit / reject, the
  paste flow, bad answers, busy guard, crash → `failed`, run log row,
  tracker JSON, API key never leaked, settings allow-list, feedback
  validation. **112 tests in total.**

### Problems hit
1. **Thread id vs. context.** The first version routed print() → log by
   thread id. LangGraph runs parallel work on pool threads that copy the
   caller's *context*, so a `ContextVar` follows the run, where a thread id
   would lose those lines. A test proves a pool thread's print still arrives.
2. **Endless loop, found only by the real-agent run.** If anything prints
   *while an event is being delivered* (a logger, pywebview, or the test's
   own sink), that print became a new log event, which was delivered,
   printed again, and so on: a `RecursionError` in the agent thread. Fix:
   `emit()` delivers with log capture off. A regression test now prints
   from inside the sink.

### Real check (no window)
The real agent (`job_agent.graph`) was driven through `Api` on an already
tracked job:
- it reused the saved analysis and streamed the log
- it paused for review after **25 s** (revision 1, 135 words, full summary)
- reject → `finished` with nothing saved, suggested rating "not usable",
  clean run state

### Concepts learned
- **Events vs. calls:** the page *asks* (calls that return), Python
  *tells* (one-way events). Never the other way round (spike lesson).
- **ContextVar:** "thread-local" that also follows async tasks and
  context-copying thread pools.
- **Re-entrancy:** an output hook must never trigger itself.
- **Trust boundaries:** treat the page as less trusted than Python. It
  renders text from the web, so it gets the minimum: no secrets, and only
  allow-listed writes.
