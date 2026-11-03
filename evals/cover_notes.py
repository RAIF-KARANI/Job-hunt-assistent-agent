"""
15f: the cover-note eval. For every job in the tracker (or the ones given),
draft a cover note from its saved analysis and research, with the old prompt
(whole resume + talking points) and the new one (achievements picked by
code), and measure:
  - which of the resume's projects each note mentions, and how often one
    project appears across all notes (CodeLens was in 23 of 35)
  - projects put at the wrong employer / role / school (placement notices)
  - stock phrases ("I'm excited to apply", "aligns with my passion")
  - numbers that aren't in the sources, and the length
Nothing is saved to the tracker; the notes go to data/evals/results/.

    python -m evals.cover_notes [--jobs 1 3 4] [--only new|old]
"""

from __future__ import annotations

import argparse
import json
import re
import sqlite3
import sys
import time
from collections import Counter
from datetime import datetime

from job_agent import paths
from job_agent.achievements import resume_entries
from job_agent.cover_note import STOCK_PHRASES, draft_cover_note, note_notices, unverified_numbers
from job_agent.models import CompanyBrief, JobPosting, ResumeMatch
from job_agent.resume import load_resumes


def saved_jobs(ids: list[int] | None) -> list[dict]:
    with sqlite3.connect(f"file:{paths.DB_PATH}?mode=ro", uri=True) as db:
        rows = db.execute("SELECT id, job_json, fit_json, company_json FROM jobs ORDER BY id").fetchall()
    out = []
    for jid, job, fit, brief in rows:
        if ids and jid not in ids or not job or not fit:
            continue
        out.append({"id": jid, "job": JobPosting.model_validate_json(job),
                    "match": ResumeMatch.model_validate_json(fit),
                    "brief": CompanyBrief.model_validate_json(brief) if brief else None})
    return out


def measure(note: str, resume_text: str, sources: str) -> dict:
    projects = [e.name for e in resume_entries(resume_text) if e.kind == "project" and len(e.name) >= 3]
    low = note.lower().replace("’", "'")
    return {
        "projects": [p for p in projects if p.lower() in low],
        "notices": [n for n in note_notices(note, resume_text) if "Stock phrase" not in n],
        "stock": [p for p in STOCK_PHRASES if p in low],
        "numbers": unverified_numbers(note, sources),
        "words": len(re.findall(r"\b\w+\b", note)),
    }


def summary(notes: list[dict]) -> dict:
    n = len(notes)
    counts = Counter(p for x in notes for p in set(x["projects"]))
    return {
        "notes": n,
        "most_used_project": counts.most_common(1)[0] if counts else None,
        "project_share": {p: f"{c}/{n}" for p, c in counts.most_common()},
        "misplaced": sum(1 for x in notes if x["notices"]),
        "stock_phrases": sum(1 for x in notes if x["stock"]),
        "unverified_numbers": sum(len(x["numbers"]) for x in notes),
        "words_avg": round(sum(x["words"] for x in notes) / n) if n else 0,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.cover_notes")
    parser.add_argument("--jobs", type=int, nargs="*")
    parser.add_argument("--only", choices=("old", "new"))
    args = parser.parse_args(argv)
    resumes = load_resumes()
    variants = [v for v in ("old", "new") if not args.only or v == args.only]
    report = {"started": datetime.now().isoformat(timespec="seconds"), "jobs": [], "summary": {}}
    by_variant: dict[str, list[dict]] = {v: [] for v in variants}
    for item in saved_jobs(args.jobs):
        job, match = item["job"], item["match"]
        text = resumes.get(match.resume_name)
        if text is None:
            print(f"#{item['id']}: resume '{match.resume_name}' isn't in data/: skipped")
            continue
        sources = text + job.model_dump_json() + (item["brief"].model_dump_json() if item["brief"] else "")
        row = {"id": item["id"], "job": f"{job.title} @ {job.company}", "resume": match.resume_name}
        for variant in variants:
            start = time.perf_counter()
            try:
                note = draft_cover_note(job, match, item["brief"], text, use_picked=(variant == "new")).text
            except Exception as e:
                print(f"#{item['id']} {variant}: FAILED {type(e).__name__}: {e}")
                continue
            m = measure(note, text, sources) | {"seconds": round(time.perf_counter() - start, 1), "text": note}
            row[variant] = m
            by_variant[variant].append(m)
            print(f"#{item['id']:<3} {variant}: {m['words']:3d} words | projects {m['projects']} | "
                  f"misplaced {len(m['notices'])} | stock {len(m['stock'])} | {m['seconds']} s")
        report["jobs"].append(row)
    for variant, notes in by_variant.items():
        report["summary"][variant] = summary(notes)
        print(f"\n=== {variant}: {json.dumps(report['summary'][variant], ensure_ascii=False)}")
    out = paths.DATA_DIR / "evals" / "results" / f"{datetime.now():%Y%m%d-%H%M}_cover_notes.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"\nSaved {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
