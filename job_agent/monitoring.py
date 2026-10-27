"""
Monitoring data layer: turn raw Langfuse traces + the SQLite tracker into
tables (pandas DataFrames) that the dashboard (monitor.py) can chart.

Two data sources, two kinds of truth:
    - Langfuse  = HOW the agent behaved: runs, LLM calls, tokens, latency,
                  tool calls, your approve/edit/reject decisions.
    - Tracker   = WHAT it produced: jobs, fit scores, application status.

This file has no Streamlit code on purpose: the "build_*" functions are
pure (DataFrame in, DataFrame out), so they can be unit-tested with fake
data (tests/test_monitoring.py) without Langfuse running.

Langfuse v4 read API used here (discovered in Phase 8c):
    GET /api/public/v2/observations   cursor-paginated, `fields=` groups
    GET /api/public/v3/scores
"""

import os
from datetime import datetime, timedelta, timezone

import pandas as pd
import requests

from job_agent import tracing  # noqa: F401  (loads .env so LANGFUSE_* are set)
from job_agent.tracker import list_jobs

# The main workflow's nodes, in pipeline order (graph.py).
PIPELINE_NODES = [
    "check_tracker", "read_posting", "analyze_fit",
    "research_company", "save_to_tracker", "cover_note",
]
TOOL_NAMES = ["web_search", "news_search"]
STATUS_ORDER = [
    "researched", "cover_note_ready", "applied", "interviewing", "offer", "rejected",
]


# ---------------------------------------------------------------------------
# Fetching (network)
# ---------------------------------------------------------------------------


def langfuse_url() -> str:
    return os.getenv("LANGFUSE_HOST", "http://localhost:3000").rstrip("/")


def langfuse_available() -> bool:
    try:
        return requests.get(f"{langfuse_url()}/api/public/health", timeout=3).ok
    except requests.RequestException:
        return False


def _get(path: str, params: dict) -> dict:
    auth = (os.getenv("LANGFUSE_PUBLIC_KEY", ""), os.getenv("LANGFUSE_SECRET_KEY", ""))
    r = requests.get(f"{langfuse_url()}{path}", params=params, auth=auth, timeout=30)
    r.raise_for_status()
    return r.json()


def _get_all(path: str, params: dict, max_pages: int = 50) -> list[dict]:
    """Follow cursor pagination until there are no more pages."""
    rows, cursor = [], None
    for _ in range(max_pages):
        page = _get(path, {**params, **({"cursor": cursor} if cursor else {})})
        rows.extend(page.get("data", []))
        cursor = (page.get("meta") or {}).get("cursor")
        if not cursor:
            break
    return rows


def fetch_observations(days: int | None) -> pd.DataFrame:
    """Every observation (span, LLM call, tool call) without prompts/outputs.

    We deliberately skip the `io` field group: inputs/outputs contain your
    full resume text and would make every refresh slow and heavy.
    """
    params = {"limit": 1000, "fields": "core,basic,model,usage,metrics,trace_context"}
    if days:
        since = datetime.now(timezone.utc) - timedelta(days=days)
        params["fromStartTime"] = since.isoformat()
    return pd.DataFrame(_get_all("/api/public/v2/observations", params))


def fetch_tool_calls(days: int | None) -> pd.DataFrame:
    """Tool observations WITH outputs (small), to tell success from failure.

    Our tools never raise - they return "Search failed (...)" as text so the
    agent can recover (Phase 3). So "failed" must be read from the output.
    """
    frames = []
    for name in TOOL_NAMES:
        params = {"limit": 1000, "name": name, "fields": "core,basic,io,metrics"}
        if days:
            params["fromStartTime"] = (
                datetime.now(timezone.utc) - timedelta(days=days)
            ).isoformat()
        frames.append(pd.DataFrame(_get_all("/api/public/v2/observations", params)))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()


def fetch_scores() -> pd.DataFrame:
    # The scores endpoint caps page size lower than observations (1000 -> 400).
    return pd.DataFrame(_get_all("/api/public/v3/scores", {"limit": 100}))


def fetch_jobs() -> pd.DataFrame:
    return pd.DataFrame([dict(r) for r in list_jobs()])


# ---------------------------------------------------------------------------
# Building tables (pure functions - unit-tested)
# ---------------------------------------------------------------------------


def _with_times(obs: pd.DataFrame) -> pd.DataFrame:
    obs = obs.copy()
    obs["startTime"] = pd.to_datetime(obs["startTime"], utc=True)
    obs["latency"] = pd.to_numeric(obs.get("latency"), errors="coerce").fillna(0.0)
    return obs


def interface_of(tags) -> str:
    """Which front door started the run: cli / web / api / desktop (tag from tracing.py)."""
    for t in tags if isinstance(tags, list) else []:
        if t in ("cli", "web", "api", "desktop"):
            return t
    return "unknown"


def build_llm_calls(obs: pd.DataFrame) -> pd.DataFrame:
    """One row per LLM call: model, input/output tokens, latency."""
    if obs.empty:
        return pd.DataFrame(columns=["startTime", "sessionId", "model", "input_tokens",
                                     "output_tokens", "latency", "interface"])
    gens = _with_times(obs[obs["type"] == "GENERATION"])
    usage = gens.get("usageDetails", pd.Series([{}] * len(gens), index=gens.index))
    gens["input_tokens"] = [int((u or {}).get("input", 0)) for u in usage]
    gens["output_tokens"] = [int((u or {}).get("output", 0)) for u in usage]
    gens["interface"] = [interface_of(t) for t in gens.get("tags", [None] * len(gens))]
    return gens[["startTime", "sessionId", "model", "input_tokens", "output_tokens",
                 "latency", "interface"]].reset_index(drop=True)


