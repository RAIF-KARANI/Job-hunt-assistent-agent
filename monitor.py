"""
Monitoring dashboard for the Job Hunt Assistant (Streamlit + Altair).

Run:
    streamlit run monitor.py --server.port 8502     (the web UI uses 8501)

What it shows, and where the data comes from:
    Langfuse (localhost:3000)  runs, LLM calls, tokens, latency, tool calls,
                               your approve/edit/reject decisions
    SQLite tracker             fit scores and application status

Why build our own when Langfuse has dashboards? Langfuse knows about tokens
and latency, but not about OUR domain: fit scores, the job pipeline, which
front door (cli/web) a run came from. Combining both sources in one page is
what "monitoring an agent" means in practice.

All data logic lives in job_agent/monitoring.py; this file only draws.
Chart choices follow one rule each: a single series gets one color; two
series get the first two validated palette slots plus a legend; ok/failed
uses the reserved status colors and always carries a text label.
"""

import altair as alt
import pandas as pd
import streamlit as st

from job_agent import monitoring as m

st.set_page_config(page_title="Agent Monitor", page_icon="📈", layout="wide")

# Palette (validated with the dataviz skill's validator, light + dark).
BLUE, ORANGE = "#2a78d6", "#eb6834"        # categorical slots 1 and 2
STATUS_OK, STATUS_FAILED = "#0ca30c", "#d03b3b"  # reserved status colors
# No "surface-colored" separator lines between stacked segments: guessing the
# page background from st.context.theme proved unreliable (it reported dark
# while the page rendered light -> black outlines). The two stacked colors
# are far apart (validated CVD dE 24.7), and every chart has a legend.
BAR = dict(cornerRadiusEnd=4)                 # rounded data-end, flat at baseline
ROW = 36        # px per bar row
CHROME = 90     # px for title + x-axis + axis title
LEGEND = 30     # px for a legend on top


def rows_height(n_rows: int, legend: bool = False) -> int:
    """Total chart height. Streamlit fits the WHOLE chart (title, axes, legend)
    into `height`, so the bars only get what's left - budget for it."""
    return ROW * max(n_rows, 1) + CHROME + (LEGEND if legend else 0)


# ---------------------------------------------------------------------------
# Data (cached for 60 s so clicking around doesn't hammer Langfuse)
# ---------------------------------------------------------------------------


@st.cache_data(ttl=60, show_spinner="Loading traces from Langfuse...")
def load_langfuse(days):
    return m.fetch_observations(days), m.fetch_tool_calls(days), m.fetch_scores()


@st.cache_data(ttl=60)
def load_jobs():
    return m.fetch_jobs()


# ---------------------------------------------------------------------------
# Chart helpers
# ---------------------------------------------------------------------------


def hbar(df, value, label, title, value_title, color=BLUE, sort=None, domain=None,
         counts=False):
    """Horizontal bars: one color, labels on the axis, value on hover + at the end.
    counts=True: whole-number ticks only (no "0.5 decisions")."""
    x = alt.X(f"{value}:Q", title=value_title,
              scale=alt.Scale(domain=domain) if domain else alt.Undefined,
              axis=alt.Axis(tickMinStep=1) if counts else alt.Undefined)
    # Band padding (not a fixed bar size) keeps thin bars with clear gaps, and
    # 36 px per row leaves room for every label - Altair silently DROPS axis
    # labels that would overlap, which hid half the step names before.
    y = alt.Y(f"{label}:N", title=None, sort=sort or "-x",
              scale=alt.Scale(paddingInner=0.45, paddingOuter=0.2),
              axis=alt.Axis(labelOverlap=False, labelLimit=180))
    base = alt.Chart(df).encode(x=x, y=y)
    bars = base.mark_bar(color=color, **BAR).encode(
        tooltip=[alt.Tooltip(f"{label}:N"), alt.Tooltip(f"{value}:Q", format=",.1f")]
    )
    text = base.mark_text(align="left", dx=4).encode(
        text=alt.Text(f"{value}:Q", format=",.0f")
    )
    return (bars + text).properties(title=title, height=rows_height(len(df)))


def show(chart):
    st.altair_chart(chart, width="stretch", theme="streamlit")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("📈 Agent Monitor")
st.caption("How the Job Hunt Assistant behaves (from Langfuse traces) and what it "
           "produced (from your tracker). Refreshes every 60 s.")

# Filters: one row above everything.
f1, f2, f3 = st.columns([2, 2, 1])
range_label = f1.selectbox("Time range", ["Last 7 days", "Last 30 days", "Last 90 days", "All time"], index=1)
days = {"Last 7 days": 7, "Last 30 days": 30, "Last 90 days": 90, "All time": None}[range_label]
interfaces = f2.multiselect("Started from", ["cli", "web", "desktop", "api"], default=["cli", "web", "desktop", "api"],
                            help="Which front door started the run (tag set in tracing.py)")
