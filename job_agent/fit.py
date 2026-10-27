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

import re

from langchain_core.messages import HumanMessage, SystemMessage

from job_agent.llm import get_llm
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch, SkillMatch

SYSTEM_PROMPT = """You are an experienced technical recruiter.
Compare the candidate's RESUME with the JOB POSTING. Be honest and specific.
Rules:
- A skill matches ONLY if the RESUME shows it. The job posting is never evidence.
- For each match, quote a short phrase copied word-for-word from the RESUME.
- Anything required but not in the resume goes in missing_skills.
- Do not invent experience. If unsure, treat it as missing."""

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
    """One LLM call: how well does this single resume fit this job?"""
    structured_llm = get_llm().with_structured_output(FitAnalysis)

    # Send the structured job (from Phase 1) as JSON, not the raw page:
    # it's shorter and already cleaned up, so the model focuses better.
    # Clear section markers help the model keep the two documents apart.
    prompt = (
        f"=== JOB POSTING ===\n{job.model_dump_json(indent=2)}\n\n"
        f"=== RESUME ===\n{resume_text}\n=== END RESUME ==="
    )
    return structured_llm.invoke(
        [SystemMessage(content=SYSTEM_PROMPT), HumanMessage(content=prompt)]
    )


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


def pick_best_resume(
    job: JobPosting, resumes: dict[str, str]
) -> tuple[ResumeMatch, list[ResumeMatch]]:
    """Score + verify every resume, return (best_match, all_matches)."""
    matches = []
    for name, text in resumes.items():
        print(f"  - scoring '{name}'...")
        match = verify_analysis(analyze_fit(job, text), text)
        match.resume_name = name
        matches.append(match)

    # The decision is plain code: highest score wins; on a tie, the resume
    # with more VERIFIED matching skills wins.
    best = max(
        matches,
        key=lambda m: (m.analysis.fit_score, len(m.analysis.matching_skills)),
    )
    return best, matches
