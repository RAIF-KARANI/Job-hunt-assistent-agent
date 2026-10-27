"""
Phase 2 check: URL -> JobPosting -> score each resume -> pick the best.

Run:
    python phase2_fit.py <job-url or .txt file>
"""

import sys
import time
from pathlib import Path

from job_agent.fit import pick_best_resume
from job_agent.posting import extract_job_posting, fetch_page_text
from job_agent.resume import load_resumes

if len(sys.argv) != 2:
    sys.exit("Usage: python phase2_fit.py <job-url or .txt file>")

source = sys.argv[1]
start = time.time()

print("Step 1/3: reading the job posting...")
text = fetch_page_text(source) if source.startswith("http") else Path(source).read_text(encoding="utf-8")
job = extract_job_posting(text)
print(f"  -> {job.title} @ {job.company}\n")

print("Step 2/3: loading resumes from data/...")
resumes = load_resumes()
print(f"  -> found {len(resumes)}: {', '.join(resumes)}\n")

print("Step 3/3: comparing each resume with the job (one LLM call each)...")
best, all_matches = pick_best_resume(job, resumes)

print("\n=== Scores ===")
for m in all_matches:
    marker = "  <- best" if m is best else ""
    verified = len(m.analysis.matching_skills)
    print(
        f"  {m.analysis.fit_score:>3}/100  {m.resume_name}"
        f"  ({verified} verified, {len(m.rejected_matches)} rejected){marker}"
    )

a = best.analysis
print(f"\n=== Best resume: {best.resume_name} ===")
print(f"Verdict: {a.verdict}\n")
print("Matching skills (evidence verified in resume):")
for s in a.matching_skills:
    print(f'  + {s.requirement}  <- "{s.resume_evidence}"')
if best.unsupported_matches:
    print("\nJudge: real quote, but doesn't prove the claim (moved to gaps):")
    for s in best.unsupported_matches:
        print(f"  ~ {s}")
if best.rejected_matches:
    print("\nRejected claims (evidence NOT found in resume):")
    for s in best.rejected_matches:
        print(f'  x {s.requirement}  <- "{s.resume_evidence}"')
print("\nGaps:")
for s in a.missing_skills:
    print(f"  - {s}")
print("\nTalking points for the cover note:")
for s in a.talking_points:
    print(f"  * {s}")

print(f"\nTotal time: {time.time() - start:.1f}s")
