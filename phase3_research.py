"""
Phase 3 check: company name -> agent searches the web -> CompanyBrief.

Run:
    python phase3_research.py "GitLab"
    python phase3_research.py "GitLab" "Backend Engineer, AI Engineering"
"""

import sys
import time

from job_agent.research import build_research_graph, research_company

if len(sys.argv) not in (2, 3):
    sys.exit('Usage: python phase3_research.py "<company>" ["<role>"]')

company = sys.argv[1]
role = sys.argv[2] if len(sys.argv) == 3 else ""

# Print the graph structure as a Mermaid diagram (paste into mermaid.live).
print("Graph structure:")
print(build_research_graph().get_graph().draw_mermaid())

print(f"Researching {company}...\n")
start = time.time()
brief = research_company(company, role)
print(f"\nDone in {time.time() - start:.1f}s\n")

print(f"=== {company} ===")
print(f"What they do: {brief.what_they_do}\n")
print(f"Size/stage: {brief.size_and_stage}\n")
for title, items in [
    ("Products", brief.products),
    ("Recent news", brief.recent_news),
    ("Culture & values", brief.culture_and_values),
    ("Cover note hooks", brief.cover_note_hooks),
    ("Sources (verified)", brief.sources),
]:
    print(f"{title}:")
    for item in items:
        print(f"  - {item}")
    print()
