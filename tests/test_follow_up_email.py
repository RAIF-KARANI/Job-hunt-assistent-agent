"""16g: the follow-up email. No model: _ask_model is replaced by a fake.
The points: code states the facts (role, company, date, name); the model's
one sentence is used only if it passes the checks; you always get an email."""

import pytest

from desktop_web.bridge import Api
from job_agent import follow_up_email as fe
from job_agent import tracker
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch, SkillMatch

NOTE = ("Dear Hiring Team,\n\nI'm applying for the Backend Engineer role. I cut DB latency from 1.2 s to 9 ms "
        "and wrote 300+ Jest tests.\n\nI look forward to contributing to your mission. Raif Karani")
GOOD = "I cut DB latency from 1.2 s to 9 ms."


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")


def save(status="applied", note=NOTE):
    posting = JobPosting(title="Backend Engineer", company="Acme Robotics Pvt. Ltd.", location="Bengaluru",
                         employment_type="Full-time", seniority="Junior", salary="Not specified", summary="x",
                         required_skills=["Python"], nice_to_have_skills=[], responsibilities=[])
    analysis = FitAnalysis(matching_skills=[SkillMatch(requirement="Python", resume_evidence="Built a FastAPI service")],
                           missing_skills=[], talking_points=[])
    job_id = tracker.save_job("https://jobs.example/1", posting, ResumeMatch(resume_name="cv.pdf", fit_score=80, analysis=analysis), None)
    if note:
        tracker.add_cover_note(job_id, note)
    tracker.update_status(job_id, status)
    with tracker._db() as conn:
        conn.execute("UPDATE jobs SET updated_at = '2026-11-03 12:00:00' WHERE id = ?", (job_id,))
    return job_id


def draft(job_id, model=None, **kwargs):
    notes = tracker.get_cover_notes(job_id)
    return fe.draft(tracker.get_job(job_id), notes[0]["text"] if notes else None, **kwargs)


def model_says(monkeypatch, *answers):
    said = list(answers)
    calls = []

    def ask(f):
        calls.append(f)
        answer = said.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer
    monkeypatch.setattr(fe, "_ask_model", ask)
    return calls


# ---- the facts are stated by code ------------------------------------------------------

def test_the_name_is_taken_from_the_cover_note():
    assert fe.candidate_name(NOTE) == "Raif Karani"                          # after the last sentence
    assert fe.candidate_name("Dear Hiring Team,\n\nText.\n\nBest regards,\nMohammed Iyad") == "Mohammed Iyad"
    assert fe.candidate_name("Dear Hiring Team,\n\nI look forward to hearing from you.") == ""
    assert fe.candidate_name("Thank you for your time. Best Regards") == ""  # a sign-off isn't a name
    assert fe.candidate_name(None) == "" and fe.candidate_name("") == ""


def test_the_email_states_role_company_date_and_name(monkeypatch):
    model_says(monkeypatch, GOOD)
    result = draft(save())
    assert result["subject"] == "Following up: Backend Engineer application"
    assert result["text"] == (
        "Dear Hiring Team,\n\n"
        "I am following up on my application for the Backend Engineer role at Acme Robotics Pvt. Ltd., "
        "which I sent on 3 November. I cut DB latency from 1.2 s to 9 ms.\n\n"
        "Is there an update, or a timeline for the next steps? I am happy to send anything else you need.\n\n"
        "Best regards,\nRaif Karani")
    assert result["strength"] == GOOD and result["note"] == "" and result["warnings"] == []


def test_the_model_only_sees_the_role_and_the_cover_note(monkeypatch):
    calls = model_says(monkeypatch, GOOD)
    draft(save())
    assert calls[0]["source"] == NOTE and calls[0]["title"] == "Backend Engineer"


# ---- the model's sentence is checked -----------------------------------------------------

@pytest.mark.parametrize("sentence, why", [
    ("I cut DB latency from 1.2 s to 3 ms.", "number that isn't in your cover note (3)"),
    ("I cut DB latency, which aligns with your focus on speed.", "fit their business"),
    ("I built an API. I also wrote tests.", "more than one sentence"),
    ("I built [project] in Python for the team.", "placeholder"),
    ("The candidate cut DB latency from 1.2 s to 9 ms.", "isn't about your own work"),
    ("I did.", "2 words"),
])
def test_a_bad_sentence_is_refused(sentence, why):
    f = {"source": NOTE}
    assert any(why in p for p in fe.problems(sentence, f)), fe.problems(sentence, f)


