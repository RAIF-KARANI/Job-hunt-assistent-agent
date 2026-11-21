"""
19d (E7): resume tailoring. The model suggests changes to YOUR resume lines
for one job (before -> after, and the requirement each one shows); plain
code then checks every suggestion against the resume, the way the cover
note is checked (D43 kept the prep sheet code-only for the same reason: no
claim the resume doesn't show).

    1. SUGGEST (one LLM call)  edits = [{before, after, requirement, why}]
    2. CHECK (code), per edit; a failed edit is DROPPED, with the reason:
         - "before" must really be in the resume (the fit check's quote test)
         - "after" must differ from "before"
         - no number that "before" doesn't have (no new %, years, team sizes),
           and "about 40 s" doesn't become "within 40 s" (a stronger claim)
         - nothing of yours left out: every number and every named tool of
           "before" stays (19d measuring: the model "tightened" lines by
           cutting "reduced latency by 25%" and a list of five databases)
         - no skill from the job that the resume doesn't show anywhere
         - no new name-like term (a tool, product, employer, certificate):
           a capitalised word, or one with digits / + / # / a dot inside,
           that is in neither the resume nor "before". Except the job's own
           words for a requirement the fit check (and judge) already
           verified the resume shows: "RAG" for a verified "RAG pipelines"
    3. LOG (code)  how many were suggested and dropped, per model (Evals)

What the check can't see: a claim made of ordinary words ("led the team"
when you didn't). The screen says so; you read every edit before you copy.

The resume prompt (14g) stays: it is for another AI and sends nothing.
This uses the model in Settings, so with a cloud model the resume text goes
to it, as it does for the analysis (E7). Tests: tests/test_tailoring.py.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from job_agent import tracker
from job_agent.fit import _letters, _words, is_evidence_in_resume
from job_agent.models import JobPosting, ResumeMatch

MAX_EDITS = 6

PROMPT = """You help a job seeker adapt their OWN resume to one job.

Suggest up to {n} edits to existing resume lines. For each edit:
- "before": one line or bullet copied EXACTLY from the resume (word for word).
- "after": the same line rewritten so it shows a requirement of the job more clearly.
- "requirement": the job requirement it shows, in the job's words.
- "why": one short sentence.