if f3.button("Refresh now", width="stretch"):
    st.cache_data.clear()

jobs = load_jobs()
if not m.langfuse_available():
    st.warning("Langfuse isn't reachable at "
               f"{m.langfuse_url()}, so only tracker data is shown. "
               "Start it with: `cd infra\\langfuse` then `docker compose up -d`.")
    obs = tools = scores = pd.DataFrame()
else:
    obs, tools, scores = load_langfuse(days)

runs = m.build_runs(obs)
runs = runs[runs["interface"].isin(interfaces)] if not runs.empty else runs
kept_sessions = set(runs["sessionId"])
obs_f = obs[obs["sessionId"].isin(kept_sessions)] if not obs.empty else obs
calls = m.build_llm_calls(obs_f)
nodes = m.build_node_latency(obs_f)
decisions = m.build_decisions(scores)

# ---- KPI tiles -------------------------------------------------------------
k = st.columns(5)
k[0].metric("Runs", f"{len(runs)}")
k[1].metric("LLM calls", f"{len(calls)}",
            help="Each call to the model: extraction, fit, judge, research, draft")
total_in, total_out = int(calls["input_tokens"].sum()), int(calls["output_tokens"].sum())
k[2].metric("Tokens", f"{total_in + total_out:,}", help=f"{total_in:,} in · {total_out:,} out")
full_runs = runs[runs["llm_calls"] >= 5]  # full analyses, not just a re-draft
k[3].metric("Median full run", f"{full_runs['agent_seconds'].median():.0f} s" if len(full_runs) else "–",
            help="Agent working time for runs that did the full analysis (excludes "
                 "time spent waiting for your decision)")
decided = int(decisions["count"].sum())
approved = int(decisions.loc[decisions["decision"] == "approve", "count"].sum())
k[4].metric("Approval rate", f"{approved / decided:.0%}" if decided else "–",
            help=f"{approved} approved out of {decided} decisions (all time)")

st.divider()

# ---- Where the time goes ---------------------------------------------------
st.subheader("Where the time goes")
c1, c2 = st.columns(2)
with c1:
    if nodes.empty:
        st.info("No pipeline runs in this range yet.")
    else:
        show(hbar(nodes, "avg_seconds", "node", "Average seconds per pipeline step",
                  "seconds", sort=m.PIPELINE_NODES))
with c2:
    if calls.empty:
        st.info("No LLM calls in this range yet.")
    else:
        # Same y-axis (seconds) for both panels: a fair side-by-side comparison.
        y = alt.Y("latency:Q", title="seconds",
                  scale=alt.Scale(domain=[0, float(calls["latency"].max()) * 1.1]))
        tip = [alt.Tooltip("model:N"), alt.Tooltip("input_tokens:Q", format=","),
               alt.Tooltip("output_tokens:Q", format=","), alt.Tooltip("latency:Q", format=".1f")]
        out_pts = alt.Chart(calls).mark_circle(size=80, color=BLUE, opacity=0.85).encode(
            x=alt.X("output_tokens:Q", title="output tokens"), y=y, tooltip=tip
        ).properties(title="vs output tokens", height=230)
        in_pts = alt.Chart(calls).mark_circle(size=80, color=BLUE, opacity=0.85).encode(
            x=alt.X("input_tokens:Q", title="input tokens"), y=y, tooltip=tip
        ).properties(title="vs input tokens", height=230)
        st.markdown("**How long each LLM call took**")
        # Two Streamlit columns instead of alt.hconcat: concatenated Altair
        # charts don't shrink to the container and overflowed off-screen.
        s1, s2 = st.columns(2)
        with s1:
            show(out_pts)
        with s2:
            show(in_pts)
        if len(calls) >= 3:
            r_out = calls["output_tokens"].corr(calls["latency"])
            r_in = calls["input_tokens"].corr(calls["latency"])
            st.caption(f"Correlation with latency: output tokens **{r_out:.2f}**, "
                       f"input tokens **{r_in:.2f}**. On a local model, the time "
                       "goes into *generating* tokens, so shorter outputs = faster runs.")

# ---- Tokens per run --------------------------------------------------------
st.subheader("Tokens per run")
if runs.empty:
    st.info("No runs in this range yet.")
