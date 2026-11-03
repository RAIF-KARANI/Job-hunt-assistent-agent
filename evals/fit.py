"""
15a: the fit eval. Runs ONLY step 2 (compare a resume with a job) on a fixed
set of cases with hand labels, several times each, and measures how right
and how stable it is. Nothing is saved to the tracker or the run log, and
nothing is sent to Langfuse.

    python -m evals.fit list
    python -m evals.fit new <name> --job <tracker id> --resume <pdf or txt>
    python -m evals.fit run [--case NAME ...] [--runs 3] [--model qwen3:8b] [--no-judge]
    python -m evals.fit compare <old results.json> <new results.json>

Cases live in two places:
    evals/sample_cases/<name>/     made-up data, committed (works on any PC)
    data/evals/cases/<name>/       real resumes: git-ignored, like all of data/
Each case is a folder with job.json (the posting, frozen so every run sees
the same input) and case.json (the resume, the labels, an expected score).
A resume written "data:<file>" is read from the data folder.

Results go to data/evals/results/<time>_<model>.json, so a change can be
compared with the baseline (`compare`).
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

from job_agent import paths  # loads the settings (.env) on import
from evals.metrics import LABELS, compare, label_score, predict, stability

ROOT = Path(__file__).resolve().parent
SAMPLE_CASES = ROOT / "sample_cases"
REAL_CASES = paths.DATA_DIR / "evals" / "cases"
RESULTS = paths.DATA_DIR / "evals" / "results"


# ---------------------------------------------------------------------------
# cases
# ---------------------------------------------------------------------------

def case_dirs() -> dict[str, Path]:
    found = {}
    for base in (SAMPLE_CASES, REAL_CASES):
        if base.is_dir():
            for d in sorted(base.iterdir()):
                if (d / "case.json").is_file():
                    found[d.name] = d
    return found


def requirements(job: dict) -> tuple[list[str], list[str]]:
    """The job's own requirements in order, and their kind."""
    reqs = list(job["required_skills"]) + list(job["nice_to_have_skills"])
    kinds = ["required"] * len(job["required_skills"]) + ["nice"] * len(job["nice_to_have_skills"])
    return reqs, kinds


def resume_text(case_dir: Path, ref: str) -> str:
    path = paths.DATA_DIR / ref[5:] if ref.startswith("data:") else case_dir / ref
    if path.suffix.lower() == ".pdf":
        from pypdf import PdfReader  # the same extraction as job_agent.resume

        return "\n".join(page.extract_text() or "" for page in PdfReader(path).pages)
    return path.read_text(encoding="utf-8")


def load_case(case_dir: Path) -> dict:
    case = json.loads((case_dir / "case.json").read_text(encoding="utf-8"))
    job = json.loads((case_dir / "job.json").read_text(encoding="utf-8"))
    reqs, kinds = requirements(job)
    labels = [entry["label"] for entry in case["labels"]]
    if [entry["requirement"] for entry in case["labels"]] != reqs:
        raise ValueError(f"{case_dir.name}: the labels don't list job.json's requirements in order")
    bad = [label for label in labels if label not in LABELS]
    if bad:
        raise ValueError(f"{case_dir.name}: unlabelled requirements ({bad[0]!r}); use {LABELS}")
    return {"name": case_dir.name, "dir": case_dir, "job": job, "reqs": reqs, "kinds": kinds,
            "labels": labels, "resume": resume_text(case_dir, case["resume"]),
            "expected": case.get("expected_score")}