RULES (most important)
1. Use ONLY what the "before" line already says. Never add a skill, tool, technology, employer, title, certificate, number, percentage, team size or result that is not in that line.
2. Keep every number, result and named tool of "before" in "after". You may move them.
3. Each "after" must bring in the JOB'S OWN WORDS for its requirement, for something the line really shows. Example: the job asks for "test automation" and the line says "900+ tests in CI" -> "Test automation: 900+ tests in CI, ...". Lead with what the job cares about.
4. An "after" that is the same as "before", or only swaps a word or a comma, is useless: leave that line out. Two real edits beat six cosmetic ones.
5. Keep words like "about", "around" or "up to" in front of a number exactly as they are.
6. Don't touch headings, dates, contact details, degree titles or plain skill lists. No first person, no buzzwords.
"""


class BulletEdit(BaseModel):
    before: str = Field(description="A line copied exactly from the resume")
    after: str = Field(description="The rewritten line")
    requirement: str = Field(description="The job requirement it shows")
    why: str = Field(description="One short sentence")


class Tailoring(BaseModel):
    edits: list[BulletEdit] = Field(description="Up to 6 edits to existing resume lines")


# ---------------------------------------------------------------------------
# 1. SUGGEST (LLM)
# ---------------------------------------------------------------------------


def suggest(job: JobPosting, match: ResumeMatch, resume_text: str) -> list[BulletEdit]:
    from job_agent.llm import call_with_quota_waits, structured_llm

    shown = "\n".join(f"- {m.requirement}: \"{m.resume_evidence}\"" for m in match.analysis.matching_skills)
    prompt = (f"=== JOB ===\n{job.title} at {job.company}\n"
              f"Required: {'; '.join(job.required_skills)}\nNice to have: {'; '.join(job.nice_to_have_skills)}\n"
              f"Responsibilities: {'; '.join(job.responsibilities)}\n\n"
              f"=== WHAT A CHECK FOUND THE RESUME SHOWS (requirement: quote) ===\n{shown or '(nothing yet)'}\n\n"
              f"=== RESUME ===\n{resume_text}\n=== END RESUME ===")
    result = call_with_quota_waits(lambda: structured_llm(Tailoring).invoke(
        [SystemMessage(content=PROMPT.format(n=MAX_EDITS)), HumanMessage(content=prompt)]))
    return list(result.edits)[:MAX_EDITS]


# ---------------------------------------------------------------------------
# 2. CHECK (code)
# ---------------------------------------------------------------------------

NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9+#./-]*[A-Za-z0-9+#]|[A-Za-z0-9]")


def _quoted(before: str, resume_text: str) -> bool:
    """Stricter than a fit quote: almost every word, or the letters in order."""
    words = _words(before)
    if not words:
        return False
    letters = _letters(before)
    if len(letters) >= 12 and letters in _letters(resume_text):
        return True
    known = set(_words(resume_text))
    return sum(w in known for w in words) / len(words) >= 0.9 and is_evidence_in_resume(before, resume_text)


def _name_like(after: str) -> list[str]:
    """Words that look like a name: a tool, product, employer, certificate."""
    out = []
    for i, m in enumerate(TOKEN.finditer(after)):
        w = m.group(0).rstrip(".-/")
        start = m.start() == 0 or after[:m.start()].rstrip().endswith((".", ":", ";", "•", "-", "–"))
        if any(c.isdigit() for c in w) or any(c in w for c in "+#") or "." in w.strip("."):
            out.append(w)
        elif w[:1].isupper() and not start and len(w) > 1:
            out.append(w)
        elif w.isupper() and len(w) > 1:  # "AWS" at the start of a line
            out.append(w)
    return out


def _known(word: str, *texts: str) -> bool:
    """A word one of the texts has, also as a part of a hyphenated word
    ("MVC-based": MVC) or a plural ("UIs": UI)."""
    parts = [p for p in re.split(r"[-/]", word) if p] or [word]
    # Only the name-like parts must be known: "MVC-based" needs MVC, not "based".
    named = [p for p in parts if p != p.lower() or any(c.isdigit() or c in "+#" for c in p)]
    parts = [p.lower() for p in (named or parts)]
    forms = lambda p: {p, p[:-1] if p.endswith("s") and len(p) > 2 else p, p[:-2] if p.endswith("es") and len(p) > 3 else p}
    return all(any(f in text for f in forms(p) for text in texts) for p in parts)


HEDGE = re.compile(r"\b(about|around|approximately|approx\.?|roughly|nearly|almost|up to|~)\s*(\d+(?:[.,]\d+)?)", re.I)


def _hedges_lost(before: str, after: str) -> list[str]:
    """"about 40" in before, but 40 without "about" in after."""
    kept = {n for _, n in HEDGE.findall(after)}
    return sorted({f"{h} {n}" for h, n in HEDGE.findall(before) if n not in kept and n in NUMBER.findall(after)})


def _skill_terms(job: JobPosting) -> list[str]:
    return [s for s in (*job.required_skills, *job.nice_to_have_skills) if _words(s)]


def problems(edit: BulletEdit, job: JobPosting, resume_text: str, verified: list[str] = ()) -> list[str]:
    """Why this edit can't be shown ([] = it passes). `verified`: the job's
    requirements the fit check found proven in the resume."""
    before, after = edit.before.strip(), edit.after.strip()
    if not before or not after:
        return ["empty"]
    if not _quoted(before, resume_text):
        return ["the “before” line isn't in your resume"]
    if _letters(before) == _letters(after):
        return ["no change"]
    found = []
    extra = sorted(set(NUMBER.findall(after)) - set(NUMBER.findall(before)))
    if extra:
        found.append(f"adds a number your line doesn't have ({', '.join(extra)})")
    resume_words, before_words = set(_words(resume_text)), set(_words(before))
    after_words = set(_words(after))
    for skill in _skill_terms(job):
        words = set(_words(skill))
        if words and words <= after_words and not words <= resume_words:
            found.append(f"adds “{skill}”, which your resume doesn't show")
    lost = _hedges_lost(before, after)
    if lost:
        found.append(f"makes “{lost[0]}” sound exact")
    gone = sorted(set(NUMBER.findall(before)) - set(NUMBER.findall(after)), key=before.find)
    if gone:
        found.append(f"leaves out your number{'s' if len(gone) > 1 else ''} {', '.join(gone)}")
    after_low = after.lower()
    dropped_names = [w for w in dict.fromkeys(_name_like(before)) if not any(c.isdigit() for c in w) and not _known(w, after_low)]
    if dropped_names:
        found.append(f"leaves out {', '.join('“' + w + '”' for w in dropped_names[:4])}{'…' if len(dropped_names) > 4 else ''}")
    resume_low, before_low = resume_text.lower(), before.lower()
    allowed = " ".join(verified).lower()  # the job's words for what the resume is proven to show
    new_names = [w for w in _name_like(after) if not _known(w, resume_low, before_low, allowed)]
    # A name the skill check already reported is said once.
    new_names = [w for w in new_names if not any(w.lower() in f.lower() for f in found)]
    if new_names:
        found.append(f"adds {', '.join('“' + w + '”' for w in dict.fromkeys(new_names))}, not in your resume")
    return found


def check(edits: list[BulletEdit], job: JobPosting, resume_text: str, verified: list[str] = ()) -> tuple[list[dict], list[dict]]:
    """(kept, dropped). Duplicates of the same "before" line keep the first."""
    kept, dropped, seen = [], [], set()
    for e in edits:
        why_not = problems(e, job, resume_text, verified)
        key = _letters(e.before)
        if not why_not and key in seen:
            why_not = ["the same line twice"]
        row = e.model_dump()
        if why_not:
            dropped.append({**row, "reasons": why_not})
        else:
            seen.add(key)
            kept.append(row)
    return kept, dropped


# ---------------------------------------------------------------------------
# 3. LOG (code) + the whole step
# ---------------------------------------------------------------------------

LOG_SCHEMA = """
CREATE TABLE IF NOT EXISTS tailoring_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id      INTEGER,
    model       TEXT,
    suggested   INTEGER NOT NULL,
    kept        INTEGER NOT NULL,
    reasons     TEXT,               -- the dropped edits' first reasons, one per line
    seconds     REAL,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