def test_a_good_sentence_passes():
    assert fe.problems(GOOD, {"source": NOTE}) == []
    assert fe.problems("I wrote 300+ Jest tests for the hiring pipeline.", {"source": NOTE}) == []


def test_a_bad_sentence_is_asked_for_again_then_left_out(monkeypatch):
    calls = model_says(monkeypatch, "I cut costs by 80%.", GOOD)
    assert draft(save())["strength"] == GOOD and len(calls) == 2                # the second try was fine

    calls = model_says(monkeypatch, "I cut costs by 80%.", "I cut costs by 70%.")
    result = draft(save())
    assert len(calls) == 2 and result["strength"] == ""
    assert "80" not in result["text"] and "70" not in result["text"]            # the invented number never reaches you
    assert "I remain very interested in the position." in result["text"]        # still a complete email
    assert "wasn't usable" in result["note"]


def test_a_model_that_fails_still_gives_an_email(monkeypatch):
    calls = model_says(monkeypatch, RuntimeError("connection refused"))
    result = draft(save())
    assert len(calls) == 1 and result["strength"] == "" and "connection refused" in result["note"]
    assert result["text"].startswith("Dear Hiring Team,") and result["text"].endswith("Raif Karani")


# ---- when no sentence is wanted -----------------------------------------------------------

def test_after_an_interview_it_thanks_and_asks(monkeypatch):
    calls = model_says(monkeypatch)                                             # the model is never asked
    result = draft(save(status="interviewing"))
    assert calls == [] and result["subject"] == "Following up: Backend Engineer interview"
    assert result["text"].splitlines()[2].startswith("Thank you for speaking with me about the Backend Engineer role at Acme")
    assert "After an interview" in result["note"]


def test_a_second_follow_up_is_shorter(monkeypatch):
    calls = model_says(monkeypatch)
    job_id = save()
    from job_agent import followup
    followup.mark_followed_up(job_id)
    result = draft(job_id)
    assert calls == [] and "I am following up again on my application" in result["text"]
    assert "second follow-up" in result["note"]


def test_without_a_cover_note_you_are_told_to_add_your_name(monkeypatch):
    calls = model_says(monkeypatch, "I built a FastAPI service.")
    result = draft(save(note=None))
    assert calls[0]["source"] == "Python: Built a FastAPI service"              # what the resume proves, instead
    assert result["text"].endswith("Best regards,") and result["warnings"] == [
        "Add your name at the end: there was no cover note to take it from."]


def test_without_a_model_the_reason_is_said(monkeypatch):
    calls = model_says(monkeypatch)
    result = draft(save(), use_model=False, no_model_reason="The agent is working on another job")
    assert calls == [] and result["note"].startswith("The agent is working on another job, so the email has no sentence")


# ---- the bridge -----------------------------------------------------------------------------

def test_the_page_gets_a_draft_only_when_it_asks(monkeypatch):
    calls = model_says(monkeypatch, GOOD)
    monkeypatch.setattr("desktop_web.bridge.llm_status", lambda: (True, "ready"))
    api = Api(send=lambda e: None, graph=object())
    job_id = save()
    api.list_jobs(), api.get_job(job_id)                                        # looking at a job writes nothing
    assert calls == []
    assert api.draft_follow_up_email(job_id)["strength"] == GOOD and len(calls) == 1
    with pytest.raises(ValueError):
        api.draft_follow_up_email(999)


def test_a_model_that_is_not_ready_is_not_asked(monkeypatch):
    calls = model_says(monkeypatch)
    monkeypatch.setattr("desktop_web.bridge.llm_status", lambda: (False, "Can't reach Ollama"))
    api = Api(send=lambda e: None, graph=object())
    result = api.draft_follow_up_email(save())
    assert calls == [] and "Can't reach Ollama" in result["note"] and result["text"].startswith("Dear Hiring Team,")
