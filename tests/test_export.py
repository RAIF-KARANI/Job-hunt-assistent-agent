"""
Tests for export (14i): the tracker as CSV, a cover note as .txt / .docx /
.pdf. The Save dialog is replaced by a temp path; files are read back.
"""

import csv
import zipfile
from xml.dom import minidom

import pytest
from pypdf import PdfReader

from desktop_web.bridge import Api
from job_agent import cover_note, export, tracker
from job_agent.models import FitAnalysis, JobPosting, ResumeMatch

NOTE = "Dear Hiring Team,\n\nI built LangGraph agents at Łódź Labs.\nFirst line, second line.\n\nBest regards,\nRaif"


@pytest.fixture(autouse=True)
def temp_db(tmp_path, monkeypatch):
    monkeypatch.setattr(tracker, "DB_PATH", tmp_path / "jobs.db")
    monkeypatch.setattr(cover_note, "NOTES_DIR", tmp_path / "notes")


def save(url="https://jobs.example/1", title="AI Engineer", company="Acme"):
    job = JobPosting(title=title, company=company, location="Dubai", employment_type="Full-time",
                     seniority="Mid", salary="AED 20k", summary="s",
                     required_skills=["Python"], nice_to_have_skills=[], responsibilities=["x"])
    analysis = FitAnalysis(matching_skills=[], missing_skills=[], talking_points=[], verdict="ok")
    return tracker.save_job(url, job, ResumeMatch(resume_name="cv.pdf", analysis=analysis, fit_score=70), None)


def api_saving_to(path):
    api = Api(send=lambda e: None, graph=object())
    api._save_path = lambda name, kind: path if path else None
    return api


# ---- CSV -----------------------------------------------------------------------

def test_the_tracker_exports_one_row_per_job_with_your_notes(tmp_path):
    first = save()
    save("https://jobs.example/2", "Data Engineer", "Zürich Analytics")
    tracker.update_status(first, "applied")
    tracker.save_notes(first, {"notes": "Line one\nline two", "interview_at": "2026-11-04T10:30", "contact": "Sara"})
    out = tmp_path / "jobs.csv"
    assert api_saving_to(out).export_tracker() == {"path": str(out), "count": 2}
    assert out.read_bytes().startswith(b"\xef\xbb\xbf")          # BOM: Excel reads UTF-8
    rows = list(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert rows[0]["Company"] == "Acme" and rows[0]["Status"] == "Applied"
    assert rows[0]["Interview"] == "2026-11-04T10:30" and rows[0]["Notes"] == "Line one\nline two"
    assert rows[1]["Company"] == "Zürich Analytics" and rows[1]["Fit"] == "70"


def test_a_cell_that_excel_would_run_as_a_formula_is_defused(tmp_path):
    save(title='=HYPERLINK("http://evil.example","Click")', company="+Acme")
    out = tmp_path / "jobs.csv"
    export.export_tracker_csv(out)
    row = next(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert row["Role"].startswith("'=") and row["Company"] == "'+Acme"


def test_cancelling_the_dialog_writes_nothing():
    save()
    assert api_saving_to(None).export_tracker() is None


# ---- cover notes ------------------------------------------------------------------

def approved_job():
    job_id = save()
    tracker.add_cover_note(job_id, NOTE)
    return job_id


def test_txt(tmp_path):
    out = tmp_path / "note.txt"
    api_saving_to(out).export_cover_note(approved_job(), "txt")
    assert out.read_text(encoding="utf-8") == NOTE + "\n"


def test_docx_is_a_word_document_with_the_paragraphs(tmp_path):
    out = tmp_path / "note.docx"
    api_saving_to(out).export_cover_note(approved_job(), "docx")
    with zipfile.ZipFile(out) as z:
        assert {"[Content_Types].xml", "_rels/.rels", "word/document.xml", "word/styles.xml"} <= set(z.namelist())
        document = z.read("word/document.xml").decode("utf-8")
    assert document.count("<w:p>") == 3                          # 3 paragraphs
    assert "Łódź Labs." in document and "<w:br/>" in document     # a single line break stays a break
    minidom.parseString(document)                                # well-formed


def test_docx_escapes_text_that_looks_like_xml(tmp_path):
    out = tmp_path / "x.docx"
    export.write_docx(out, "Salary <negotiable> & benefits")
    with zipfile.ZipFile(out) as z:
        assert "Salary &lt;negotiable&gt; &amp; benefits" in z.read("word/document.xml").decode("utf-8")


def test_pdf_has_the_text_including_non_english_letters(tmp_path):
    out = tmp_path / "note.pdf"
    api_saving_to(out).export_cover_note(approved_job(), "pdf")
    text = PdfReader(out).pages[0].extract_text()
    assert "Dear Hiring Team," in text and "Łódź Labs." in text and "Best regards," in text


def test_no_note_or_a_bad_format_is_refused(tmp_path):
    job_id = save()
    api = api_saving_to(tmp_path / "x.pdf")
    with pytest.raises(ValueError, match="no approved cover note"):
        api.export_cover_note(job_id, "pdf")
    with pytest.raises(ValueError, match="Format"):
        api.export_cover_note(job_id, "exe")


def test_file_names_are_safe_on_windows():
    assert export.file_name("Cover note", "A/B: Co?", "Dev <Lead>", ext="docx") == "Cover note - A B Co - Dev Lead.docx"
    assert len(export.file_name("x" * 500, ext="pdf")) <= 124


def test_show_in_folder_opens_only_what_was_exported(tmp_path):
    api = api_saving_to(tmp_path / "note.txt")
    with pytest.raises(ValueError):
        api.show_in_folder(r"C:\Windows\System32\cmd.exe")