else:
    tok = runs.head(15).assign(
        run=lambda d: d["started"].dt.tz_convert(None).dt.strftime("%d %b %H:%M")
        + " · " + d["interface"]
    ).melt(id_vars=["run"], value_vars=["input_tokens", "output_tokens"],
           var_name="kind", value_name="tokens")
    tok["kind"] = tok["kind"].map({"input_tokens": "input", "output_tokens": "output"})
    show(alt.Chart(tok).mark_bar().encode(
        x=alt.X("tokens:Q", title="tokens", stack="zero"),
        y=alt.Y("run:N", title=None, sort=None,
                scale=alt.Scale(paddingInner=0.45, paddingOuter=0.2),
                axis=alt.Axis(labelOverlap=False, labelLimit=200)),
        color=alt.Color("kind:N", title=None,
                        scale=alt.Scale(domain=["input", "output"], range=[BLUE, ORANGE]),
                        legend=alt.Legend(orient="top")),
        order=alt.Order("kind:N"),
        tooltip=["run:N", "kind:N", alt.Tooltip("tokens:Q", format=",")],
    ).properties(height=rows_height(tok["run"].nunique(), legend=True)))
    st.caption("Input = prompts (job, resume, research), mostly cheap to process. "
               "Output = what the model writes; that's where the time goes.")

# ---- Tools & decisions -----------------------------------------------------
c3, c4 = st.columns(2)
with c3:
    st.subheader("Search tool calls")
    tool_stats = m.build_tool_stats(tools)
    if tool_stats.empty:
        st.info("No research tool calls in this range yet.")
    else:
        # ok/failed is STATE, so it uses the reserved status colors - always
        # with a text label (legend + tooltip), never color alone.
        show(alt.Chart(tool_stats).mark_bar().encode(
            x=alt.X("calls:Q", title="calls", stack="zero", axis=alt.Axis(tickMinStep=1)),
            y=alt.Y("tool:N", title=None,
                    scale=alt.Scale(paddingInner=0.45, paddingOuter=0.2),
                    axis=alt.Axis(labelOverlap=False)),
            color=alt.Color("status:N", title=None,
                            scale=alt.Scale(domain=["ok", "failed"], range=[STATUS_OK, STATUS_FAILED]),
                            legend=alt.Legend(orient="top", labelExpr="datum.label == 'ok' ? '✓ ok' : '✗ failed'")),
            tooltip=["tool:N", "status:N", "calls:Q"],
        ).properties(height=rows_height(tool_stats["tool"].nunique(), legend=True)))
        st.caption("Failed searches aren't crashes: the tool returns the error as "
                   "text and the agent retries (Phase 3).")
with c4:
    st.subheader("Your cover-note decisions")
    if decided == 0:
        st.info("No decisions recorded yet.")
    else:
        show(hbar(decisions, "count", "decision", "", "decisions",
                  sort=["approve", "edit", "reject"], counts=True))

st.divider()

# ---- Tracker ---------------------------------------------------------------
st.subheader("Job tracker")
c5, c6 = st.columns(2)
with c5:
    if jobs.empty:
        st.info("No tracked jobs yet.")
    else:
        fit = jobs.assign(job=lambda d: "#" + d["id"].astype(str) + " " + d["company"].str[:18])
        show(hbar(fit, "fit_score", "job", "Fit score per job (computed in code, Phase 8a)",
                  "fit score", domain=[0, 100]))
with c6:
    funnel = m.build_status_funnel(jobs)
    show(hbar(funnel, "jobs", "status", "Where your applications are", "jobs",
              sort=m.STATUS_ORDER, counts=True))

# ---- Recent runs table -----------------------------------------------------
st.subheader("Recent runs")
if runs.empty:
    st.info("No runs in this range yet.")
else:
    project = obs["projectId"].dropna().iloc[0] if "projectId" in obs and not obs.empty else ""
    table = runs.assign(
        started=runs["started"].dt.tz_convert(None),
        open_in_langfuse=m.langfuse_url() + f"/project/{project}/sessions/" + runs["sessionId"],
    )[["started", "interface", "agent_seconds", "segments", "llm_calls",
       "input_tokens", "output_tokens", "open_in_langfuse"]]
    st.dataframe(
        table, hide_index=True, width="stretch",
        column_config={
            "started": st.column_config.DatetimeColumn("started (UTC)", format="D MMM, HH:mm"),
            "agent_seconds": st.column_config.NumberColumn("agent time (s)", format="%.0f"),
            "segments": st.column_config.NumberColumn("segments", help="1 = start; +1 for each resume after a decision"),
            "llm_calls": "LLM calls",
            "input_tokens": st.column_config.NumberColumn("tokens in", format="%d"),
            "output_tokens": st.column_config.NumberColumn("tokens out", format="%d"),
            "open_in_langfuse": st.column_config.LinkColumn("trace", display_text="open ↗"),
        },
    )
