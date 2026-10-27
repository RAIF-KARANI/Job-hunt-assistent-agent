"""
Phase 1 check: URL -> clean JobPosting.

Run:
    python phase1_read_posting.py <job-url>
    python phase1_read_posting.py path/to/job.txt     (if a site blocks fetching)
"""

import sys
import time
from pathlib import Path

from job_agent.posting import extract_job_posting, fetch_page_text

if len(sys.argv) != 2:
    sys.exit("Usage: python phase1_read_posting.py <job-url or .txt file>")

source = sys.argv[1]

print("Step 1/2: getting the posting text (plain code, no AI)...")
if source.startswith("http"):
    text = fetch_page_text(source)
else:
    text = Path(source).read_text(encoding="utf-8")
print(f"  -> {len(text):,} characters of text\n")

print("Step 2/2: asking the LLM to extract structured fields...")
start = time.time()
job = extract_job_posting(text)
print(f"  -> done in {time.time() - start:.1f}s\n")

# model_dump_json() turns the Pydantic object into pretty JSON.
print(job.model_dump_json(indent=2))
