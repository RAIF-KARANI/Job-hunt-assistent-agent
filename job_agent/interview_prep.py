"""
16f: the interview prep sheet.

By the time a company calls, its posting is usually gone, and with it what
you'd prepare from. The tracker already holds everything about the job:
what they asked for, which of it your resume proves (with the exact quote),
what it doesn't, the company research, the cover note you sent, your own
notes, and (since 16e) the posting's text. This file puts it on one page.

NO LLM here, on purpose: the sheet is for a real interview, so every line
is copied from what was saved and checked when the job was analyzed.
Nothing is written fresh, so nothing can be invented. Tests:
tests/test_interview_prep.py.

    build_sheet(job, cover_note)  -> a dict of sections (the screen)
    as_text(sheet)                -> plain text (export: .txt, .docx, .pdf)
"""

from job_agent import posting_archive

_EMPTY = ("", "not specified", "not applicable", "unknown", "none", "n/a")


def _said(value) -> str:
    """A saved value, or "" when it is one of the model's ways to say nothing."""
    text = str(value or "").strip()
    return "" if text.lower() in _EMPTY else text


def build_sheet(job: dict, cover_note: str | None = None) -> dict:
    """`job`: tracker.get_job() (the row plus `job`, `best_match`,
    `company_brief`). `cover_note`: the latest approved note's text."""
    posting, match, brief = job["job"], job["best_match"], job.get("company_brief")
    analysis = match.analysis
    reasons = analysis.gap_reasons or {}

    facts = [("Location", _said(posting.location)), ("Type", _said(posting.employment_type)),
             ("Level", _said(posting.seniority)), ("Salary", _said(posting.salary)),
             ("Interview", _said(job.get("interview_at")).replace("T", " ")), ("Contact", _said(job.get("contact")))]

    proven = [{"requirement": m.requirement, "evidence": m.resume_evidence} for m in analysis.matching_skills]
    partial = [{"requirement": m.requirement, "evidence": m.resume_evidence} for m in analysis.partial_skills]
    gaps = [{"requirement": gap, "reason": _said(reasons.get(gap))} for gap in analysis.missing_skills]

    company = None
    if brief is not None:
        company = {
            "what_they_do": _said(brief.what_they_do), "size_and_stage": _said(brief.size_and_stage),
            "products": [p for p in brief.products if _said(p)],
            "recent_news": [n for n in brief.recent_news if _said(n)],
            "culture_and_values": [c for c in brief.culture_and_values if _said(c)],
            "hooks": [h for h in brief.cover_note_hooks if _said(h)],
            "sources": list(brief.sources),
        }

    return {
        "job_id": job["id"],
        "title": posting.title, "company": posting.company,
        "facts": [{"label": label, "value": value} for label, value in facts if value],
        "summary": _said(posting.summary),
        "responsibilities": list(posting.responsibilities),
        "required": list(posting.required_skills), "nice_to_have": list(posting.nice_to_have_skills),
        "resume": match.resume_name, "fit_score": match.fit_score, "verdict": _said(analysis.verdict),
        "proven": proven, "partial": partial, "gaps": gaps,
        "talking_points": [t for t in analysis.talking_points if _said(t)],
        "research": company,  # None when no reliable research was found
        "cover_note": (cover_note or "").strip() or None,
        "notes": _said(job.get("notes")) or None,
        "description": posting_archive.readable(job.get("posting_text")) or None,
        "url": job.get("url"),
    }


def sheet_for(job: dict, cover_note: str | None = None) -> dict:
    """The sheet plus its plain-text form (for "Copy all")."""
    sheet = build_sheet(job, cover_note)
    return {**sheet, "text": as_text(sheet)}


def _section(title: str, lines: list[str], detail: str = "") -> str:
    """A heading in capitals (plain text has no bold), then its lines. `detail`
    stays as written: a file name in capitals is hard to read."""
    return "\n".join([title.upper() + detail, *lines]) if lines else ""


def as_text(sheet: dict) -> str:
    """The sheet as plain text. Blank lines separate the sections (the
    export turns each into a paragraph)."""
    head = f"Interview prep: {sheet['title']} at {sheet['company']}"
    facts = [f"{f['label']}: {f['value']}" for f in sheet["facts"]]
    company = sheet["research"] or {}
    parts = [
        "\n".join([head, *facts]),
        _section("The role", [sheet["summary"]] if sheet["summary"] else []),
        _section("What you would do", [f"- {r}" for r in sheet["responsibilities"]]),
        _section("What they ask for", [f"- {r}" for r in sheet["required"]]
                 + [f"- {r} (nice to have)" for r in sheet["nice_to_have"]]),
        _section("What your resume proves",
                 [f"- {m['requirement']}\n  Your resume says: \"{m['evidence']}\"" for m in sheet["proven"]],
                 detail=f" ({sheet['resume']}, fit {sheet['fit_score']})"),
        _section("Shown only in part",
                 [f"- {m['requirement']}\n  Closest in your resume: \"{m['evidence']}\"" for m in sheet["partial"]]),
        _section("Not in your resume: decide what you will say",
                 [f"- {g['requirement']}" + (f"\n  Why it counts as a gap: {g['reason']}" if g["reason"] else "")
                  for g in sheet["gaps"]]),
        _section("Worth bringing up", [f"- {t}" for t in sheet["talking_points"]]),
        _section("The company", [line for line in (
            company.get("what_they_do"),
            f"Size and stage: {company['size_and_stage']}" if company.get("size_and_stage") else "",
            *[f"- Product: {p}" for p in company.get("products", [])],
            *[f"- News: {n}" for n in company.get("recent_news", [])],
            *[f"- Culture: {c}" for c in company.get("culture_and_values", [])],
            *[f"- Source: {s}" for s in company.get("sources", [])],
        ) if line]),
        _section("The cover note you approved", [sheet["cover_note"].replace("\n\n", "\n")] if sheet["cover_note"] else []),
        _section("Your notes", [sheet["notes"]] if sheet["notes"] else []),
        _section("The job description, as saved", [sheet["description"].replace("\n\n", "\n")] if sheet["description"] else []),
    ]
    return "\n\n".join(p for p in parts if p)