def build_runs(obs: pd.DataFrame) -> pd.DataFrame:
    """One row per run (= Langfuse session = LangGraph thread_id).

    'agent time' = sum of the root spans' latency, i.e. time the agent was
    actually working. It excludes the time a run sat paused waiting for you,
    which would otherwise make every run look hours long.
    """
    cols = ["sessionId", "started", "agent_seconds", "segments", "llm_calls",
            "input_tokens", "output_tokens", "interface"]
    if obs.empty:
        return pd.DataFrame(columns=cols)
    obs = _with_times(obs[obs["sessionId"].notna()])
    calls = build_llm_calls(obs)
    is_root = obs["isRootObservation"].fillna(False).astype(bool) \
        if "isRootObservation" in obs else pd.Series(False, index=obs.index)
    roots = obs[is_root]

    runs = obs.groupby("sessionId").agg(started=("startTime", "min"))
    runs["agent_seconds"] = roots.groupby("sessionId")["latency"].sum()
    runs["segments"] = roots.groupby("sessionId").size()  # start + each resume
    runs["llm_calls"] = calls.groupby("sessionId").size()
    runs["input_tokens"] = calls.groupby("sessionId")["input_tokens"].sum()
    runs["output_tokens"] = calls.groupby("sessionId")["output_tokens"].sum()
    runs["interface"] = obs.groupby("sessionId")["tags"].first().map(interface_of) \
        if "tags" in obs else "unknown"
    runs = runs.fillna(0).reset_index()
    for c in ("segments", "llm_calls", "input_tokens", "output_tokens"):
        runs[c] = runs[c].astype(int)
    return runs[cols].sort_values("started", ascending=False).reset_index(drop=True)


def build_node_latency(obs: pd.DataFrame) -> pd.DataFrame:
    """Average and slowest duration per pipeline node, in pipeline order."""
    if obs.empty:
        return pd.DataFrame(columns=["node", "avg_seconds", "max_seconds", "count"])
    obs = _with_times(obs)
    nodes = obs[obs["name"].isin(PIPELINE_NODES)]
    out = nodes.groupby("name")["latency"].agg(["mean", "max", "count"]).reset_index()
    out.columns = ["node", "avg_seconds", "max_seconds", "count"]
    out["order"] = out["node"].map(PIPELINE_NODES.index)
    return out.sort_values("order").drop(columns="order").reset_index(drop=True)


def tool_status(output) -> str:
    """'failed' if the tool returned its error text, else 'ok'."""
    text = output if isinstance(output, str) else str(output or "")
    return "failed" if "search failed" in text.lower()[:200] else "ok"


def build_tool_stats(tools: pd.DataFrame) -> pd.DataFrame:
    """Calls per tool, split into ok / failed."""
    if tools.empty:
        return pd.DataFrame(columns=["tool", "status", "calls"])
    t = tools.assign(status=tools.get("output").map(tool_status))
    return (t.groupby(["name", "status"]).size().reset_index(name="calls")
            .rename(columns={"name": "tool"}))


def build_decisions(scores: pd.DataFrame) -> pd.DataFrame:
    """Counts of your cover-note decisions (approve / edit / reject)."""
    order = ["approve", "edit", "reject"]
    if scores.empty:
        return pd.DataFrame({"decision": order, "count": [0, 0, 0]})
    d = scores[scores["name"] == "cover_note_decision"]["value"].value_counts()
    return pd.DataFrame({"decision": order, "count": [int(d.get(k, 0)) for k in order]})


def build_kpis(runs: pd.DataFrame, calls: pd.DataFrame, decisions: pd.DataFrame) -> dict:
    """The headline numbers, shared by both dashboards (Streamlit + desktop).

    'median_full_run' only counts runs that did the full analysis (>= 5 LLM
    calls), not quick re-drafts, and uses agent time (waiting excluded).
    """
    full = runs[runs["llm_calls"] >= 5] if not runs.empty else runs
    decided = int(decisions["count"].sum())
    approved = int(decisions.loc[decisions["decision"] == "approve", "count"].sum())
    return {
        "runs": len(runs),
        "llm_calls": len(calls),
        "tokens_in": int(calls["input_tokens"].sum()) if not calls.empty else 0,
        "tokens_out": int(calls["output_tokens"].sum()) if not calls.empty else 0,
        "median_full_run": float(full["agent_seconds"].median()) if len(full) else None,
        "approved": approved,
        "decided": decided,
        "approval_rate": approved / decided if decided else None,
    }


def build_status_funnel(jobs: pd.DataFrame) -> pd.DataFrame:
    """How many tracked jobs are at each stage, in lifecycle order."""
    counts = jobs["status"].value_counts() if not jobs.empty else pd.Series(dtype=int)
    return pd.DataFrame({"status": STATUS_ORDER,
                         "jobs": [int(counts.get(s, 0)) for s in STATUS_ORDER]})
