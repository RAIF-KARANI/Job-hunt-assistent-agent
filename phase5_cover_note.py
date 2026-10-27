"""
Phase 5 check: draft a cover note for a tracked job and approve / edit / reject it.

Run:
    python phase4_tracker.py list          (find the job id)
    python phase5_cover_note.py <job-id>
"""

import sys

from langgraph.types import Command

from job_agent.cover_note import build_cover_note_graph
from job_agent.resume import load_resumes
from job_agent.tracker import get_job

if len(sys.argv) != 2:
    sys.exit("Usage: python phase5_cover_note.py <job-id>")

data = get_job(int(sys.argv[1]))
if data is None:
    sys.exit(f"No job with id {sys.argv[1]}. See: python phase4_tracker.py list")

job, best = data["job"], data["best_match"]
print(f"Cover note for #{data['id']}: {job.title} @ {job.company}")
print(f"Using resume: {best.resume_name} (fit {best.fit_score}/100)\n")

graph = build_cover_note_graph()

# thread_id = which conversation/run this is. The checkpointer stores the
# paused state under this id, and resuming with the same id continues it.
config = {"configurable": {"thread_id": f"cover-note-job-{data['id']}"}}

result = graph.invoke(
    {
        "job_id": data["id"],
        "job": job,
        "best_match": best,
        "company_brief": data["company_brief"],
        "resume_text": load_resumes()[best.resume_name],
    },
    config,
)

# While the graph is paused at interrupt(), the result contains "__interrupt__".
while "__interrupt__" in result:
    payload = result["__interrupt__"][0].value

    print("\n" + "=" * 70)
    print(f"DRAFT #{payload['revision']}  ({payload['word_count']} words)"
          "  - graph is PAUSED, waiting for you")
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
        answer = {"decision": "approve"}
    elif choice == "e":
        answer = {"decision": "edit", "feedback": input("What should change? ").strip()}
    else:
        answer = {"decision": "reject"}

    # Resume the paused graph; interrupt() inside review_node returns `answer`.
    result = graph.invoke(Command(resume=answer), config)

if result.get("saved_path"):
    print(f"\nApproved and saved: {result['saved_path']}")
    print("Tracker status -> cover_note_ready")
else:
    print("\nRejected - nothing was saved.")
