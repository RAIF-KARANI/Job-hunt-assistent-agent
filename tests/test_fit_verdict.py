"""
14c: the verdict is written AFTER the quote check and the judge, for the best
resume only, and the fit answer can be short or detailed.

The LLM is replaced by a fake that records each prompt and returns canned
answers, so these tests check the wiring, not what a model would say.
"""

from langchain_core.messages import HumanMessage, SystemMessage

from job_agent import fit
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

JOB = JobPosting(
    title="AI Engineer", company="Acme", location="Remote", employment_type="Full-time",
    seniority="Mid", salary="Not specified", summary="Build LLM agents.",
    required_skills=["Python", "LangGraph", "Docker"], nice_to_have_skills=[], responsibilities=[],
)
RESUMES = {
    "strong": "Built agents in Python with LangChain; shipped Docker images for them",
    "weak": "Wrote Java services.",
}


class FakeLLM:
    """structured_llm(schema) stand-in: canned answer per schema, prompts recorded."""

    def __init__(self, calls):
        self.calls = calls

    def __call__(self, schema):
        self.schema = schema
        return self

    def invoke(self, messages):
        system = next(m.content for m in messages if isinstance(m, SystemMessage))
        human = next(m.content for m in messages if isinstance(m, HumanMessage))
        self.calls.append((self.schema, system, human))
        if self.schema is FitFacts:
            if "Java" in human:
                return FitFacts(matching_skills=[], missing_skills=["Python", "LangGraph", "Docker"],
                                talking_points=["Java services"])
            return FitFacts(
                matching_skills=[
                    SkillMatch(requirement="Python", resume_evidence="Built agents in Python"),
                    # A real quote that doesn't prove the skill: the judge rejects it.
                    SkillMatch(requirement="LangGraph", resume_evidence="Built agents in Python with LangChain"),
                    SkillMatch(requirement="Docker", resume_evidence="Shipped Docker images"),
                ],
                missing_skills=[], talking_points=["Agents in Python"],
            )
        if self.schema is EvidenceReview:
            return EvidenceReview(judgments=[
                SkillJudgment(id=0, supported=True, reason="ok"),
                SkillJudgment(id=1, supported=False, reason="LangChain is not LangGraph"),
                SkillJudgment(id=2, supported=True, reason="ok"),
            ])
        assert self.schema is FitVerdict
        return FitVerdict(verdict=self.verdict)

    verdict = "  Apply: Python and Docker are proven; LangGraph is the main gap.  "


def run(monkeypatch, detail=None, verdict=None):
    calls = []
    fake = FakeLLM(calls)
    if verdict is not None:
        fake.verdict = verdict
    monkeypatch.setattr(fit, "structured_llm", fake)
    monkeypatch.setenv("JUDGE_EVIDENCE", "true")
    if detail is None:
        monkeypatch.delenv("FIT_DETAIL", raising=False)
    else:
        monkeypatch.setenv("FIT_DETAIL", detail)
    best, matches = fit.pick_best_resume(JOB, RESUMES)
    return best, matches, calls


def test_verdict_is_written_last_from_the_checked_facts(monkeypatch):
    best, _, calls = run(monkeypatch)
    assert [c[0] for c in calls][-1] is FitVerdict  # after both scorings and the judge
    _, _, prompt = calls[-1]
    proven = prompt.split("=== PROVEN")[1].split("=== GAPS")[0]
    assert "Python" in proven and "Docker" in proven
    assert "LangGraph" not in proven  # rejected by the judge -> only under GAPS
    assert "LangGraph" in prompt.split("=== GAPS ===")[1]
    assert best.analysis.verdict == "Apply: Python and Docker are proven; LangGraph is the main gap."


def test_only_the_best_resume_gets_a_verdict(monkeypatch):
    best, matches, calls = run(monkeypatch)
    assert sum(c[0] is FitVerdict for c in calls) == 1
    by_name = {m.resume_name: m for m in matches}
    assert best.resume_name == "strong"
    assert by_name["strong"].analysis.verdict == best.analysis.verdict  # the list has the same answer
    assert by_name["weak"].analysis.verdict == ""


def test_short_is_the_default_and_detailed_asks_for_more(monkeypatch):
    _, _, calls = run(monkeypatch)
    facts_system = next(c[1] for c in calls if c[0] is FitFacts)
    assert "at most 3" in facts_system
    assert "One sentence." in calls[-1][1]

    _, _, calls = run(monkeypatch, "detailed")
    facts_system = next(c[1] for c in calls if c[0] is FitFacts)
    assert "3-5" in facts_system
    assert "Two or three sentences" in calls[-1][1]


def test_a_one_word_verdict_is_replaced_by_one_built_from_the_facts(monkeypatch):
    # qwen3:8b once answered just "apply" (14c measurement).
    best, _, _ = run(monkeypatch, verdict="apply")
    assert best.analysis.verdict == (
        f"Worth applying (fit {best.fit_score}): proven: Python; Docker. Main gaps: LangGraph."
    )


def test_unknown_detail_level_counts_as_short(monkeypatch):
    monkeypatch.setenv("FIT_DETAIL", "huge")
    assert fit.detail_level() == "short"


def test_short_keeps_every_match_and_quote(monkeypatch):
    # The score must not depend on the setting: short trims words, not facts.
    short, _, _ = run(monkeypatch, "short")
    detailed, _, _ = run(monkeypatch, "detailed")
    assert short.fit_score == detailed.fit_score
    assert short.analysis.matching_skills == detailed.analysis.matching_skills


def test_rows_saved_before_14c_still_load():
    old = '{"resume_name": "cv", "analysis": {"matching_skills": [], "missing_skills": [], ' \
          '"talking_points": [], "verdict": "written by the old prompt"}}'
    assert ResumeMatch.model_validate_json(old).analysis.verdict == "written by the old prompt"
    new = FitAnalysis(matching_skills=[], missing_skills=[], talking_points=[])
    assert new.verdict == ""


def test_the_llm_is_never_asked_for_a_verdict_per_resume():
    # The per-resume schema has no verdict field any more.
    assert "verdict" not in FitFacts.model_json_schema()["properties"]
