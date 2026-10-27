"""
Phase 4 check: run phases 1-3 on a job and save it to the SQLite tracker.

Run:
    python phase4_tracker.py add <job-url>        analyze + save (takes ~2-3 min)
    python phase4_tracker.py list                 show all tracked jobs
    python phase4_tracker.py show <id>            details of one job
    python phase4_tracker.py status <id> <status> e.g. status 1 applied
"""

import sys
import time

from job_agent.fit import pick_best_resume
from job_agent.posting import extract_job_posting, fetch_page_text
from job_agent.research import research_company
from job_agent.resume import load_resumes
from job_agent.tracker import DB_PATH, STATUSES, get_job, list_jobs, save_job, update_status


def add(url: str) -> None:
    start = time.time()

    print("Step 1/4: reading the job posting...")
    job = extract_job_posting(fetch_page_text(url))
    print(f"  -> {job.title} @ {job.company}\n")

    print("Step 2/4: comparing resumes...")
    best, _ = pick_best_resume(job, load_resumes())
    print(f"  -> best: {best.resume_name} ({best.fit_score}/100)\n")

    print("Step 3/4: researching the company (agent)...")
    try:
        company = research_company(job.company, job.title)
    except Exception as e:
        # Research is "nice to have": if it fails, still save the job.
        print(f"  ! research failed ({e}); saving without company brief")
        company = None
    print()

    print("Step 4/4: saving to the tracker...")
    job_id = save_job(url, job, best, company)
    print(f"  -> saved as job #{job_id} in {DB_PATH}")
    print(f"\nTotal time: {time.time() - start:.1f}s")


def show_list() -> None:
    rows = list_jobs()
    if not rows:
        print("No jobs tracked yet. Add one: python phase4_tracker.py add <url>")
        return
    print(f"{'ID':>3}  {'FIT':>3}  {'STATUS':<16} {'COMPANY':<14} TITLE")
    for r in rows:
        print(
            f"{r['id']:>3}  {r['fit_score']:>3}  {r['status']:<16} "
            f"{r['company'][:14]:<14} {r['title'][:55]}"
        )


def show(job_id: int) -> None:
    data = get_job(job_id)
    if data is None:
        sys.exit(f"No job with id {job_id}")
    job, best, brief = data["job"], data["best_match"], data["company_brief"]
    print(f"#{data['id']}  {job.title} @ {job.company}")
    print(f"URL:      {data['url']}")
    print(f"Status:   {data['status']}   (added {data['created_at']}, updated {data['updated_at']})")
    print(f"Location: {job.location}   Salary: {job.salary}")
    print(f"Fit:      {best.fit_score}/100 with {best.resume_name}")
    print(f"Verdict:  {best.analysis.verdict}")
    if brief:
        print(f"Company:  {brief.what_they_do}")


if __name__ == "__main__":
    args = sys.argv[1:]
    if len(args) == 2 and args[0] == "add":
        add(args[1])
    elif args == ["list"]:
        show_list()
    elif len(args) == 2 and args[0] == "show":
        show(int(args[1]))
    elif len(args) == 3 and args[0] == "status":
        update_status(int(args[1]), args[2])
        print(f"Job #{args[1]} -> {args[2]}")
    else:
        sys.exit(__doc__ + f"\nStatuses: {', '.join(STATUSES)}")
