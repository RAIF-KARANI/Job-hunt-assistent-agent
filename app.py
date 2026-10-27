"""
Phase 8b: a web UI for JobLens (the Job Hunt Assistant), built with Streamlit.

Run:
    streamlit run app.py          (opens http://localhost:8501)

How Streamlit works - and why it changes the agent design:
    Streamlit re-runs THIS WHOLE FILE from the top every time you click a
    button. Nothing in normal Python variables survives between clicks.
    So a run that is paused at interrupt() can't live in memory like in
    main.py. Instead:

      1. The graph uses a SQLite checkpointer (data/checkpoints.db), so every
         step - including the pause - is saved to disk.
      2. The run's thread_id is stored in the page URL (?thread=...).
      3. On every rerun we ask the graph "where is this thread?" with
         graph.get_state(config) and draw the matching screen.

    That also means you can reload the page, or close the tab and come back
    with the same URL, and the paused run is still waiting for you.

This file only draws the UI. All logic stays in job_agent/ (same as main.py).
"""

import sqlite3
import sys
import uuid

import pandas as pd
import streamlit as st
from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.types import Command

from job_agent.cover_note import SAFE_SERDE
from job_agent.graph import build_job_hunt_graph
from job_agent.llm import check_llm_ready
from job_agent.paths import CHECKPOINT_DB, DATA_DIR
from job_agent.tracker import STATUSES, get_job, list_jobs, update_status
from job_agent.tracing import flush, record_decision, tracing_config

st.set_page_config(page_title="JobLens", page_icon="🔎", layout="wide")


# ---------------------------------------------------------------------------
# The graph, with a checkpointer that survives reruns
# ---------------------------------------------------------------------------


@st.cache_resource  # build once per server, not on every rerun
def get_graph():
    DATA_DIR.mkdir(exist_ok=True)
    # check_same_thread=False: Streamlit may call us from different threads.
    conn = sqlite3.connect(CHECKPOINT_DB, check_same_thread=False)
    return build_job_hunt_graph(checkpointer=SqliteSaver(conn, serde=SAFE_SERDE))


def config_for(thread_id: str) -> dict:
    return {"configurable": {"thread_id": thread_id}}


class LogBuffer:
    """Collects everything the agent print()s, to show it in the browser.

    Our nodes print progress lines (e.g. "[agent] decides to call web_search").
    We temporarily point sys.stdout here while the graph runs. Prints can come
    from worker threads, so we only APPEND here (safe from any thread) and the
    main script thread redraws the log after each graph step.
    """

    def __init__(self):
        self.lines: list[str] = []

    def write(self, text: str) -> None:
        self.lines.append(text)

    def flush(self) -> None:
        pass

    def text(self) -> str:
        return "".join(self.lines).strip()


def run_graph(graph_input, thread_id: str) -> None:
    """Run (or resume) the graph until it finishes or pauses, showing live progress."""
    graph = get_graph()
    log = LogBuffer()
    # Phase 8c: add tracing callbacks + metadata ({} when TRACING=off).
    config = {**config_for(thread_id), **tracing_config(thread_id, interface="web")}
    with st.status("The agent is working... (a full analysis takes ~3 min)", expanded=True) as status:
        live = st.empty()
        real_stdout, sys.stdout = sys.stdout, log
        try:
            # stream_mode="updates" yields after each node finishes, so we can
            # refresh the log between steps.
            for _ in graph.stream(graph_input, config, stream_mode="updates"):
                live.code(log.text() or "...", language=None)
        finally:
            sys.stdout = real_stdout
            flush()
        live.code(log.text() or "...", language=None)
        status.update(label="Step finished", state="complete", expanded=False)
    st.rerun()  # redraw the page for the graph's new state


# ---------------------------------------------------------------------------
# Screens
# ---------------------------------------------------------------------------


def start_screen() -> None:
    st.subheader("Analyze a job")
    st.write(
        "Paste a job posting link. The agent reads it, compares it with your "
        "resumes, researches the company, saves it to the tracker and drafts a "
        "cover note **that you approve before anything is saved**."
    )
    with st.form("start"):
        url = st.text_input("Job posting URL", placeholder="https://...")
        fresh = st.checkbox("Re-analyze even if this job is already tracked")
        submitted = st.form_submit_button("Start", type="primary")
    if submitted:
        if not url.strip():
            st.error("Please paste a URL.")
            return
        start_run(url.strip(), fresh)


def start_run(url: str, fresh: bool = False) -> None:
    try:
        check_llm_ready()
    except SystemExit as e:  # check_llm_ready() exits with a readable message
        st.error(str(e))
        return
    thread_id = str(uuid.uuid4())
    st.query_params["thread"] = thread_id  # remember the run in the URL
    run_graph({"url": url, "fresh": fresh}, thread_id)


def paste_screen(payload: dict, thread_id: str) -> None:
    st.warning(f"I couldn't read that page ({payload['reason']}). "
               "It may need a login or JavaScript.")
    st.write("Open it in your browser, copy the job description and paste it below.")
    text = st.text_area("Job description", height=350)
    if st.button("Continue", type="primary"):
        if len(text.strip()) < 200:
            st.error("That's too little text to be a job posting.")
        else:
            run_graph(Command(resume=text.strip()), thread_id)


