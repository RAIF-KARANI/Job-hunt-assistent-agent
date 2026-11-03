"""
Phase 2b: compare resumes against a job and pick the best one.

Design choice 1: "LLM judges, code decides."
    We could paste BOTH resumes into one prompt and ask "which is better?",
    but small local models often mix up details between two similar documents.
    Instead we score each resume in its own, focused LLM call, then plain
    Python picks the winner. Each call is simpler -> more reliable,
    and the final decision is transparent (you can see every score).

Design choice 2: "Don't trust, verify."
    LLMs sometimes claim skills the resume doesn't have (hallucination), or
    copy wording from the job posting. So for every matching skill the model
    must quote evidence from the resume, and code checks that quote really
    exists in the resume. Claims that fail the check are dropped.
"""

import os
import re

from langchain_core.messages import HumanMessage, SystemMessage

from job_agent.llm import structured_llm
from job_agent.models import (
    EvidenceReview,
    FitAnalysis,
    FitVerdict,
    JobPosting,
    RequirementCheck,
    RequirementReview,
    ResumeMatch,
    SkillJudgment,
    SkillMatch,
    TalkingPoints,
)

# 14c: how much the agent writes besides the facts. "short" never trims the
# matches and their quotes (the evidence checks and the score need them);
# it trims the talking points and the verdict.
DETAIL_LEVELS = ("short", "detailed")
TALKING_POINTS = {
    "short": "- talking_points: at most 3, each under 15 words.",
    "detailed": "- talking_points: 3-5, each a full sentence.",
}
VERDICT_LENGTH = {
    "short": "One sentence.",
    "detailed": "Two or three sentences: whether to apply, the strongest proof, "
    "and the gap worth addressing in the application.",
}


def detail_level() -> str:
    """The FIT_DETAIL setting; anything unknown counts as "short"."""
    level = os.getenv("FIT_DETAIL", "short").strip().lower()
    return level if level in DETAIL_LEVELS else "short"

# A quote counts as verified if this share of its words appear in the resume.
# 1.0 would demand a perfect copy; small models often change a word or two.
EVIDENCE_THRESHOLD = 0.8


def _words(text: str) -> list[str]:
    """Lowercase words/numbers, ignoring punctuation and tiny words.

    Dots are kept inside a word ("node.js", ".net", "1.2") but not at its end:
    "images." at the end of a resume sentence must match "images" in a quote.
    """
    words = (w.rstrip(".") for w in re.findall(r"[a-z0-9+#.]+", text.lower()))
    return [w for w in words if len(w) > 2]


