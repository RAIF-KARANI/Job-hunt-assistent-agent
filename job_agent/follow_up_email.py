"""
16g: a follow-up email, written only when you ask for one.

The follow-up reminder (14e) says "a short, polite email often gets an
answer". This file writes that email for one job. It is never written by
itself: a draft made on the reminder's date would be wasted on the jobs you
mean to ignore (D43). You press a button, read it, change it, send it.

Who writes what:
    code   the subject, the greeting, the opening (role, company, the date
           you applied), the question about next steps, the sign-off
    model  ONE sentence: a strength of yours, restated from the cover note
           they already have

Why so little for the model: the first version let it write the whole email
(measured on 6 real jobs, 15 Nov 2026). It left the company's name out of 2,
wrote "I'm applying ... on 13 November" for a job applied to days ago, and
once claimed an installer "aligns well with your focus on seamless payment
experiences". Dates and names are facts: code states them exactly.

The model's sentence is checked by code (one sentence, no number that isn't
in the cover note, no claim about fitting their business). If it fails
twice, or the model isn't ready, the email simply goes without it: you
always get an email to start from.

Tests: tests/test_follow_up_email.py (no model: a fake one).
"""

import re
from datetime import datetime, timezone

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from job_agent.cover_note import unverified_numbers
from job_agent.llm import structured_llm

MAX_STRENGTH_WORDS = 45
_FORMAT = "%Y-%m-%d %H:%M:%S"  # SQLite's CURRENT_TIMESTAMP, in UTC
# The model may state a strength, not judge how well it suits the employer.
_FIT_CLAIMS = re.compile(r"\b(align\w*|match\w*|fit\w*|suit\w*|perfect\w*|ideal\w*|your (focus|mission|team|company|needs))\b", re.I)


class Strength(BaseModel):
    """Structured output: only the one sentence, no chatter around it."""

    sentence: str = Field(description="ONE sentence in the first person, under 40 words, stating one "
                                      "achievement from the source with its facts and numbers unchanged.")


WRITER_PROMPT = """You help write a follow-up email for a job application. The rest of the email is already
written; you write ONE sentence for it, in the FIRST PERSON as the candidate.
Rules:
- One sentence, under 40 words, that restates ONE achievement from the SOURCE below: the one most relevant
  to the ROLE. Start with "I" (for example "I built ...", "I cut ...").
- Keep its facts and numbers exactly as the source has them. Add nothing the source doesn't say.
- State it as a plain fact about your work. Do NOT say it matches, fits, suits or aligns with the role or
  the company, and don't mention the company at all.
- No greeting, no sign-off, no placeholders like [Company]."""


def _local_day(utc_text: str | None) -> str:
    """ "2026-11-12 08:30:00" (UTC) -> "12 November" in this PC's time zone; "" if unknown."""
    try:
        when = datetime.strptime(utc_text or "", _FORMAT).replace(tzinfo=timezone.utc).astimezone()
    except ValueError:
        return ""
    return f"{when.day} {when.strftime('%B')}"


def candidate_name(cover_note: str | None) -> str:
    """The name the cover note signs off with: its last line, if that looks
    like a name (2-4 capitalised words). "" when there is no such line."""
    lines = [line.strip() for line in (cover_note or "").splitlines() if line.strip()]
    if not lines:
        return ""

    def a_name(text: str) -> str:
        text = text.strip().rstrip(".")
        words = text.split()
        ok = 1 < len(words) <= 4 and all(re.fullmatch(r"[^\W\d_][^\W\d_.'-]*", w) and w[0].isupper() for w in words)
        return text if ok and words[0].lower() not in ("best", "kind", "sincerely", "thank", "regards", "warm", "yours") else ""

    # "…\nRaif Karani", or (most saved notes) "…to your mission. Raif Karani"
    return a_name(lines[-1]) or a_name(re.split(r"[.!?]\s+", lines[-1])[-1])


def facts(job: dict, cover_note: str | None) -> dict:
    """What the email may say. `job`: tracker.get_job(); `cover_note`: the
    latest approved note's text (None if there is none)."""
    posting, match = job["job"], job["best_match"]
    proven = [f"{m.requirement}: {m.resume_evidence}" for m in match.analysis.matching_skills[:4]]
    return {
        "title": posting.title, "company": posting.company,
        "after_interview": job["status"] == "interviewing",
        # the status change is when you applied (or moved it to Interviewing)
        "since": _local_day(job.get("updated_at")),
        "again": bool(job.get("followed_up_at")),
        "name": candidate_name(cover_note),
        # the cover note is what they have already read from you; without one, what the resume proves
        "source": (cover_note or "").strip() or "\n".join(proven),
    }