def approval_screen(payload: dict, values: dict, thread_id: str) -> None:
    job, best = values["job"], values["best_match"]
    st.subheader(f"{job.title} @ {job.company}")

    col1, col2 = st.columns([3, 2])
    with col2:
        st.metric("Fit score", f"{best.fit_score}/100", help=best.score_breakdown)
        st.caption(f"Resume: **{best.resume_name}**")
        st.caption(best.score_breakdown)
        with st.expander("Proven matches", expanded=True):
            for m in best.analysis.matching_skills:
                st.markdown(f"- **{m.requirement}** — _\"{m.resume_evidence}\"_")
        with st.expander("Gaps"):
            for g in best.analysis.missing_skills:
                st.markdown(f"- {g}")
        brief = values.get("company_brief")
        if brief:
            with st.expander("Company research"):
                st.write(brief.what_they_do)
                for hook in brief.cover_note_hooks:
                    st.markdown(f"- {hook}")
                st.caption(" · ".join(brief.sources))

    with col1:
        st.markdown(f"**Draft #{payload['revision']}** · {payload['word_count']} words · "
                    "_the agent is paused, waiting for you_")
        if payload["warnings"]:
            st.warning("Check these numbers, they're not in your resume or the research: "
                       + ", ".join(payload["warnings"]))
        # Editable: whatever is in this box when you click Approve is saved.
        text = st.text_area("Cover note (you can edit it directly)",
                            payload["draft"], height=380)

        b1, b2 = st.columns(2)
        if b1.button("✅ Approve and save", type="primary", width="stretch"):
            record_decision(thread_id, "approve")
            run_graph(Command(resume={"decision": "approve", "text": text}), thread_id)
        if b2.button("🗑️ Reject", width="stretch"):
            record_decision(thread_id, "reject")
            run_graph(Command(resume={"decision": "reject"}), thread_id)

        feedback = st.text_input("Or ask the agent for changes",
                                 placeholder="e.g. shorter, more confident, mention remote work")
        if st.button("✏️ Rewrite with this feedback") and feedback.strip():
            record_decision(thread_id, "edit")
            run_graph(Command(resume={"decision": "edit", "feedback": feedback.strip()}),
                      thread_id)


def done_screen(values: dict) -> None:
    if values.get("saved_path"):
        st.success(f"Approved and saved to the tracker and `{values['saved_path']}`. "
                   "Status is now **cover_note_ready**.")
        st.text_area("Saved cover note", values["draft"], height=300, disabled=True)
    else:
        st.info("Cover note rejected, so nothing was saved. The job is still in your tracker.")
    if st.button("Analyze another job", type="primary"):
        st.query_params.clear()
        st.rerun()


def analyze_tab() -> None:
    thread_id = st.query_params.get("thread")
    if not thread_id:
        start_screen()
        return

    # Ask the checkpointer where this run is. This is what makes reruns work.
    snapshot = get_graph().get_state(config_for(thread_id))
    if not snapshot.values:
        st.query_params.clear()  # unknown/expired thread id
        start_screen()
        return

    if snapshot.interrupts:  # paused at an interrupt() somewhere in the graph
        payload = snapshot.interrupts[0].value
        if payload["kind"] == "paste_posting":
            paste_screen(payload, thread_id)
        else:
            approval_screen(payload, snapshot.values, thread_id)
    elif not snapshot.next:  # nothing left to run
        done_screen(snapshot.values)
    else:
        st.warning("This run stopped unexpectedly (maybe the server restarted mid-step).")
        if st.button("Resume it"):
            run_graph(None, thread_id)  # None = continue from the last checkpoint


def tracker_tab() -> None:
    rows = list_jobs()
    if not rows:
        st.info("No jobs tracked yet. Analyze one in the first tab.")
        return

    df = pd.DataFrame([dict(r) for r in rows])
    df = df.rename(columns={"fit_score": "fit", "best_resume": "resume", "updated_at": "updated (UTC)"})
    st.dataframe(df, hide_index=True, width="stretch")

    job_id = st.selectbox(
        "Job details", [r["id"] for r in rows],
        format_func=lambda i: next(f"#{r['id']}  {r['company']} - {r['title']}" for r in rows if r["id"] == i),
    )
    data = get_job(job_id)
    job, best, brief = data["job"], data["best_match"], data["company_brief"]

    c1, c2 = st.columns([3, 2])
    with c1:
        st.markdown(f"### {job.title} @ {job.company}")
        st.caption(f"{job.location} · {job.seniority} · salary: {job.salary} · [posting]({data['url']})")
        st.write(best.analysis.verdict)
        st.markdown("**Gaps:** " + (", ".join(best.analysis.missing_skills) or "none"))
        if brief:
            st.markdown(f"**Company:** {brief.what_they_do}")
    with c2:
        st.metric("Fit score", f"{best.fit_score}/100", help=best.score_breakdown)
        new_status = st.selectbox("Status", STATUSES, index=STATUSES.index(data["status"]))
        if new_status != data["status"]:
            update_status(job_id, new_status)
            st.toast(f"Job #{job_id} -> {new_status}")
            st.rerun()
        if st.button("Draft a cover note for this job"):
            # A tracked URL skips straight to the draft; the approval screen
            # then appears in the "Analyze a job" tab.
            start_run(data["url"])


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title("🔎 JobLens")
analyze, tracker = st.tabs(["Analyze a job", "Tracker"])
with analyze:
    analyze_tab()
with tracker:
    tracker_tab()
