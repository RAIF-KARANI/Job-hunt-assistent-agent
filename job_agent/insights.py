"""
19c (E7): what your own tracker says about your job search.

NO LLM, offline, plain counting. The words mean:

    applied      the job is (or was) Applied, Interviewing or Offer. A job's
                 history (status_changes, since 19c) also counts: Rejected
                 after Applied is still an application.
    interview    the job reached Interviewing or Offer
    rate         interviews / applications, per group
    answer       the first change after Applied (to Interviewing, Offer or
                 Rejected); its time is only known when both changes were
                 recorded, so only for jobs applied to since 19c

Honest by design:
    - a group with fewer than MIN_GROUP applications shows its counts but
      no rate ("too few to say"): 1 of 2 is not "50 %";
    - a Rejected job with no history (from before 19c) may have been
      rejected by them or dropped by you before applying: it is counted
      as "unknown", never guessed into either.

Tests: tests/test_insights.py.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from statistics import median
from urllib.parse import urlparse

from job_agent import tracker

MIN_GROUP = 5
APPLIED = ("applied", "interviewing", "offer")
INTERVIEW = ("interviewing", "offer")
ANSWERS = ("interviewing", "offer", "rejected")
FIT_BANDS = (("75 and up", 75), ("60 to 74", 60), ("under 60", 0))  # 75+: Ready to apply's bar (16i)

# Job sites by the end of their address, in your words.
SITES = {
    "linkedin.com": "LinkedIn", "indeed.com": "Indeed", "glassdoor.com": "Glassdoor", "bayt.com": "Bayt",
    "naukrigulf.com": "Naukrigulf", "gulftalent.com": "GulfTalent", "wellfound.com": "Wellfound",
    "greenhouse.io": "Greenhouse", "lever.co": "Lever",
    "myworkdayjobs.com": "Workday", "ashbyhq.com": "Ashby",
    "smartrecruiters.com": "SmartRecruiters", "workable.com": "Workable",
}


def site(url: str | None) -> str:
    """'https://www.linkedin.com/jobs/view/1' -> 'LinkedIn'; other sites by their domain."""
    host = (urlparse(url or "").hostname or "").lower()
    if not host:
        return "Pasted job text"
    for end, name in SITES.items():
        if host == end or host.endswith("." + end):
            return name
    parts = host.removeprefix("www.").split(".")
    # "jobs.acme.co.uk" -> "acme.co.uk"; "careers.acme.com" -> "acme.com"
    keep = 3 if len(parts) >= 3 and len(parts[-1]) == 2 and parts[-2] in ("co", "com", "ac", "org", "net", "gov") else 2
    return ".".join(parts[-keep:])


def fit_band(score) -> str:
    if score is None:
        return "no score"
    return next(name for name, low in FIT_BANDS if score >= low)


def _days(a: str, b: str) -> float:
    fmt = "%Y-%m-%d %H:%M:%S"
    return (datetime.strptime(b, fmt) - datetime.strptime(a, fmt)).total_seconds() / 86400


def _job_facts(job: dict, history: list[dict]) -> dict:
    """What one job tells: applied? interview? offer? when? (None = unknown)."""
    seen = {job["status"], *(h["to_status"] for h in history)}
    applied = bool(seen & set(APPLIED))
    if job["status"] == "rejected" and not applied:
        applied = None if not history else False  # no history: we can't know
    applied_at = next((h["changed_at"] for h in history if h["to_status"] == "applied"), None)
    answer = None
    if applied_at:
        answer = next((h for h in history if h["changed_at"] >= applied_at and h["to_status"] in ANSWERS
                       and h["from_status"] in ("applied",)), None)
    stage = None  # where a rejected job stopped
    if job["status"] == "rejected":
        before = [h["from_status"] for h in history if h["to_status"] == "rejected"]
        stage = before[-1] if before else None
    return {"applied": applied, "interview": bool(seen & set(INTERVIEW)), "offer": "offer" in seen,
            "applied_at": applied_at, "answer": answer, "rejected_from": stage}


def _group(rows: list[dict], key) -> list[dict]:
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[key(r)].append(r)
    out = []
    for name, members in groups.items():
        n, hits = len(members), sum(1 for m in members if m["interview"])
        out.append({"name": name, "applications": n, "interviews": hits,
                    "offers": sum(1 for m in members if m["offer"]),
                    "rate": round(hits / n, 3) if n >= MIN_GROUP else None})
    # Most applications first: the groups that say the most lead.
    return sorted(out, key=lambda g: (-g["applications"], g["name"]))


def compute(jobs: list[dict], changes: list[dict], now: datetime | None = None) -> dict:
    """Insights from job rows (id, url, status, fit_score, best_resume) and
    their status changes. Pure: tests pass both in."""
    now = now or datetime.now(timezone.utc).replace(tzinfo=None)  # the tracker stores UTC
    history: dict[int, list[dict]] = defaultdict(list)
    for c in changes:
        history[c["job_id"]].append(c)
    facts = [{**j, **_job_facts(j, history[j["id"]])} for j in jobs]
    applied = [f for f in facts if f["applied"]]
    unknown = [f for f in facts if f["applied"] is None]

    waits = [_days(f["applied_at"], f["answer"]["changed_at"]) for f in applied if f["answer"]]
    waiting = [f for f in applied if f["applied_at"] and not f["answer"] and f["status"] == "applied"]
    now_s = now.strftime("%Y-%m-%d %H:%M:%S")

    stages = {s: sum(1 for f in facts if f["status"] == s) for s in tracker.STATUSES}
    rejected = {"after applying": 0, "after an interview": 0, "before applying": 0, "unknown": 0}
    for f in facts:
        if f["status"] != "rejected":
            continue
        if f["rejected_from"] in INTERVIEW:
            rejected["after an interview"] += 1
        elif f["rejected_from"] == "applied" or (f["rejected_from"] is None and f["applied"]):
            rejected["after applying"] += 1
        elif f["applied"] is False:
            rejected["before applying"] += 1
        else:
            rejected["unknown"] += 1

    interviews = sum(1 for f in applied if f["interview"])
    return {
        "jobs": len(facts),
        "applications": len(applied),
        "interviews": interviews,
        "offers": sum(1 for f in applied if f["offer"]),
        "rate": round(interviews / len(applied), 3) if len(applied) >= MIN_GROUP else None,
        "min_group": MIN_GROUP,
        "unknown": len(unknown),
        "by_resume": _group(applied, lambda f: f.get("best_resume") or "no resume"),
        "by_site": _group(applied, lambda f: site(f.get("url"))),
        "by_fit": sorted(_group(applied, lambda f: fit_band(f.get("fit_score"))),
                         key=lambda g: [b for b, _ in FIT_BANDS].index(g["name"]) if g["name"] != "no score" else 9),
        "answer_days": {"median": round(median(waits), 1) if waits else None, "count": len(waits),
                        "fastest": round(min(waits), 1) if waits else None,
                        "slowest": round(max(waits), 1) if waits else None},
        "waiting": {"count": len(waiting),
                    "longest_days": round(max(_days(f["applied_at"], now_s) for f in waiting), 1) if waiting else None},
        "stages": stages,
        "rejected": rejected,
        "recorded_since": min((c["changed_at"] for c in changes), default=None),
    }


def from_tracker() -> dict:
    tracker.init_db()
    with tracker._db() as conn:
        jobs = [dict(r) for r in conn.execute("SELECT id, url, status, fit_score, best_resume FROM jobs")]
    return compute(jobs, tracker.status_changes())
