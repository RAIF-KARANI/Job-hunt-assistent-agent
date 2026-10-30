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

# The main workflow's nodes, in pipeline order (graph.py). The last one is
# `draft` (inside the cover-note subgraph), not `cover_note`: cover_note
# pauses for your review, so its own timing is split in two and the part
# after the resume is ~0 s. `draft` is the model writing (each rewrite
# counts once). Changed in 12f (D19).
PIPELINE_NODES = [
    "check_tracker", "read_posting", "analyze_fit",
    "research_company", "save_to_tracker", "draft",
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


# ---------------------------------------------------------------------------
# Phase 11: the same tables from JobLens' OWN run log (local SQLite), so the
# desktop Dashboard works for every user - no Langfuse, no Docker. Column
# names match the Langfuse builders above, so build_kpis() works on both.
# ---------------------------------------------------------------------------

QUALITY_LABELS = {  # check name -> what the user sees
    "fake_quotes_caught": "Fake resume quotes caught",
    "judge_rejections": "Claims rejected by the judge",
    "invented_urls_removed": "Invented source URLs removed",
    "invented_dates_removed": "Invented news dates removed",
    "number_warnings": "Unverified numbers flagged",
    "search_failures": "Web searches that failed",
}


def _local(sql: str, params=()) -> pd.DataFrame:
    from job_agent import runlog, tracker

    runlog.init_db()
    with tracker._db() as conn:
        return pd.read_sql_query(sql, conn, params=params)


def _since(days: int | None) -> str:
    if not days:
        return "1970-01-01"
    return (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%d %H:%M:%S")


def local_runs(days: int | None = 30) -> pd.DataFrame:
    df = _local("SELECT * FROM runs WHERE started_at >= ? ORDER BY started_at DESC", (_since(days),))
    return df.rename(columns={"run_id": "sessionId", "started_at": "started"})


def local_llm_calls(days: int | None = 30) -> pd.DataFrame:
    return _local("""SELECT c.model, c.input_tokens, c.output_tokens, c.seconds AS latency, c.step
                     FROM run_llm_calls c JOIN runs r ON r.run_id = c.run_id
                     WHERE r.started_at >= ?""", (_since(days),))


def local_node_latency(days: int | None = 30) -> pd.DataFrame:
    steps = _local("""SELECT s.step AS name, s.seconds AS latency FROM run_steps s
                      JOIN runs r ON r.run_id = s.run_id WHERE r.started_at >= ?""", (_since(days),))
    steps["startTime"] = "1970-01-01T00:00:00Z"   # build_node_latency() expects these columns
    return build_node_latency(steps)


def local_decisions(days: int | None = 30) -> pd.DataFrame:
    runs = local_runs(days)
    counts = runs["decision"].value_counts() if not runs.empty else pd.Series(dtype=int)
    return pd.DataFrame({"decision": ["approve", "edit", "reject"],
                         "count": [int(counts.get(k, 0)) for k in ("approve", "edit", "reject")]})


def build_quality(quality: pd.DataFrame, runs: pd.DataFrame) -> pd.DataFrame:
    """Average safety-net catches per run that ran that check (pure)."""
    q = quality.copy()
    if not runs.empty:  # search failures come from the runs table
        q = pd.concat([q, pd.DataFrame({"run_id": runs["sessionId"], "check_name": "search_failures",
                                        "value": runs["tool_failures"]})[runs["tool_calls"] > 0]])
    q = q[q["check_name"].isin(QUALITY_LABELS)] if not q.empty else q
    if q.empty:
        return pd.DataFrame(columns=["check", "per_run", "total", "runs"])
    out = q.groupby("check_name")["value"].agg(["mean", "sum", "count"]).reset_index()
    out.columns = ["check_name", "per_run", "total", "runs"]
    out["order"] = out["check_name"].map(list(QUALITY_LABELS).index)
    out["check"] = out["check_name"].map(QUALITY_LABELS)
    return out.sort_values("order")[["check", "per_run", "total", "runs"]].reset_index(drop=True)


def local_quality(days: int | None = 30) -> tuple[pd.DataFrame, float | None]:
    """(average catches per run, overall evidence pass rate)."""
    quality = _local("""SELECT q.run_id, q.check_name, q.value FROM run_quality q
                        JOIN runs r ON r.run_id = q.run_id WHERE r.started_at >= ?""", (_since(days),))
    rates = quality[quality["check_name"] == "evidence_pass_rate"]["value"]
    return build_quality(quality, local_runs(days)), (float(rates.mean()) if len(rates) else None)


def build_feedback(feedback: pd.DataFrame) -> pd.DataFrame:
    """Counts per (aspect, rating) in a fixed order, zeros included (pure)."""
    from job_agent.runlog import FEEDBACK_OPTIONS

    rows = []
    for aspect, ratings in FEEDBACK_OPTIONS.items():
        sub = feedback[feedback["aspect"] == aspect] if not feedback.empty else feedback
        counts = sub["rating"].value_counts() if not sub.empty else pd.Series(dtype=int)
        label = "Fit score" if aspect == "fit_score" else "Cover note"
        rows += [{"label": f"{label}: {r}", "aspect": aspect, "rating": r,
                  "count": int(counts.get(r, 0))} for r in ratings]
    return pd.DataFrame(rows)


def local_feedback(days: int | None = None) -> pd.DataFrame:
    return build_feedback(_local("SELECT aspect, rating FROM run_feedback WHERE created_at >= ?",
                                 (_since(days),)))


def build_status_funnel(jobs: pd.DataFrame) -> pd.DataFrame:
    """How many tracked jobs are at each stage, in lifecycle order."""
    counts = jobs["status"].value_counts() if not jobs.empty else pd.Series(dtype=int)
    return pd.DataFrame({"status": STATUS_ORDER,
                         "jobs": [int(counts.get(s, 0)) for s in STATUS_ORDER]})


# ---------------------------------------------------------------------------
# Phase 12f2: the Evals screen - how well the agent did, per run and per
# model, from the local run log. build_evals() is pure (DataFrames in, plain
# dicts out) so it's unit-tested with hand-made tables.
# ---------------------------------------------------------------------------

EVAL_CHECKS = {  # run_quality check -> (label, what it means)
    "claims_checked": ("Claims checked", "skill claims the fit analysis made"),
    "fake_quotes_caught": ("Fake quotes caught", "quote not found in your resume"),
    "judge_rejections": ("Judge rejections", "quote is real but doesn't prove the skill"),
    "invented_urls_removed": ("Invented URLs removed", "source not in the search results"),
    "invented_dates_removed": ("Invented dates removed", "news date not in the search results"),
    "number_warnings": ("Number warnings", "number in the cover note found nowhere"),
    "draft_rewrites": ("Draft rewrites", "times you asked for a new draft"),
}
# LLM calls made inside a step count towards it: the research agent's own
# node is called "agent".
CALL_STEP = {"agent": "research_company"}
FULL_RUN_CALLS = 5  # same rule as build_kpis(): runs that did the whole analysis


def _num(value):
    """numpy/NaN -> plain float or None (JSON-safe)."""
    if value is None or pd.isna(value):
        return None
    return float(value)


def _median_full(runs: pd.DataFrame):
    full = runs[runs["llm_calls"] >= FULL_RUN_CALLS]
    return _num(full["agent_seconds"].median()) if len(full) else None


def _per_run_quality(quality: pd.DataFrame) -> pd.DataFrame:
    """run_quality rows, with draft_revisions (1 = first draft) turned into rewrites."""
    q = quality.copy()
    drafts = q["check_name"] == "draft_revisions"
    q.loc[drafts, "value"] = (q.loc[drafts, "value"] - 1).clip(lower=0)
    q.loc[drafts, "check_name"] = "draft_rewrites"
    return q


def _result(run) -> str:
    if run["status"] == "error":
        return "error"
    if run["status"] == "paused":
        return "not finished"
    return {"approve": "approved", "reject": "rejected"}.get(run["decision"], "done")


def build_evals(runs: pd.DataFrame, quality: pd.DataFrame, steps: pd.DataFrame,
                calls: pd.DataFrame, feedback: pd.DataFrame, jobs: pd.DataFrame,
                model: str | None = None, recent: int = 15, trend: int = 20) -> dict:
    """Everything the Evals screen shows. `model` filters all of it except
    the model comparison (which always shows every model)."""
    runs = runs.sort_values("started_at").reset_index(drop=True)
    rates_all = quality[quality["check_name"] == "evidence_pass_rate"].set_index("run_id")["value"]

    models = []
    for name, group in runs.groupby("model", sort=False):
        full = group[group["llm_calls"] >= FULL_RUN_CALLS]
        rates = rates_all.reindex(group["run_id"]).dropna()
        models.append({
            "model": name, "provider": group["provider"].iloc[-1], "runs": len(group),
            "pass_rate": _num(rates.mean()) if len(rates) else None,
            "approved": int((group["decision"] == "approve").sum()),
            "decided": int(group["decision"].isin(["approve", "reject"]).sum()),
            "median_seconds": _median_full(group),
            "tokens_per_run": _num((full["input_tokens"] + full["output_tokens"]).mean()) if len(full) else None,
        })
    models.sort(key=lambda m: -m["runs"])

    if model:
        runs = runs[runs["model"] == model].reset_index(drop=True)
        keep = set(runs["run_id"])
        quality, steps, calls, feedback = (df[df["run_id"].isin(keep)]
                                           for df in (quality, steps, calls, feedback))

    # ---- headline numbers ----
    rates = rates_all.reindex(runs["run_id"]).dropna()  # in run order
    window = min(10, len(rates) // 2)  # latest runs vs the same number before them
    delta = (_num(rates.iloc[-window:].mean() - rates.iloc[-2 * window:-window].mean())
             if window >= 2 else None)
    full = runs[runs["llm_calls"] >= FULL_RUN_CALLS]
    kpis = {
        "runs": len(runs),
        "pass_rate": _num(rates.mean()) if len(rates) else None,
        "pass_rate_delta": delta, "pass_rate_window": window if delta is not None else None,
        "approved": int((runs["decision"] == "approve").sum()),
        "decided": int(runs["decision"].isin(["approve", "reject"]).sum()),
        "median_seconds": _median_full(runs),
        "full_runs": len(full),
        "tokens_in_per_run": _num(full["input_tokens"].mean()) if len(full) else None,
        "tokens_out_per_run": _num(full["output_tokens"].mean()) if len(full) else None,
        "tool_calls": int(runs["tool_calls"].sum()),
        "tool_failures": int(runs["tool_failures"].sum()),
    }

    # ---- evidence pass rate, run by run ----
    started = runs.set_index("run_id")["started_at"]
    trend_rows = [{"run_id": rid, "started_at": started[rid], "rate": float(v)}
                  for rid, v in rates.iloc[-trend:].items()]

    # ---- safety nets ----
    q = _per_run_quality(quality)
    checks = []
    for name, (label, meaning) in EVAL_CHECKS.items():
        values = q[q["check_name"] == name]["value"]
        checks.append({"check": name, "label": label, "meaning": meaning,
                       "total": float(values.sum()), "runs": len(values),
                       "per_run": _num(values.mean()) if len(values) else None})

    # ---- where the time goes ----
    out_tokens = calls.groupby(calls["step"].map(lambda s: CALL_STEP.get(s, s)))["output_tokens"].sum()
    time_rows = []
    for node in PIPELINE_NODES:
        seconds = steps[steps["step"] == node]["seconds"]
        if len(seconds):
            time_rows.append({"node": node, "avg_seconds": float(seconds.mean()), "count": len(seconds),
                              "out_tokens": float(out_tokens.get(node, 0)) / len(seconds)})
    timed = calls[calls["output_tokens"] > 0]
    corr = {"output": None, "input": None, "calls": len(timed)}
    if len(timed) >= 3:
        corr["output"] = _num(timed["output_tokens"].corr(timed["seconds"]))
        corr["input"] = _num(timed["input_tokens"].corr(timed["seconds"]))

    # ---- recent runs ----
    names = jobs.set_index("id")[["company", "title"]]
    recent_rows = []
    for _, r in runs.iloc[::-1].head(recent).iterrows():
        job_id = int(r["job_id"]) if pd.notna(r["job_id"]) else None
        recent_rows.append({
            "run_id": r["run_id"], "started_at": r["started_at"], "model": r["model"],
            "result": _result(r), "agent_seconds": float(r["agent_seconds"] or 0),
            "llm_calls": int(r["llm_calls"] or 0),
            "tokens": int((r["input_tokens"] or 0) + (r["output_tokens"] or 0)),
            "pass_rate": _num(rates_all.get(r["run_id"])),
            # Runs from before 12f2 have no value: NULL -> NaN in pandas, and NaN is truthy.
            "tracing": r["tracing"] if isinstance(r.get("tracing"), str) else "off",
            "job": ({"id": job_id, **names.loc[job_id].to_dict()}
                    if job_id is not None and job_id in names.index else None),
        })

    return {"model": model, "models": models, "kpis": kpis, "trend": trend_rows,
            "ratings": build_feedback(feedback).to_dict("records"),
            "checks": checks, "steps": time_rows, "correlation": corr, "recent": recent_rows}


def local_evals(model: str | None = None) -> dict:
    return build_evals(
        _local("SELECT * FROM runs"),
        _local("SELECT run_id, check_name, value FROM run_quality"),
        _local("SELECT run_id, step, seconds FROM run_steps"),
        _local("SELECT run_id, step, model, input_tokens, output_tokens, seconds FROM run_llm_calls"),
        _local("SELECT run_id, aspect, rating FROM run_feedback"),
        _local("SELECT id, company, title FROM jobs"),
        model,
    )