"""


def _log(job_id: int, model: str, suggested: int, kept: int, dropped: list[dict], seconds: float) -> None:
    tracker.init_db()
    with tracker._db() as conn:
        conn.executescript(LOG_SCHEMA)
        conn.execute("INSERT INTO tailoring_log (job_id, model, suggested, kept, reasons, seconds) VALUES (?, ?, ?, ?, ?, ?)",
                     (job_id, model, suggested, kept, "\n".join(d["reasons"][0] for d in dropped), round(seconds, 1)))


def reason_kind(reason: str) -> str:
    """A dropped edit's reason, grouped for Evals."""
    if reason.startswith("leaves out"):
        return "left out something of yours"
    if reason.startswith("makes"):
        return "made an estimate exact"
    if "number" in reason:
        return "added a number"
    if "isn't in your resume" in reason:
        return "changed your line"
    if reason.startswith("adds"):
        return "added a skill or name"
    return reason  # "no change", "the same line twice", "empty"


def stats(model: str | None = None) -> dict:
    """For Evals: suggestions made and dropped by the check, per model or all."""
    tracker.init_db()
    with tracker._db() as conn:
        conn.executescript(LOG_SCHEMA)
        where, args = ("WHERE model = ?", (model,)) if model else ("", ())
        row = conn.execute(f"SELECT COUNT(*) runs, COALESCE(SUM(suggested), 0) suggested, COALESCE(SUM(kept), 0) kept, "
                           f"AVG(seconds) seconds FROM tailoring_log {where}", args).fetchone()
        reasons = [r["reasons"] for r in conn.execute(f"SELECT reasons FROM tailoring_log {where}", args) if r["reasons"]]
    kinds: dict[str, int] = {}
    for line in "\n".join(reasons).splitlines():
        kind = reason_kind(line)
        kinds[kind] = kinds.get(kind, 0) + 1
    suggested, kept = row["suggested"], row["kept"]
    return {"runs": row["runs"], "suggested": suggested, "kept": kept, "dropped": suggested - kept,
            "drop_rate": round((suggested - kept) / suggested, 3) if suggested else None,
            "seconds": round(row["seconds"], 1) if row["seconds"] is not None else None, "reasons": kinds}


def tailor(job_id: int, resume_text: str, suggest_fn=suggest) -> dict:
    """Suggest, check, log. `suggest_fn`: tests pass a stand-in for the model."""
    import os
    import time

    job = tracker.get_job(int(job_id))
    if job is None:
        raise ValueError(f"No job with id {job_id}")
    posting, match = job["job"], job["best_match"]
    started = time.monotonic()
    edits = suggest_fn(posting, match, resume_text)
    verified = [m.requirement for m in match.analysis.matching_skills]
    kept, dropped = check(edits, posting, resume_text, verified)
    seconds = time.monotonic() - started
    model = os.getenv("LLM_MODEL", "")
    _log(int(job_id), model, len(edits), len(kept), dropped, seconds)
    return {"resume": match.resume_name, "model": model, "edits": kept, "dropped": dropped,
            "seconds": round(seconds, 1), "at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
