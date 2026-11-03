"""15f: splitting a resume into projects and jobs, picking achievements for a
job, and catching a project put at the wrong employer. Made-up resume in the
layout of a real one (PDF text: no bullets, wrapped lines)."""

from job_agent.achievements import pick_achievements, placement_notices, resume_entries
from job_agent.cover_note import note_notices

RESUME = """Alex Example
Pune, India | alex@example.com
SUMMARY
Engineer who builds LLM tools, e.g. ReviewBot, a code reviewer.
EDUCATION
Example Institute of Technology, Pune 2022 - 2026
B.E. Computer Science, CGPA 8.1 / 10
PROJECTS
ReviewBot - AI Code Reviewer for Pull Requests Live | Code
Python, FastAPI, Celery, Redis, PostgreSQL, Docker
Built a GitHub App that reviews pull requests with a local LLM and posts
inline comments about 40 seconds after a push.
Built a 50-case evaluation harness gated by a bootstrap CI:
raised F1 from 0.60 to 0.75.
my-shop - Online Store with React
React, TypeScript, Node.js, Express, MongoDB
Built a React storefront with a cart, Stripe test payments and 120 Jest tests.
EXPERIENCE
Acme Training Jan 2026 - Jul 2026
Software Engineering Intern
Completed Java full-stack training (core Java, OOP, JDBC, Servlets/JSP, SQL),
applying data structures in hands-on builds.
Widget Corp Feb 2025 - May 2025
Android Intern
Built 2 Android apps with Firebase and reduced network latency by 25%.
TECHNICAL SKILLS
Languages: Python, Java, TypeScript"""


def test_entries_follow_the_resume():
    entries = resume_entries(RESUME)
    assert [(e.kind, e.name) for e in entries] == [
        ("education", "Example Institute of Technology"),
        ("project", "ReviewBot"), ("project", "my-shop"),
        ("experience", "Acme Training"), ("experience", "Widget Corp")]
    review = entries[1]
    assert len(review.facts) == 2  # wrapped lines joined; the tech line skipped
    assert review.facts[1] == "Built a 50-case evaluation harness gated by a bootstrap CI: raised F1 from 0.60 to 0.75."
    assert entries[3].role == "Software Engineering Intern"
    assert entries[3].facts[0].startswith("Completed Java full-stack training")


def test_titles_are_not_mistaken_for_verbs():
    text = "PROJECTS\nVision-Guided Robotic Arm Team of 4\nBuilt the OpenCV pipeline.\n" \
           "EXPERIENCE\nEmbedded / IoT Intern, Adsafe Solutions Jun - Jul 2026\nBuilt a grow-box controller."
    entries = resume_entries(text)
    assert [e.name for e in entries] == ["Vision-Guided Robotic Arm Team of 4", "Embedded / IoT Intern"]


def test_the_job_decides_which_projects_are_picked():
    entries = resume_entries(RESUME)
    frontend = pick_achievements(entries, ["React and TypeScript", "Jest testing", "REST APIs with Node.js"])
    assert frontend[0].entry.name == "my-shop"
    llm = pick_achievements(entries, ["LLM applications", "Python and FastAPI", "evaluation of models"])
    assert llm[0].entry.name == "ReviewBot"
    android = pick_achievements(entries, ["Android development", "Firebase"])
    assert android[0].entry.name == "Widget Corp"
    assert all(a.entry.kind != "education" for a in llm + frontend + android)


def test_a_verified_quote_pulls_its_entry_up():
    entries = resume_entries(RESUME)
    picked = pick_achievements(entries, ["code quality"], evidence=["reduced network latency by 25%"])
    assert picked[0].entry.name == "Widget Corp"


def test_a_project_at_the_wrong_employer_is_flagged():
    entries = resume_entries(RESUME)
    bad = ("Dear Hiring Team,\n\nAs a Software Engineering Intern, I built ReviewBot, an AI reviewer. "
           "At Widget Corp I built my-shop. At my university, I developed ReviewBot.")
    notices = placement_notices(bad, entries)
    assert any("ReviewBot" in n and "Acme Training" in n for n in notices)
    assert any("my-shop" in n and "Widget Corp" in n for n in notices)
    assert any("university" in n for n in notices)
    good = "I built ReviewBot, a GitHub App that reviews pull requests. At Widget Corp I reduced latency by 25%."
    assert placement_notices(good, entries) == []


def test_stock_phrases_are_flagged():
    notices = note_notices("Dear Hiring Team,\n\nI’m excited to apply for the role; it aligns with my passion.", RESUME)
    assert len(notices) == 2 and all("Stock phrase" in n for n in notices)


def test_a_resume_without_sections_gives_no_entries():
    assert resume_entries("Just a paragraph about me. I like Python.") == []


def test_a_project_in_an_unnamed_job_is_flagged():
    # 15f eval (Intel): "At my last role, I developed a RAG Document Assistant ..."
    entries = resume_entries(RESUME)
    notices = placement_notices("At my last role, I developed ReviewBot, a code reviewer.", entries)
    assert notices == ["“ReviewBot” is a project in your resume, not part of a job: check this sentence."]
