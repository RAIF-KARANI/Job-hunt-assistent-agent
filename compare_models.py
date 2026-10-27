"""
Compare LLMs on the same task: the resume fit analysis for a tracked job.

Run:
    python compare_models.py <job-id> qwen3:8b qwen3:14b

Why this exists: "which model should I use?" is an engineering question with
a measurable answer. Run the SAME input through each model and compare speed
and quality side by side, instead of guessing. (LLMs are non-deterministic,
so for a real decision run it on several jobs, not just one.)
"""

import os
import sys
import time

from job_agent.fit import pick_best_resume
from job_agent.resume import load_resumes
from job_agent.tracker import get_job

if len(sys.argv) < 3:
    sys.exit("Usage: python compare_models.py <job-id> <model> [<model> ...]")

data = get_job(int(sys.argv[1]))
if data is None:
    sys.exit(f"No job with id {sys.argv[1]}")
job, resumes = data["job"], load_resumes()
print(f"Job #{data['id']}: {job.title} @ {job.company}\n")

for model in sys.argv[2:]:
    # get_llm() reads LLM_MODEL on every call, so changing it here switches model.
    os.environ["LLM_MODEL"] = model
    print(f"===== {model} =====")
    start = time.time()
    best, all_matches = pick_best_resume(job, resumes)
    elapsed = time.time() - start

    for m in all_matches:
        a = m.analysis
        print(f"  {m.fit_score:>3}/100  {m.resume_name}: "
              f"{len(a.matching_skills)} proven, {len(m.rejected_matches)} fake quotes, "
              f"{len(m.unsupported_matches)} judged unproven, {len(a.missing_skills)} gaps")
    print(f"  best: {best.resume_name}   time: {elapsed:.0f}s")
    print("  proven matches:")
    for s in best.analysis.matching_skills:
        print(f'    + {s.requirement}  <- "{s.resume_evidence[:70]}"')
    print("  judged unproven:")
    for s in best.unsupported_matches:
        print(f"    ~ {s}")
    print(f"  gaps: {', '.join(best.analysis.missing_skills) or 'none'}\n")
