"""
Phase 6: the main workflow - every phase wired into ONE LangGraph graph.

    START
      |
    check_tracker --(URL already tracked, no --fresh)--------------+
      |                                                            |
    read_posting -> analyze_fit -> research_company -> save_job    |
                                                         |         |
                                                         v         v
                                                   cover_note (SUBGRAPH)
                                                   draft -> review(interrupt) -> save
                                                         |
                                                        END

Key ideas:

1. Workflow, not agent. The ORDER of these steps never changes, so our code
   fixes it with edges. The only "agent" (LLM deciding what to do) is the
   research step - and it lives INSIDE one node (research_company runs its
   own little graph). Agents are a tool you use where needed, not everywhere.

2. Shared state. Every node receives the whole JobHuntState and returns only
   the keys it changed. LangGraph merges them. Nodes never call each other;
   they communicate only through the state.

3. Subgraph. The Phase 5 cover-note graph is added as a single node,
   unchanged. Because JobHuntState includes all CoverNoteState keys, values
   flow in and out automatically. Its interrupt() pauses the WHOLE graph.

4. Conditional entry. check_tracker looks up the URL; if it's already
   analyzed, we jump straight to the cover note and skip ~2 minutes of work.
"""

from pathlib import Path

import requests
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph
from langgraph.types import interrupt

from job_agent.cover_note import SAFE_SERDE, CoverNoteState, build_cover_note_graph
from job_agent.fit import pick_best_resume
from job_agent.models import ResumeMatch
from job_agent.posting import extract_job_posting, fetch_page_text
from job_agent.research import research_company
from job_agent.resume import choose_resumes, load_resumes
from job_agent.tracker import find_job_id, get_job, save_job


class JobHuntState(CoverNoteState, total=False):
    """Everything the workflow knows. Inherits job, best_match, company_brief,
    resume_text, job_id, draft, decision... from CoverNoteState."""

    url: str              # a web URL, or a path to a .txt file
    fresh: bool           # True = re-analyze even if already tracked
    reused: bool          # True = loaded from the tracker, analysis skipped
    all_matches: list[ResumeMatch]
    research_checks: dict  # Phase 11b: invented URLs / dates removed by verification
    resumes: list[str] | None  # 14b: the resumes to compare (None = the default set)


def _step(n: int, text: str) -> None:
    print(f"\n[{n}/5] {text}")


# ---------------------------------------------------------------------------
# NODES - each one is a thin wrapper around the phase it came from.
# ---------------------------------------------------------------------------


def check_tracker(state: JobHuntState) -> dict:
    job_id = find_job_id(state["url"])
    if job_id is None or state.get("fresh"):
        return {"reused": False}

    data = get_job(job_id)
    best = data["best_match"]
    print(f"\nAlready tracked as job #{job_id} - reusing saved analysis "
          f"(use --fresh to redo it).")
    print(f"  {data['job'].title} @ {data['job'].company}, "
          f"fit {best.fit_score}/100 with {best.resume_name}")
    return {
        "reused": True,
        "job_id": job_id,
        "job": data["job"],
        "best_match": best,
        "company_brief": data["company_brief"],
        "resume_text": load_resumes()[best.resume_name],
    }


def route_after_check(state: JobHuntState) -> str:
    return "cover_note" if state["reused"] else "read_posting"


def read_posting(state: JobHuntState) -> dict:
    _step(1, "Reading the job posting...")
    url = state["url"]
    try:
        text = (
            fetch_page_text(url)
            if url.startswith("http")
            else Path(url).read_text(encoding="utf-8")
        )
    except (requests.RequestException, ValueError, OSError) as e:
        # Blocked site, login wall, JS-only page, typo in the path...
        # Instead of crashing, ask the human: the human is the fallback tool.
        # (On resume this node re-runs from the top, so the fetch is tried -
        # and fails - once more; then interrupt() returns the pasted text.)
        print(f"  ! couldn't read the posting: {e}")
        text = interrupt({"kind": "paste_posting", "reason": str(e)})
    job = extract_job_posting(text)
    print(f"  -> {job.title} @ {job.company} ({job.location})")
    return {"job": job}


def analyze_fit(state: JobHuntState) -> dict:
    _step(2, "Comparing your resumes with the job...")
    every = load_resumes()
    resumes, note = choose_resumes(every, state.get("resumes"))  # 14b
    if note:
        print(f"  ! {note}")
    if len(resumes) < len(every):
        print(f"  -> comparing {len(resumes)} of {len(every)} resumes")
    best, all_matches = pick_best_resume(state["job"], resumes)
    for m in all_matches:
        print(f"  {m.fit_score:>3}/100  {m.resume_name}   [{m.score_breakdown}]")
    print(f"  -> best: {best.resume_name}")
    print(f"  -> {best.analysis.verdict}")
    return {
        "best_match": best,
        "all_matches": all_matches,
        "resume_text": resumes[best.resume_name],
    }


def research(state: JobHuntState) -> dict:
    _step(3, "Researching the company (agent picks its own searches)...")
    checks: dict = {}
    try:
        brief = research_company(state["job"].company, state["job"].title, stats=checks)
        print(f"  -> {len(brief.sources)} verified sources")
    except Exception as e:
        # Graceful degradation: research is nice-to-have, not essential.
        print(f"  ! research failed ({e}) - continuing without it")
        brief = None
    return {"company_brief": brief, "research_checks": checks}


def save_to_tracker(state: JobHuntState) -> dict:
    _step(4, "Saving to the job tracker...")
    job_id = save_job(state["url"], state["job"], state["best_match"], state["company_brief"])
    print(f"  -> job #{job_id}")
    return {"job_id": job_id}


# ---------------------------------------------------------------------------
# THE GRAPH
# ---------------------------------------------------------------------------


def build_job_hunt_graph(checkpointer=None):
    graph = StateGraph(JobHuntState)

    graph.add_node("check_tracker", check_tracker)
    graph.add_node("read_posting", read_posting)
    graph.add_node("analyze_fit", analyze_fit)
    graph.add_node("research_company", research)
    graph.add_node("save_to_tracker", save_to_tracker)
    # A compiled graph can be a node. That's a subgraph.
    graph.add_node("cover_note", build_cover_note_graph(as_subgraph=True))

    graph.add_edge(START, "check_tracker")
    graph.add_conditional_edges(
        "check_tracker", route_after_check, ["read_posting", "cover_note"]
    )
    graph.add_edge("read_posting", "analyze_fit")
    graph.add_edge("analyze_fit", "research_company")
    graph.add_edge("research_company", "save_to_tracker")
    graph.add_edge("save_to_tracker", "cover_note")
    graph.add_edge("cover_note", END)

    # One checkpointer for the whole graph, subgraph included.
    return graph.compile(checkpointer=checkpointer or InMemorySaver(serde=SAFE_SERDE))
