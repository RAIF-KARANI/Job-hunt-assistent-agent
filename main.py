"""
Job Hunt Assistant - the command-line interface.

    python main.py <job-url>              full run: read, fit, research, save, cover note
    python main.py <job-url> --fresh      re-analyze even if the URL is already tracked
    python main.py path\\to\\job.txt        use pasted job text (for blocked sites)
    python main.py list                   all tracked jobs, best fit first
    python main.py show <id>              details of one job
    python main.py status <id> <status>   e.g. status 1 applied
    python main.py graph                  print the workflow as a Mermaid diagram

This file only talks to the user. All the logic lives in job_agent/.
"""

import sys
import time
import uuid

from langgraph.types import Command

from job_agent.graph import build_job_hunt_graph
from job_agent.tracker import STATUSES, get_job, list_jobs, update_status


# ---------------------------------------------------------------------------
# Full run
# ---------------------------------------------------------------------------


def run(url: str, fresh: bool) -> None:
    start = time.time()
    graph = build_job_hunt_graph()
    # A new thread_id per run: this run's checkpoints are kept separate.
    config = {"configurable": {"thread_id": str(uuid.uuid4())}}

    result = graph.invoke({"url": url, "fresh": fresh}, config)

    # Paused inside the cover-note subgraph, waiting for the human.
    while "__interrupt__" in result:
        answer = ask_for_approval(result["__interrupt__"][0].value)
        result = graph.invoke(Command(resume=answer), config)

    print()
    if result.get("saved_path"):
        print(f"Approved and saved: {result['saved_path']}")
        print(f"Job #{result['job_id']} status -> cover_note_ready")
    else:
        print(f"Cover note rejected - nothing saved. Job #{result['job_id']} "
              "is still in the tracker.")
    print(f"Total time: {time.time() - start:.0f}s")


def ask_for_approval(payload: dict) -> dict:
    """Show the draft and turn the user's choice into the resume value."""
    print("\n[5/5] Cover note - the graph is PAUSED until you decide")
    print("=" * 70)
    print(f"DRAFT #{payload['revision']}  ({payload['word_count']} words)")
    print("=" * 70)
    print(payload["draft"])
    print("=" * 70)
    if payload["warnings"]:
        print(f"! Check these numbers - not found in your resume or research: "
              f"{', '.join(payload['warnings'])}")

    choice = ""
    while choice not in ("a", "e", "r"):
        choice = input("\n[a]pprove and save / [e]dit / [r]eject: ").strip().lower()
    if choice == "a":
        return {"decision": "approve"}
    if choice == "e":
        return {"decision": "edit", "feedback": input("What should change? ").strip()}
    return {"decision": "reject"}


# ---------------------------------------------------------------------------
# Tracker commands
# ---------------------------------------------------------------------------


def show_list() -> None:
    rows = list_jobs()
    if not rows:
        print("No jobs tracked yet. Try: python main.py <job-url>")
        return
    print(f"{'ID':>3}  {'FIT':>3}  {'STATUS':<16} {'COMPANY':<14} TITLE")
    for r in rows:
        print(f"{r['id']:>3}  {r['fit_score']:>3}  {r['status']:<16} "
              f"{r['company'][:14]:<14} {r['title'][:55]}")


def show(job_id: int) -> None:
    data = get_job(job_id)
    if data is None:
        sys.exit(f"No job with id {job_id}")
    job, best, brief = data["job"], data["best_match"], data["company_brief"]
    print(f"#{data['id']}  {job.title} @ {job.company}")
    print(f"URL:      {data['url']}")
    print(f"Status:   {data['status']}")
    print(f"Location: {job.location}   Salary: {job.salary}")
    print(f"Fit:      {best.analysis.fit_score}/100 with {best.resume_name}")
    print(f"Verdict:  {best.analysis.verdict}")
    print("Gaps:     " + (", ".join(best.analysis.missing_skills) or "none found"))
    if brief:
        print(f"Company:  {brief.what_they_do}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if args == ["list"]:
        show_list()
    elif len(args) == 2 and args[0] == "show":
        show(int(args[1]))
    elif len(args) == 3 and args[0] == "status":
        update_status(int(args[1]), args[2])
        print(f"Job #{args[1]} -> {args[2]}")
    elif args == ["graph"]:
        print(build_job_hunt_graph().get_graph(xray=True).draw_mermaid())
    elif args and args[0] not in ("list", "show", "status", "graph"):
        run(args[0], fresh="--fresh" in args[1:])
    else:
        sys.exit(__doc__ + f"\nStatuses: {', '.join(STATUSES)}")
