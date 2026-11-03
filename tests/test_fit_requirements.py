"""15b: the code owns the requirement list; the model answers each one.

A fake LLM answers in RequirementReview batches, so these check the wiring:
nothing skipped, nothing invented, batches, the retry, partial in the score."""

from langchain_core.messages import HumanMessage

from job_agent import fit
from job_agent.models import (
    FitAnalysis,
    JobPosting,
    RequirementCheck,
    RequirementReview,
    SkillMatch,
)


def job(required, nice=()):
    return JobPosting(title="Engineer", company="Acme", location="Remote", employment_type="Full-time",
                      seniority="Entry", salary="Not specified", summary="Build things.",
                      required_skills=list(required), nice_to_have_skills=list(nice), responsibilities=[])


class Answers:
    """Answers each listed id with `status_for(id)`; can skip ids on the first try."""

    def __init__(self, status_for, skip_first=()):
        self.status_for, self.skip_first, self.batches = status_for, set(skip_first), []

    def __call__(self, schema):
        assert schema is RequirementReview
        return self

    def invoke(self, messages):
        human = next(m.content for m in messages if isinstance(m, HumanMessage))
        ids = [int(line.split(".")[0]) for line in
               human.split("=== REQUIREMENTS TO CHECK ===")[1].strip().splitlines()]
        self.batches.append(ids)
        retry = len(self.batches) > 1 and set(ids) <= self.skip_first
        checks = []
        for i in ids:
            if i in self.skip_first and not retry:
                continue
            status = self.status_for(i)
            checks.append(RequirementCheck(id=i, status=status, reason=f"r{i}",
                                           resume_evidence="" if status == "missing" else f"quote {i}"))
        return RequirementReview(checks=checks)


def test_requirements_keep_order_and_drop_repeats():
    j = job(["Python programming", "Git and Linux"], ["Python programming", "Docker"])
    assert fit.job_requirements(j) == [("Python programming", "required"), ("Git and Linux", "required"),
                                      ("Docker", "nice")]


def test_a_shorter_requirement_is_not_a_repeat_of_a_longer_one():
    j = job(["Familiarity with Git"], ["Familiarity with Git and Linux"])
    assert len(fit.job_requirements(j)) == 2


def test_short_words_tell_requirements_apart():
    assert len(fit.job_requirements(job(["Knowledge of C", "Knowledge of Go"]))) == 2


def test_every_requirement_gets_an_answer_in_batches(monkeypatch):
    fake = Answers(lambda i: "proven")
    monkeypatch.setattr(fit, "structured_llm", fake)
    checks = fit.check_requirements(job([f"skill {n}" for n in range(13)]), "resume")
    assert [c.id for c in checks] == list(range(13))
    assert fake.batches == [list(range(0, 6)), list(range(6, 12)), [12]]


def test_skipped_ids_are_asked_again_then_count_as_missing(monkeypatch):
    fake = Answers(lambda i: "proven", skip_first={1, 2})
    monkeypatch.setattr(fit, "structured_llm", fake)
    checks = fit.check_requirements(job(["a1", "b2", "c3"]), "resume")
    assert fake.batches == [[0, 1, 2], [1, 2]]          # one retry, only the skipped ones
    assert [c.status for c in checks] == ["proven", "proven", "proven"]

    class Silent(Answers):
        def invoke(self, messages):
            self.batches.append(None)
            return RequirementReview(checks=[])
    monkeypatch.setattr(fit, "structured_llm", Silent(lambda i: "proven"))
    checks = fit.check_requirements(job(["a1"]), "resume")
    assert checks[0].status == "missing" and "no answer" in checks[0].reason


def test_gaps_use_the_jobs_own_wording_so_none_is_invented(monkeypatch):
    status = {0: "proven", 1: "partial", 2: "missing"}
    monkeypatch.setattr(fit, "structured_llm", Answers(status.get))
    a = fit.analyze_fit(job(["Python", "Embedded C", "RTOS"]), "resume")
    assert [m.requirement for m in a.matching_skills] == ["Python"]
    assert [m.requirement for m in a.partial_skills] == ["Embedded C"]
    assert a.missing_skills == ["RTOS"]
    assert a.gap_reasons == {"Embedded C": "r1", "RTOS": "r2"}


def test_a_proven_claim_without_a_quote_is_a_gap(monkeypatch):
    class NoQuote(Answers):
        def invoke(self, messages):
            return RequirementReview(checks=[RequirementCheck(id=0, status="proven", resume_evidence=" ",
                                                              reason="trust me")])
    monkeypatch.setattr(fit, "structured_llm", NoQuote(None))
    assert fit.analyze_fit(job(["Python"]), "resume").missing_skills == ["Python"]


def test_partial_quotes_are_checked_too():
    a = FitAnalysis(matching_skills=[], missing_skills=[], talking_points=[],
                    partial_skills=[SkillMatch(requirement="C", resume_evidence="Arduino C firmware"),
                                    SkillMatch(requirement="BLE", resume_evidence="invented Bluetooth stack")])
    m = fit.verify_analysis(a, "Developed Arduino C firmware for sensors")
    assert [s.requirement for s in m.analysis.partial_skills] == ["C"]
    assert [s.requirement for s in m.rejected_matches] == ["BLE"]


def test_partial_counts_half():
    j = job(["Python", "Embedded C"], ["Docker"])
    a = FitAnalysis(matching_skills=[SkillMatch(requirement="Python", resume_evidence="x")],
                    partial_skills=[SkillMatch(requirement="Embedded C", resume_evidence="x")],
                    missing_skills=["Docker"], talking_points=[])
    score, breakdown = fit.compute_fit_score(a, j)
    # 1.5 proven / (1.5 + 0 required gaps + 0.3 x 1 nice gap + 0.5 x 1 partial required) = 1.5 / 2.3
    assert score == 65
    assert "0.5 x 1 partial" in breakdown and "1 nice-to-have gaps" in breakdown


def test_an_exact_required_wording_is_never_taken_for_a_nice_to_have():
    # _similar alone would call "Python" a nice-to-have here.
    j = job(["Python"], ["Python scripting for test automation"])
    a = FitAnalysis(matching_skills=[], missing_skills=["Python"], talking_points=[])
    _, breakdown = fit.compute_fit_score(a, j)
    assert "1 required gaps" in breakdown