def _letters(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def is_evidence_in_resume(evidence: str, resume_text: str) -> bool:
    """Plain-code fact check: does the quoted evidence really come from the resume?

    15c: PDFs often glue a heading to its text ("LanguagesEmbedded C/C++"), so
    the quote "Languages: Embedded C/C++" lost a word and failed. A quote whose
    letters and digits appear in the resume in the same order, ignoring
    spaces and punctuation, is a real quote too (F2)."""
    quote_words = _words(evidence)
    if not quote_words:
        return False
    resume_words = set(_words(resume_text))
    found = sum(1 for w in quote_words if w in resume_words)
    if found / len(quote_words) >= EVIDENCE_THRESHOLD:
        return True
    letters = _letters(evidence)
    return len(letters) >= 8 and letters in _letters(resume_text)


CHECK_PROMPT = """You check a candidate's RESUME against numbered job requirements.
For EACH requirement, answer:
- "proven": the resume clearly shows it. Projects, coursework, certificates and
  skill lists all count as evidence. Quote the phrase that shows it.
- "partial": the resume shows part of it, or something close but less (some of
  the listed tools; student projects where years of work experience are asked;
  a degree not finished yet). Quote the closest phrase.
- "missing": nothing in the resume shows it. Leave the quote empty.
Rules:
- Search the WHOLE resume (summary, experience, projects, skills, certificates)
  for each requirement before answering. Skills are often only in a list.
- The quote is copied word for word from the RESUME. The job posting is never evidence.
- Answer every requirement id exactly once."""

# 15b: how many requirements one call checks. An 8B model checking 19 at once
# got lazy (all nice-to-haves "missing", unread); a smaller batch keeps it
# reading. The resume comes first in the prompt, so Ollama reuses that part
# from the previous batch instead of reading it again.
BATCH_SIZE = int(os.getenv("FIT_BATCH_SIZE", "6"))  # env only for the evals


_FILLER = {"a", "an", "and", "as", "for", "in", "of", "on", "or", "the", "to", "with"}


def _tokens(text: str) -> set[str]:
    """Every word, short ones included ("C", "Go", "AI" matter here)."""
    return {w.rstrip(".") for w in re.findall(r"[a-z0-9+#.]+", text.lower())} - _FILLER - {""}


def _same_requirement(a: str, b: str) -> bool:
    """Near-identical wording (a posting repeating itself across its lists)."""
    wa, wb = _tokens(a), _tokens(b)
    return bool(wa and wb) and len(wa & wb) / max(len(wa), len(wb)) >= 0.8


def job_requirements(job: JobPosting) -> list[tuple[str, str]]:
    """The job's requirements as (text, "required" | "nice"), in order, with
    repeats dropped (the first one wins, so a required skill stays required)."""
    kept: list[tuple[str, str]] = []
    for kind, items in (("required", job.required_skills), ("nice", job.nice_to_have_skills)):
        for text in items:
            text = text.strip()
            if text and not any(_same_requirement(text, seen) for seen, _ in kept):
                kept.append((text, kind))
    return kept


def check_requirements(job: JobPosting, resume_text: str, ids: list[int] | None = None,
                       notes: dict[int, str] | None = None) -> list[RequirementCheck]:
    """One answer per requirement, in the job's order (several small calls).
    15c: `ids` + `notes` ask again about some of them, each with a note
    (a second look)."""
    reqs = job_requirements(job)
    ids = list(range(len(reqs))) if ids is None else list(ids)
    notes = notes or {}
    header = (f"=== RESUME ===\n{resume_text}\n=== END RESUME ===\n\n"
              f"=== JOB ===\n{job.title} at {job.company} (seniority: {job.seniority})\n\n")
    llm = structured_llm(RequirementReview)
    answers: dict[int, RequirementCheck] = {}

    def ask(batch: list[int]) -> None:
        listed = "\n".join(f"{i}. {reqs[i][0]}" + (f"\n   Note: {notes[i]}" if i in notes else "")
                           for i in batch)
        review = llm.invoke([SystemMessage(content=CHECK_PROMPT),
                             HumanMessage(content=f"{header}=== REQUIREMENTS TO CHECK ===\n{listed}")])
        for check in review.checks:
            if check.id in batch and check.id not in answers:
                answers[check.id] = check

    for start in range(0, len(ids), BATCH_SIZE):
        batch = ids[start:start + BATCH_SIZE]
        ask(batch)
        unanswered = [i for i in batch if i not in answers]
        if unanswered:
            ask(unanswered)  # once more, just the ones it skipped
    return [answers.get(i) or RequirementCheck(id=i, status="missing", resume_evidence="",
                                               reason="the AI gave no answer for it")
            for i in ids]


# 15c: words that say nothing about WHICH skill a requirement is about. The
# rest ("OpenCV", "SQLite", "C") are its key terms.
_GENERIC = {
    "ability", "applications", "application", "basic", "building", "build", "concepts", "degree",
    "design", "develop", "developing", "development", "engineering", "environment", "environments",
    "equivalent", "etc", "experience", "exposure", "familiarity", "field", "good", "hands",
    "including", "knowledge", "least", "like", "minimum", "plus", "preferred", "proficiency",
    "programming", "related", "skill", "skills", "solid", "strong", "such", "systems", "system",
    "tools", "understanding", "use", "using", "work", "working", "year", "years", "e.g", "i.e",
}


def gap_hint(requirement: str, resume_text: str, limit: int = 3) -> str:
    """Resume lines that contain the requirement's key terms ("" if none).
    A gap whose terms are in the resume deserves a second look (F1, F6)."""
    terms = {t for t in _tokens(requirement) if t not in _GENERIC and not t.isdigit()}
    # A requirement with many terms needs two of them on one line: "power"
    # alone (from "band-power features") sent "battery-powered design" for a
    # second look, and the model then called it partial (15c measurement).
    need = 1 if len(terms) <= 3 else 2
    hits = []
    for line in (raw.strip() for raw in resume_text.splitlines()):
        found = terms & _tokens(line)
        if line and len(found) >= need:
            hits.append((len(found), line))
    hits.sort(key=lambda hit: -hit[0])
    return " | ".join(f'"{line[:200]}"' for _, line in hits[:limit])


def analysis_from_checks(reqs: list[tuple[str, str]], checks: list[RequirementCheck]) -> FitAnalysis:
    proven, partial, missing, reasons = [], [], [], {}
    for check in checks:
        text = reqs[check.id][0]
        evidence = check.resume_evidence.strip()
        if check.status in ("proven", "partial") and evidence:
            (proven if check.status == "proven" else partial).append(
                SkillMatch(requirement=text, resume_evidence=evidence))
        else:  # "missing", or a claim with nothing quoted
            missing.append(text)
        if check.status != "proven" and check.reason:
            reasons[text] = check.reason
    return FitAnalysis(matching_skills=proven, partial_skills=partial, missing_skills=missing,
                       talking_points=[], gap_reasons=reasons)


def analyze_fit(job: JobPosting, resume_text: str) -> FitAnalysis:
    """How well does this single resume fit this job? (Facts only, first look.)

    15b: the code owns the requirement list and the model answers each one,
    so nothing is skipped and no gap is invented. Talking points and the
    verdict are written later, for the best resume only."""
    return analysis_from_checks(job_requirements(job), check_requirements(job, resume_text))


def assess_resume(job: JobPosting, resume_text: str) -> ResumeMatch:
    """15c: the first look, then a second look where it is likely wrong:
    - a quote that isn't in the resume (F3: it used to vanish from the score)
    - a gap whose key terms ARE in the resume (F1, F6)
    Both are asked again in one go, with a note each. A quote that still
    isn't in the resume after that is a gap, never a lost requirement."""
    reqs = job_requirements(job)
    checks = {c.id: c for c in check_requirements(job, resume_text)}

    caught, notes = [], {}
    for i, c in checks.items():
        quote = c.resume_evidence.strip()
        if c.status != "missing" and quote and not is_evidence_in_resume(quote, resume_text):
            caught.append(SkillMatch(requirement=reqs[i][0], resume_evidence=quote))
            notes[i] = (f'Your quote "{quote[:160]}" is not in the resume. Quote the resume '
                        "word for word, or answer missing.")
        elif c.status == "missing":
            hint = gap_hint(reqs[i][0], resume_text)
            if hint:
                notes[i] = f"These resume lines share its key terms: {hint}. Read them before answering."
    if notes:
        print(f"    second look at {len(notes)} requirement(s)")
        for c in check_requirements(job, resume_text, ids=sorted(notes), notes=notes):
            quote = c.resume_evidence.strip()
            if c.status != "missing" and not (quote and is_evidence_in_resume(quote, resume_text)):
                c = RequirementCheck(id=c.id, status="missing", resume_evidence="",
                                     reason="its quote isn't in the resume")
            checks[c.id] = c

    match = verify_analysis(analysis_from_checks(reqs, [checks[i] for i in range(len(reqs))]), resume_text)
    return match.model_copy(update={"rejected_matches": caught + match.rejected_matches})


def verify_analysis(analysis: FitAnalysis, resume_text: str) -> ResumeMatch:
    """Split the model's claimed matches (proven and partial) into verified
    and rejected: every quote must really be in the resume."""
    rejected: list[SkillMatch] = []

    def keep(matches: list[SkillMatch]) -> list[SkillMatch]:
        ok = []
        for match in matches:
            (ok if is_evidence_in_resume(match.resume_evidence, resume_text) else rejected).append(match)
        return ok

    cleaned = analysis.model_copy(update={"matching_skills": keep(analysis.matching_skills),
                                          "partial_skills": keep(analysis.partial_skills)})
    return ResumeMatch(resume_name="", analysis=cleaned, rejected_matches=rejected)


TALKING_POINTS_PROMPT = """You help a job seeker prepare an application.
From the RESUME, pick the achievements or projects that best show the PROVEN
requirements below. Use only facts in the resume; keep its numbers exact."""


def write_talking_points(job: JobPosting, match: ResumeMatch, resume_text: str) -> list[str]:
    """15b: for the best resume only, from the requirements that survived
    every check (it used to come from the first, unchecked answer: F10)."""
    proven = "\n".join(f"- {m.requirement}" for m in match.analysis.matching_skills)
    if not proven:
        return []
    prompt = (f"=== RESUME ===\n{resume_text}\n=== END RESUME ===\n\n"
              f"=== JOB ===\n{job.title} at {job.company}\n\n=== PROVEN ===\n{proven}")
    system = f"{TALKING_POINTS_PROMPT}\n{TALKING_POINTS[detail_level()]}"
    answer = structured_llm(TalkingPoints).invoke(
        [SystemMessage(content=system), HumanMessage(content=prompt)])
    return [t.strip() for t in answer.talking_points if t.strip()]


# ---------------------------------------------------------------------------
# Phase 7: LLM-as-judge
# Code can prove a quote EXISTS in the resume, but not that it PROVES the
# skill (e.g. a RAG project quoted as evidence for "LangGraph"). That needs
# judgment, so a second LLM call reviews the first one's work. The judge has
# a narrower job (yes/no per claim) than the writer, which makes it more
# reliable - the same reason code reviews catch bugs the author missed.
# ---------------------------------------------------------------------------

JUDGE_PROMPT = """You are a strict reviewer double-checking a recruiter's work.
For each numbered claim, decide whether the resume quote is real PROOF of that
specific job requirement.
- supported = true only if the quote directly demonstrates the requirement.
- A tool or skill named in the requirement and listed in the resume IS proof,
  wherever it is listed (a skills list counts as much as a project).
- Related-but-different is NOT proof (a React project doesn't prove Vue;
  writing code alone doesn't prove team leadership or communication).
Judge every claim, using its number as the id."""


def judge_evidence(matches: list[SkillMatch]) -> list[SkillJudgment]:
    """One LLM call that rules on all claims at once (faster than one each).

    15c tried a three-way judge (proven / partial / no) that also saw the
    quote's whole resume line. It called proven skills "partial" because
    "the quote is incomplete" (Nexora accuracy 96 % -> 70 %), so it was
    dropped (D39). Only the sentence about skills lists stayed."""
    claims = "\n".join(
        f'{i}. Requirement: {m.requirement}\n   Resume quote: "{m.resume_evidence}"'
        for i, m in enumerate(matches)
    )
    review = structured_llm(EvidenceReview).invoke(
        [SystemMessage(content=JUDGE_PROMPT), HumanMessage(content=claims)]
    )
    return review.judgments


def apply_judgments(match: ResumeMatch, judgments: list[SkillJudgment]) -> ResumeMatch:
    """Move claims the judge rejected out of matching_skills (plain code)."""
    by_id = {j.id: j for j in judgments}
    kept, unsupported, newly_missing = [], [], []
    for i, m in enumerate(match.analysis.matching_skills):
        verdict = by_id.get(i)
        # No verdict for a claim (judge skipped it) -> keep it: we only remove
        # what the judge explicitly rejected.
        if verdict is None or verdict.supported:
            kept.append(m)
        else:
            unsupported.append(f"{m.requirement} - {verdict.reason}")
            # Don't add a gap the model already listed (possibly reworded,
            # e.g. "LangGraph (LangChain is not LangGraph)").
            already_listed = any(
                m.requirement.lower() in gap.lower() for gap in match.analysis.missing_skills
            )
            if not already_listed:
                newly_missing.append(m.requirement)

    analysis = match.analysis.model_copy(
        update={
            "matching_skills": kept,
            "missing_skills": match.analysis.missing_skills + newly_missing,
        }
    )
    return match.model_copy(update={"analysis": analysis, "unsupported_matches": unsupported})


# 15c: "3+ years of ...", "2 yrs", "five years"
YEARS = re.compile(r"\b(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\s*\+?\s*(?:years?|yrs)\b", re.I)


def cap_years(match: ResumeMatch) -> ResumeMatch:
    """A requirement asking for N years is at most partial when its quote says
    nothing about time (a student project for "3+ years": job 14, F7)."""
    kept, partly = [], list(match.analysis.partial_skills)
    reasons = dict(match.analysis.gap_reasons)
    for m in match.analysis.matching_skills:
        if YEARS.search(m.requirement) and not re.search(r"\b(years?|yrs|months?|20\d\d)\b", m.resume_evidence, re.I):
            partly.append(m)
            reasons[m.requirement] = "the skill is shown, but not the years of experience asked for"
        else:
            kept.append(m)
    if len(kept) == len(match.analysis.matching_skills):
        return match
    analysis = match.analysis.model_copy(update={"matching_skills": kept, "partial_skills": partly,
                                                 "gap_reasons": reasons})
    return match.model_copy(update={"analysis": analysis})


# ---------------------------------------------------------------------------
# Phase 8a: the fit score, computed by code
# The LLM's job is to list facts (proven matches, gaps); code verifies them
# and turns them into a number. Same input -> same score, every time, and the
# breakdown shows exactly why.
# ---------------------------------------------------------------------------

def _similar(text: str, other: str) -> bool:
    """True if most of text's words appear in other (wording often differs)."""
    words = set(_words(text))
    return bool(words) and len(words & set(_words(other))) / len(words) >= 0.5


def _is_nice(text: str, job: JobPosting) -> bool:
    """Is this requirement a nice-to-have? Since 15b the text is the job's own
    wording (exact); older rows have the model's wording (similar)."""
    if text in job.required_skills:
        return False
    if text in job.nice_to_have_skills:
        return True
    return any(_similar(text, nice) for nice in job.nice_to_have_skills)


# 15d: how much each kind of requirement counts in the score.
REQUIRED_SHARE = 0.8


def coverage_score(required_have: float, required_n: int, nice_have: float, nice_n: int) -> int:
    """80 % required coverage + 20 % nice-to-have coverage (a job with only
    one kind: that kind alone). Meeting every required skill gives >= 80,
    whatever the nice-to-haves (the old formula capped that case at 77: F7)."""
    if required_n and nice_n:
        value = REQUIRED_SHARE * required_have / required_n + (1 - REQUIRED_SHARE) * nice_have / nice_n
    elif required_n:
        value = required_have / required_n
    elif nice_n:
        value = nice_have / nice_n
    else:
        return 0
    return round(100 * value)


def compute_fit_score(analysis: FitAnalysis, job: JobPosting) -> tuple[int, str]:
    """15d: score = 0.8 x required coverage + 0.2 x nice-to-have coverage,
    where a partly shown requirement counts half (15b)."""
    have = {"required": 0.0, "nice": 0.0}
    count = {"required": 0, "nice": 0}
    partly = {"required": 0, "nice": 0}
    for items, value in ((analysis.matching_skills, 1.0), (analysis.partial_skills, 0.5),
                         ([SkillMatch(requirement=g, resume_evidence="") for g in analysis.missing_skills], 0.0)):
        for m in items:
            kind = "nice" if _is_nice(m.requirement, job) else "required"
            have[kind] += value
            count[kind] += 1
            partly[kind] += value == 0.5
    score = coverage_score(have["required"], count["required"], have["nice"], count["nice"])

    def part(kind: str, title: str) -> str:
        pct = round(100 * have[kind] / count[kind])
        extra = f", {partly[kind]} of them partly" if partly[kind] else ""
        return f"{title}: {have[kind]:g} of {count[kind]} shown{extra} ({pct}%)"

    parts = [part(k, t) for k, t in (("required", "Required"), ("nice", "Nice-to-have")) if count[k]]
    if count["required"] and count["nice"]:
        rule = (f"score = {REQUIRED_SHARE:g} x {round(100 * have['required'] / count['required'])}% + "
                f"{1 - REQUIRED_SHARE:.1g} x {round(100 * have['nice'] / count['nice'])}% = {score}")
    else:
        rule = f"score = {score}"
    note = " (partly shown counts half)" if partly["required"] or partly["nice"] else ""
    return score, "; ".join(parts + [rule]) + note


def score_match(match: ResumeMatch, job: JobPosting) -> ResumeMatch:
    """Return a copy of the match with fit_score + breakdown filled in."""
    score, breakdown = compute_fit_score(match.analysis, job)
    return match.model_copy(update={"fit_score": score, "score_breakdown": breakdown})


def pick_best_resume(
    job: JobPosting, resumes: dict[str, str]
) -> tuple[ResumeMatch, list[ResumeMatch]]:
    """Score + verify (+ judge) every resume, return (best_match, all_matches)."""
    use_judge = os.getenv("JUDGE_EVIDENCE", "true").lower() == "true"
    matches = []
    for name, text in resumes.items():
        print(f"  - scoring '{name}'...")
        match = assess_resume(job, text)  # 15c: first look + second look
        match.resume_name = name
        if use_judge and match.analysis.matching_skills:
            match = apply_judgments(match, judge_evidence(match.analysis.matching_skills))
            if match.unsupported_matches:
                print(f"    [judge] {len(match.unsupported_matches)} claim(s) not "
                      "actually proven by their quote -> moved to gaps")
        match = cap_years(match)
        # Score LAST, after code verification and the judge, so the number is
        # built only from facts that survived every check.
        matches.append(score_match(match, job))

    # The decision is plain code: highest score wins; on a tie, the resume
    # with more VERIFIED matching skills wins.
    best = max(
        matches,
        key=lambda m: (m.fit_score, len(m.analysis.matching_skills)),
    )
    print("  - writing the verdict...")
    points = write_talking_points(job, best, resumes[best.resume_name])
    best = best.model_copy(update={"analysis": best.analysis.model_copy(update={"talking_points": points})})
    analysis = best.analysis.model_copy(update={"verdict": write_verdict(job, best)})
    best = best.model_copy(update={"analysis": analysis})
    matches = [best if m.resume_name == best.resume_name else m for m in matches]
    return best, matches


# ---------------------------------------------------------------------------
# 14c: the verdict, written LAST
# It sees only what survived the quote check and the judge, so it can't
# praise a claim that was rejected. One small call, for the best resume only.
# ---------------------------------------------------------------------------

VERDICT_PROMPT = """You advise a job seeker. Using ONLY the checked facts below,
say whether they should apply and why. Every skill you call a strength must be
in PROVEN; anything in GAPS is not a strength. Be honest and specific: name
the skills and gaps, don't just say "relevant skills" or "some gaps".
Start with one of: "Apply", "Worth a try" or "Not yet". Below a fit score of
50, "Apply" is rarely right.
Shape (fill in from the facts): "<Apply | Worth a try | Not yet>: <proven skill>
and <proven skill> are proven; <gap> is the main gap, so <what to do about it>.\""""

# Shorter than this, the model skipped the "why" ("apply" happened in testing).
MIN_VERDICT_WORDS = 8


def verdict_from_facts(match: ResumeMatch) -> str:
    """The fallback verdict, built by code from the same checked facts."""
    fit = match.analysis
    # Requirements are often whole sentences from the posting: keep a few words.
    short = lambda text: text if len(text.split()) <= 5 else " ".join(text.split()[:5]) + "..."  # noqa: E731
    proven = "; ".join(short(m.requirement) for m in fit.matching_skills[:2]) or "none of the requirements"
    gaps = "; ".join(short(g) for g in fit.missing_skills[:2]) or "none"
    advice = "Worth applying" if match.fit_score >= 60 else "A stretch"
    return f"{advice} (fit {match.fit_score}): proven: {proven}. Main gaps: {gaps}."


def write_verdict(job: JobPosting, match: ResumeMatch) -> str:
    fit = match.analysis
    proven = "\n".join(f"- {m.requirement}" for m in fit.matching_skills) or "- (none)"
    partial = "\n".join(f"- {m.requirement}" for m in fit.partial_skills) or "- (none)"
    gaps = "\n".join(f"- {g}" for g in fit.missing_skills) or "- (none)"
    prompt = (
        f"=== JOB ===\n{job.title} at {job.company}\n{job.summary}\n\n"
        f"=== PROVEN (checked against the resume) ===\n{proven}\n\n"
        f"=== PARTLY SHOWN (not a strength, not a full gap) ===\n{partial}\n\n"
        f"=== GAPS ===\n{gaps}\n\n"
        f"Fit score: {match.fit_score}/100"
    )
    system = f"{VERDICT_PROMPT}\nLength: {VERDICT_LENGTH[detail_level()]}"
    answer = structured_llm(FitVerdict).invoke(
        [SystemMessage(content=system), HumanMessage(content=prompt)]
    )
    verdict = answer.verdict.strip()
    if len(verdict.split()) < MIN_VERDICT_WORDS:
        return verdict_from_facts(match)
    return verdict