def new_case(name: str, job_id: int, resume: str) -> Path:
    """Freeze a tracked job (repo tracker) into a new case with blank labels."""
    with sqlite3.connect(f"file:{paths.DB_PATH}?mode=ro", uri=True) as db:
        row = db.execute("SELECT job_json FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if not row:
        raise SystemExit(f"No job {job_id} in {paths.DB_PATH}")
    job = json.loads(row[0])
    reqs, kinds = requirements(job)
    folder = REAL_CASES / name
    if folder.exists():
        raise SystemExit(f"{folder} already exists")
    folder.mkdir(parents=True)
    (folder / "job.json").write_text(json.dumps(job, indent=2, ensure_ascii=False), encoding="utf-8")
    case = {
        "resume": resume,
        "expected_score": None,
        "notes": f"from tracker job {job_id}",
        "labels": [{"kind": k, "requirement": r, "label": "?", "why": ""} for r, k in zip(reqs, kinds)],
    }
    (folder / "case.json").write_text(json.dumps(case, indent=2, ensure_ascii=False), encoding="utf-8")
    return folder


# ---------------------------------------------------------------------------
# running
# ---------------------------------------------------------------------------

def run_once(case: dict) -> dict:
    """Step 2 as the app runs it, on one resume. Returns the raw answer + cost."""
    from langchain_core.callbacks import get_usage_metadata_callback

    from job_agent.fit import pick_best_resume
    from job_agent.models import JobPosting

    job = JobPosting(**case["job"])
    start = time.perf_counter()
    with get_usage_metadata_callback() as usage:
        best, _ = pick_best_resume(job, {"resume": case["resume"]})
    tokens = {"input": 0, "output": 0}
    for counts in usage.usage_metadata.values():
        tokens["input"] += counts.get("input_tokens", 0)
        tokens["output"] += counts.get("output_tokens", 0)
    return {"fit": best.model_dump(), "seconds": round(time.perf_counter() - start, 1), "tokens": tokens}


def short(text: str, n: int = 48) -> str:
    return text if len(text) <= n else text[: n - 1] + "..."


def run_cases(cases: list[dict], runs: int, on_case=None) -> dict:
    settings = {key: os.getenv(key, default) for key, default in (
        ("LLM_PROVIDER", "ollama"), ("LLM_MODEL", "qwen3:8b"), ("LLM_TEMPERATURE", "0.2"),
        ("OLLAMA_NUM_CTX", "16384"), ("JUDGE_EVIDENCE", "true"), ("FIT_DETAIL", "short"))}
    report = {"started": datetime.now().isoformat(timespec="seconds"), "settings": settings, "cases": {}}
    for case in cases:
        print(f"\n=== {case['name']}: {len(case['reqs'])} requirements, {runs} run(s)")
        results = []
        for n in range(1, runs + 1):
            try:
                raw = run_once(case)
            except Exception as e:  # one bad run shouldn't lose the others
                print(f"  run {n}: FAILED {type(e).__name__}: {e}")
                results.append({"error": f"{type(e).__name__}: {e}"})
                continue
            pred = predict(raw["fit"], case["reqs"])
            res = compare(pred, case["labels"], raw["fit"]["fit_score"])
            print(f"  run {n}: score {res.score:3d} | accuracy {res.accuracy:.0%} | "
                  f"{len(res.false_gaps)} false gaps | {len(res.false_matches)} false matches | "
                  f"{len(res.proven_as_partial)} proven->partial | "
                  f"{len(res.not_seen)} not seen | {raw['seconds']} s")
            results.append({**raw, "status": pred.status, "invented_gaps": pred.invented_gaps,
                            "judge_rejected": pred.judge_rejected, "metrics": vars(res)})
        report["cases"][case["name"]] = summarize(case, results)
        print_case(case, report["cases"][case["name"]])
        report["total"] = total(report["cases"])
        if on_case:
            on_case(report)  # saved after every case: a crash loses one case at most
    report["total"] = total(report["cases"])
    print_total(report["total"])
    return report


def summarize(case: dict, results: list[dict]) -> dict:
    ok = [r for r in results if "metrics" in r]
    m = [r["metrics"] for r in ok]
    count = lambda key, i: sum(1 for x in m if i in x.get(key, []))  # noqa: E731  runs where i is wrong
    return {
        "requirements": case["reqs"], "kinds": case["kinds"], "labels": case["labels"],
        "expected": case["expected"], "label_score": label_score(case["labels"], case["kinds"]),
        "runs": results, "failed_runs": len(results) - len(ok),
        "scores": [x["score"] for x in m],
        "accuracy": statistics.mean(x["correct"] / x["hard"] for x in m) if m and m[0]["hard"] else None,
        "false_gaps": {i: count("false_gaps", i) for i in range(len(case["reqs"])) if count("false_gaps", i)},
        "false_matches": {i: count("false_matches", i) for i in range(len(case["reqs"])) if count("false_matches", i)},
        "not_seen": {i: count("not_seen", i) for i in range(len(case["reqs"])) if count("not_seen", i)},
        "proven_as_partial": {i: count("proven_as_partial", i) for i in range(len(case["reqs"]))
                              if count("proven_as_partial", i)},
        "invented_gaps": sum(x["invented_gaps"] for x in m),
        "stability": stability([r["status"] for r in ok]),
        "seconds": statistics.mean(r["seconds"] for r in ok) if ok else None,
        "output_tokens": statistics.mean(r["tokens"]["output"] for r in ok) if ok else None,
        "proven_labels": case["labels"].count("proven"), "missing_labels": case["labels"].count("missing"),
    }


def total(cases: dict) -> dict:
    s = [c for c in cases.values() if c["scores"]]
    runs = sum(len(c["scores"]) for c in s)
    return {
        "cases": len(s), "runs": runs,
        "accuracy": statistics.mean(c["accuracy"] for c in s if c["accuracy"] is not None) if s else None,
        # Out of every (labelled proven requirement x run): how often called a gap / not seen.
        "false_gap_rate": (sum(sum(c["false_gaps"].values()) for c in s)
                           / max(1, sum(c["proven_labels"] * len(c["scores"]) for c in s))),
        "false_match_rate": (sum(sum(c["false_matches"].values()) for c in s)
                             / max(1, sum(c["missing_labels"] * len(c["scores"]) for c in s))),
        "score_error": (statistics.mean(abs(statistics.mean(c["scores"]) - c["label_score"]) for c in s)
                        if s else None),
        "stability": statistics.mean(c["stability"] for c in s) if s else None,
        "seconds_per_run": statistics.mean(c["seconds"] for c in s) if s else None,
        "output_tokens_per_run": statistics.mean(c["output_tokens"] for c in s) if s else None,
    }


def print_case(case: dict, c: dict) -> None:
    if not c["scores"]:
        print("  no successful runs")
        return
    expected = f" | you expect {c['expected'][0]}-{c['expected'][1]}" if c["expected"] else ""
    print(f"  scores {c['scores']} | the labels would give {c['label_score']}{expected}")
    print(f"  accuracy {c['accuracy']:.0%} | same answer every run: {c['stability']:.0%} | "
          f"invented gaps {c['invented_gaps']}")
    runs = len(c["scores"])
    for key, title in (("false_gaps", "proven, but not counted (gap or never scored)"), ("false_matches", "called proven, but missing"),
                       ("proven_as_partial", "proven, but called partial"),
                       ("not_seen", "never scored (skipped / quote failed)")):
        for i, n in c[key].items():
            print(f"    {title}: {short(c['requirements'][i])} ({n}/{runs})")


def print_total(t: dict) -> None:
    if not t["runs"]:
        print("\nNo successful runs.")
        return
    print(f"\n=== TOTAL: {t['cases']} cases, {t['runs']} runs")
    print(f"  accuracy {t['accuracy']:.0%} | false gaps {t['false_gap_rate']:.0%} of proven skills | "
          f"false matches {t['false_match_rate']:.0%} of missing skills")
    print(f"  score off by {t['score_error']:.0f} points on average | stability {t['stability']:.0%} | "
          f"{t['seconds_per_run']:.0f} s and {t['output_tokens_per_run']:.0f} output tokens per run")


def results_path(report: dict) -> Path:
    model = report["settings"]["LLM_MODEL"].replace(":", "-").replace("/", "-")
    stamp = report["started"].replace(":", "").replace("-", "").replace("T", "-")[:13]
    return RESULTS / f"{stamp}_{model}.json"


def save(report: dict) -> Path:
    RESULTS.mkdir(parents=True, exist_ok=True)
    path = results_path(report)  # the same file for the whole run (saved after each case)
    path.write_text(json.dumps(report, indent=1, ensure_ascii=False), encoding="utf-8")
    return path


def compare_files(old: Path, new: Path) -> None:
    a, b = (json.loads(p.read_text(encoding="utf-8")) for p in (old, new))
    print(f"{'':28} {'old':>22} {'new':>22}")
    for name in sorted(set(a["cases"]) | set(b["cases"])):
        row = []
        for r in (a, b):
            c = r["cases"].get(name)
            row.append("-" if not c or not c["scores"] else
                       f"{statistics.mean(c['scores']):.0f} pts | {c['accuracy']:.0%} acc")
        print(f"{short(name, 28):28} {row[0]:>22} {row[1]:>22}")
    for key, fmt in (("accuracy", "{:.0%}"), ("false_gap_rate", "{:.0%}"), ("false_match_rate", "{:.0%}"),
                     ("score_error", "{:.1f}"), ("stability", "{:.0%}"), ("seconds_per_run", "{:.0f} s"),
                     ("output_tokens_per_run", "{:.0f}")):
        va, vb = a["total"].get(key), b["total"].get(key)
        show = lambda v: "-" if v is None else fmt.format(v)  # noqa: E731
        print(f"{key:28} {show(va):>22} {show(vb):>22}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.fit", description=__doc__.split("\n\n")[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list", help="the cases found")
    p_new = sub.add_parser("new", help="a case from a tracked job, labels blank")
    p_new.add_argument("name")
    p_new.add_argument("--job", type=int, required=True, help="job id in the repo tracker")
    p_new.add_argument("--resume", required=True, help='"data:<file.pdf>" or a path inside the case')
    p_run = sub.add_parser("run", help="run the cases")
    p_run.add_argument("--case", action="append", help="only this case (repeatable)")
    p_run.add_argument("--runs", type=int, default=3)
    p_run.add_argument("--model", help="e.g. qwen3:14b (default: LLM_MODEL from .env)")
    p_run.add_argument("--no-judge", action="store_true", help="turn the evidence judge off")
    p_cmp = sub.add_parser("compare", help="two results files side by side")
    p_cmp.add_argument("old", type=Path)
    p_cmp.add_argument("new", type=Path)
    args = parser.parse_args(argv)

    if args.cmd == "list":
        for name, d in case_dirs().items():
            print(f"{name:32} {d}")
        return 0
    if args.cmd == "new":
        print(f"Created {new_case(args.name, args.job, args.resume)}: fill in every label "
              f"({', '.join(LABELS)}) in case.json")
        return 0
    if args.cmd == "compare":
        compare_files(args.old, args.new)
        return 0

    if args.model:
        os.environ["LLM_MODEL"] = args.model
    if args.no_judge:
        os.environ["JUDGE_EVIDENCE"] = "false"
    found = case_dirs()
    names = args.case or list(found)
    unknown = [n for n in names if n not in found]
    if unknown:
        raise SystemExit(f"Unknown case(s): {', '.join(unknown)}. Known: {', '.join(found)}")
    from job_agent.llm import llm_status

    ok, message = llm_status()
    if not ok:
        raise SystemExit(message)
    report = run_cases([load_case(found[n]) for n in names], args.runs, on_case=save)
    print(f"\nSaved {save(report)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
