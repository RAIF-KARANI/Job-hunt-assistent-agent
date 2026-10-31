"""
Tests for the "don't trust, verify" checks.

These are the code-only parts of the agent: no LLM, no network, so they run
in milliseconds and give the same result every time. We can't unit-test what
Qwen will say, but we CAN test that our safety nets catch bad output.
"""

from job_agent.cover_note import unverified_numbers
from job_agent.fit import apply_judgments, is_evidence_in_resume
from job_agent.models import FitAnalysis, ResumeMatch, SkillJudgment, SkillMatch
from job_agent.research import remove_invented_dates, verify_sources

RESUME = """Built a GitHub App that reviews pull requests with a local 8B LLM.
Exposed 12 REST endpoints with JWT and bcrypt auth.
DB latency 1.2 s to 9 ms; 900+ tests in CI."""


# ---- Phase 2: resume evidence -------------------------------------------


def test_exact_quote_is_verified():
    assert is_evidence_in_resume("Exposed 12 REST endpoints with JWT", RESUME)


def test_quote_from_the_end_of_a_sentence_is_verified():
    # The full stop used to stay on the last word: "images." != "images".
    assert is_evidence_in_resume("Shipped Docker images", "Shipped Docker images. Then more.")


def test_dots_inside_words_still_count():
    resume = "Built APIs in Node.js and .NET, cut latency to 1.2 s."
    assert is_evidence_in_resume("APIs in Node.js and .NET", resume)
    assert not is_evidence_in_resume("APIs in Node and NET", "Built APIs in Node.js and .NET")


def test_quote_with_small_changes_is_still_verified():
    # Small models often tweak a word; 80% of words matching is enough.
    assert is_evidence_in_resume("Exposed 12 REST endpoints using JWT and bcrypt", RESUME)


def test_invented_evidence_is_rejected():
    # The real hallucination we caught in Phase 2.
    assert not is_evidence_in_resume("Designed GraphQL APIs for my-rag", RESUME)


def test_empty_evidence_is_rejected():
    assert not is_evidence_in_resume("", RESUME)


# ---- Phase 7: applying the judge's verdicts ------------------------------


def _match(*requirements):
    skills = [SkillMatch(requirement=r, resume_evidence="quote") for r in requirements]
    analysis = FitAnalysis(
        matching_skills=skills, missing_skills=["Rust"], talking_points=[], verdict="ok",
    )
    return ResumeMatch(resume_name="cv", analysis=analysis)


def test_judge_rejections_move_to_gaps():
    match = _match("Python", "LangGraph", "APIs")
    judged = apply_judgments(match, [
        SkillJudgment(id=0, supported=True, reason="direct"),
        SkillJudgment(id=1, supported=False, reason="RAG is not LangGraph"),
        SkillJudgment(id=2, supported=True, reason="direct"),
    ])
    assert [m.requirement for m in judged.analysis.matching_skills] == ["Python", "APIs"]
    assert judged.analysis.missing_skills == ["Rust", "LangGraph"]
    assert judged.unsupported_matches == ["LangGraph - RAG is not LangGraph"]


def test_judge_does_not_duplicate_an_existing_gap():
    # Real bug seen with qwen3:14b: the model listed the gap itself (reworded)
    # AND claimed it as a match; the judge then added it a second time.
    match = _match("LangGraph")
    match.analysis.missing_skills = ["LangGraph (only LangChain is mentioned)"]
    judged = apply_judgments(match, [SkillJudgment(id=0, supported=False, reason="no")])
    assert judged.analysis.missing_skills == ["LangGraph (only LangChain is mentioned)"]


def test_claims_the_judge_skipped_are_kept():
    match = _match("Python", "APIs")
    judged = apply_judgments(match, [SkillJudgment(id=0, supported=True, reason="ok")])
    assert len(judged.analysis.matching_skills) == 2


# ---- Phase 3: research sources and dates ---------------------------------

SEARCH_RESULTS = """Date: 2026-10-14
Title: GitLab patches CVE
URL: https://example.com/gitlab-cve
Snippet: ..."""


def test_invented_urls_are_dropped():
    sources = ["https://example.com/gitlab-cve", "https://made-up.com/fake"]
    assert verify_sources(sources, SEARCH_RESULTS) == ["https://example.com/gitlab-cve"]


def test_invented_dates_are_replaced():
    # The real bug from Phase 3: today's date minus one year.
    news = ["2026-10-14: security patch", "2025-10-27: stock fell"]
    assert remove_invented_dates(news, SEARCH_RESULTS) == [
        "2026-10-14: security patch",
        "date unknown: stock fell",
    ]


# ---- Phase 5: numbers in the cover note ----------------------------------


def test_numbers_from_the_resume_are_fine():
    note = "I cut DB latency from 1.2 s to 9 ms and wrote 900+ tests."
    assert unverified_numbers(note, RESUME) == []


def test_invented_numbers_are_flagged():
    note = "I improved throughput by 300% across 12 endpoints."
    assert unverified_numbers(note, RESUME) == ["300"]
