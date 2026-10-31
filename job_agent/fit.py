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
    FitFacts,
    FitVerdict,
    JobPosting,
    ResumeMatch,
    SkillJudgment,
    SkillMatch,
)

SYSTEM_PROMPT = """You are an experienced technical recruiter.
Compare the candidate's RESUME with the JOB POSTING. Be honest and specific.
Rules:
- A skill matches ONLY if the RESUME shows it. The job posting is never evidence.
- For each match, quote a short phrase copied word-for-word from the RESUME.
- Anything required but not in the resume goes in missing_skills.
- Do not invent experience. If unsure, treat it as missing."""

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
    """Lowercase words/numbers, ignoring punctuation and tiny words."""
    return [w for w in re.findall(r"[a-z0-9+#.]+", text.lower()) if len(w) > 2]


def is_evidence_in_resume(evidence: str, resume_text: str) -> bool:
    """Plain-code fact check: does the quoted evidence really come from the resume?"""
    quote_words = _words(evidence)
    if not quote_words:
        return False
    resume_words = set(_words(resume_text))
    found = sum(1 for w in quote_words if w in resume_words)
    return found / len(quote_words) >= EVIDENCE_THRESHOLD


def analyze_fit(job: JobPosting, resume_text: str) -> FitAnalysis:
    """One LLM call: how well does this single resume fit this job? (Facts only.)"""
    llm = structured_llm(FitFacts)

    # Send the structured job (from Phase 1) as JSON, not the raw page:
    # it's shorter and already cleaned up, so the model focuses better.
    # Clear section markers help the model keep the two documents apart.
    prompt = (
        f"=== JOB POSTING ===\n{job.model_dump_json(indent=2)}\n\n"
        f"=== RESUME ===\n{resume_text}\n=== END RESUME ==="
    )
    system = f"{SYSTEM_PROMPT}\n{TALKING_POINTS[detail_level()]}"
    facts = llm.invoke([SystemMessage(content=system), HumanMessage(content=prompt)])
    return FitAnalysis(**facts.model_dump())


def verify_analysis(analysis: FitAnalysis, resume_text: str) -> ResumeMatch:
    """Split the model's claimed matches into verified and rejected."""
    verified: list[SkillMatch] = []
    rejected: list[SkillMatch] = []
    for match in analysis.matching_skills:
        if is_evidence_in_resume(match.resume_evidence, resume_text):
            verified.append(match)
        else:
            rejected.append(match)

    cleaned = analysis.model_copy(update={"matching_skills": verified})
    return ResumeMatch(resume_name="", analysis=cleaned, rejected_matches=rejected)


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
- Related-but-different is NOT proof (a React project doesn't prove Vue;
  writing code alone doesn't prove team leadership or communication).
Judge every claim, using its number as the id."""


def judge_evidence(matches: list[SkillMatch]) -> list[SkillJudgment]:
    """One LLM call that rules on all claims at once (faster than one each)."""
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


# ---------------------------------------------------------------------------
# Phase 8a: the fit score, computed by code
# The LLM's job is to list facts (proven matches, gaps); code verifies them
# and turns them into a number. Same input -> same score, every time, and the
# breakdown shows exactly why.
# ---------------------------------------------------------------------------

# A missing nice-to-have hurts less than a missing requirement.
NICE_TO_HAVE_WEIGHT = 0.3


def _similar(text: str, other: str) -> bool:
    """True if most of text's words appear in other (wording often differs)."""
    words = set(_words(text))
    return bool(words) and len(words & set(_words(other))) / len(words) >= 0.5


def compute_fit_score(analysis: FitAnalysis, job: JobPosting) -> tuple[int, str]:
    """score = proven / (proven + required gaps + 0.3 x nice-to-have gaps)."""
    proven = len(analysis.matching_skills)
    nice_gaps = sum(
        1
        for gap in analysis.missing_skills
        if any(_similar(gap, nice) for nice in job.nice_to_have_skills)
    )
    required_gaps = len(analysis.missing_skills) - nice_gaps

    total = proven + required_gaps + NICE_TO_HAVE_WEIGHT * nice_gaps
    score = round(100 * proven / total) if total else 0
    breakdown = (
        f"{proven} proven / ({proven} proven + {required_gaps} required gaps + "
        f"{NICE_TO_HAVE_WEIGHT} x {nice_gaps} nice-to-have gaps) = {score}"
    )
    return score, breakdown


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
        match = verify_analysis(analyze_fit(job, text), text)
        match.resume_name = name
        if use_judge and match.analysis.matching_skills:
            match = apply_judgments(match, judge_evidence(match.analysis.matching_skills))
            if match.unsupported_matches:
                print(f"    [judge] {len(match.unsupported_matches)} claim(s) not "
                      "actually proven by their quote -> moved to gaps")
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
    gaps = "\n".join(f"- {g}" for g in fit.missing_skills) or "- (none)"
    prompt = (
        f"=== JOB ===\n{job.title} at {job.company}\n{job.summary}\n\n"
        f"=== PROVEN (checked against the resume) ===\n{proven}\n\n"
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