def subject(f: dict) -> str:
    return f"Following up: {f['title']} " + ("interview" if f["after_interview"] else "application")


def compose(f: dict, strength: str = "") -> str:
    """The email. Everything but `strength` is written here, from the facts."""
    if f["after_interview"]:
        opening = (f"Thank you for speaking with me about the {f['title']} role at {f['company']}. "
                   "I enjoyed the conversation and remain very interested in the position.")
    else:
        when = f", which I sent on {f['since']}" if f["since"] else ""
        again = "again " if f["again"] else ""
        opening = f"I am following up {again}on my application for the {f['title']} role at {f['company']}{when}."
        if strength:
            opening += " " + strength
        else:
            opening += " I remain very interested in the position."
    lines = ["Dear Hiring Team,", "", opening, "",
             "Is there an update, or a timeline for the next steps? I am happy to send anything else you need.", "",
             "Best regards,"]
    if f["name"]:
        lines.append(f["name"])
    return "\n".join(lines)


def wants_strength(f: dict) -> bool:
    """Only the first follow-up after applying restates a strength. A second
    one would repeat it, and after an interview they have heard it from you."""
    return bool(f["source"]) and not f["after_interview"] and not f["again"]


def problems(sentence: str, f: dict) -> list[str]:
    """Why the model's sentence can't go into the email. Empty = usable."""
    found = []
    words = len(sentence.split())
    if not 5 <= words <= MAX_STRENGTH_WORDS:
        found.append(f"it has {words} words")
    if len(re.findall(r"[.!?](?:\s|$)", sentence.strip())) > 1 or "\n" in sentence.strip():
        found.append("it is more than one sentence")
    if re.search(r"\[[^\]]{1,40}\]", sentence) or "<" in sentence:
        found.append("it has a placeholder")
    if _FIT_CLAIMS.search(sentence):
        found.append("it claims to fit their business")
    strange = unverified_numbers(sentence, f["source"])
    if strange:
        found.append(f"it has a number that isn't in your cover note ({', '.join(strange)})")
    if not sentence.strip().lower().startswith(("i ", "i'", "i’")):
        found.append("it isn't about your own work")
    return found


def _ask_model(f: dict) -> str:
    details = f"ROLE: {f['title']}\n\nSOURCE (the cover note they already have, or what the resume proves):\n{f['source']}"
    answer = structured_llm(Strength, max_tokens=300).invoke([SystemMessage(content=WRITER_PROMPT), HumanMessage(content=details)])
    return " ".join(answer.sentence.split())  # one line


def draft(job: dict, cover_note: str | None, use_model: bool = True, attempts: int = 2,
          no_model_reason: str = "The AI model isn't ready") -> dict:
    """The follow-up email for one job: {"subject", "text", "strength" (the
    model's sentence, or ""), "note" (why there is none, in plain words),
    "warnings" (for you to check before sending)}."""
    f = facts(job, cover_note)
    strength, note = "", ""
    if not wants_strength(f):
        note = ("After an interview the email only thanks them and asks about next steps." if f["after_interview"]
                else "A second follow-up is kept short: it doesn't repeat your strengths." if f["again"]
                else "There is no cover note or proven skill to restate.")
    elif not use_model:
        note = f"{no_model_reason.rstrip('.')}, so the email has no sentence about your work. Add one if you like."
    else:
        for _ in range(attempts):
            try:
                sentence = _ask_model(f)
            except Exception as e:  # the model is off, was stopped, or answered nonsense
                note = f"The AI model couldn't write its sentence ({str(e)[:120]}). Add one about your work if you like."
                break
            found = problems(sentence, f)
            if not found:
                strength, note = sentence, ""
                break
            note = "The AI's sentence about your work wasn't usable (" + "; ".join(found) + "), so it was left out."
    warnings = [] if f["name"] else ["Add your name at the end: there was no cover note to take it from."]
    return {"subject": subject(f), "text": compose(f, strength), "strength": strength, "note": note, "warnings": warnings}
