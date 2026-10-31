"""
Export (14i, D35): the tracker to CSV, a cover note to .txt, .docx or .pdf.

    CSV   -> opens in Excel / Google Sheets: one row per job, your notes too.
             UTF-8 with a BOM, so Excel shows non-English names correctly.
             A cell starting with = + - @ gets a leading ' : job titles come
             from the web, and Excel would run such a cell as a formula.
    .txt  -> the note as plain text
    .docx -> a Word document, written with the standard library (a .docx is
             a zip of XML files): no extra dependency
    .pdf  -> ReportLab (BSD), with Windows' Arial embedded so any name in the
             note prints; Helvetica if Arial isn't there

NO LLM here: files are written exactly from what's in the tracker.
Tests: tests/test_export.py.
"""

import csv
import re
import zipfile
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape

from job_agent import tracker

CSV_COLUMNS = [
    ("id", "Job #"), ("company", "Company"), ("title", "Role"), ("status", "Status"),
    ("fit_score", "Fit"), ("best_resume", "Best resume"), ("location", "Location"),
    ("salary", "Salary"), ("interview_at", "Interview"), ("contact", "Contact"),
    ("notes", "Notes"), ("url", "Posting"), ("created_at", "Analyzed (UTC)"),
    ("updated_at", "Status changed (UTC)"),
]
STATUS_LABELS = {"researched": "Researched", "cover_note_ready": "Cover note ready", "applied": "Applied",
                 "interviewing": "Interviewing", "offer": "Offer", "rejected": "Rejected"}
FORMATS = ("txt", "docx", "pdf")


def file_name(*parts: str, ext: str) -> str:
    """'Cover note - LamdaX - AI Engineer.docx': safe on Windows, not too long."""
    text = " - ".join(p for p in parts if p)
    text = re.sub(r'[<>:"/\\|?*\x00-\x1f]', " ", text)
    text = re.sub(r"\s+", " ", text).strip(" .")[:120] or "JobLens"
    return f"{text}.{ext}"


def _cell(value) -> str:
    text = "" if value is None else str(value)
    return "'" + text if text[:1] in ("=", "+", "-", "@", "\t", "\r") else text


def tracker_rows() -> list[dict]:
    tracker.init_db()
    with tracker._db() as conn:
        rows = conn.execute("SELECT * FROM jobs ORDER BY created_at, id").fetchall()
    return [dict(r) for r in rows]


def export_tracker_csv(path: Path) -> int:
    """Every tracked job as a CSV row. Returns the number of jobs."""
    rows = tracker_rows()
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        writer = csv.writer(f)
        writer.writerow([label for _, label in CSV_COLUMNS])
        for row in rows:
            row["status"] = STATUS_LABELS.get(row["status"], row["status"])
            writer.writerow([_cell(row.get(key)) for key, _ in CSV_COLUMNS])
    return len(rows)


def _paragraphs(text: str) -> list[list[str]]:
    """Blank lines split paragraphs; single line breaks stay inside one."""
    blocks = re.split(r"\n\s*\n", text.replace("\r\n", "\n").strip())
    return [block.split("\n") for block in blocks if block.strip()]


def write_txt(path: Path, text: str) -> None:
    Path(path).write_text(text.strip() + "\n", encoding="utf-8")


_DOCX_TYPES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">
<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>
<Default Extension="xml" ContentType="application/xml"/>
<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>
<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>
</Types>"""
_DOCX_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>"""
_DOCX_DOC_RELS = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>
</Relationships>"""
# Calibri 11 pt, 8 pt after each paragraph: what a new Word document looks like.
_DOCX_STYLES = """<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:docDefaults>
<w:rPrDefault><w:rPr><w:rFonts w:ascii="Calibri" w:hAnsi="Calibri" w:cs="Calibri" w:eastAsia="Calibri"/><w:sz w:val="22"/><w:szCs w:val="22"/></w:rPr></w:rPrDefault>
<w:pPrDefault><w:pPr><w:spacing w:after="160" w:line="276" w:lineRule="auto"/></w:pPr></w:pPrDefault>
</w:docDefaults>
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/></w:style>
</w:styles>"""


def write_docx(path: Path, text: str) -> None:
    body = []
    for lines in _paragraphs(text):
        runs = '<w:r><w:br/></w:r>'.join(f'<w:r><w:t xml:space="preserve">{escape(line)}</w:t></w:r>' for line in lines)
        body.append(f"<w:p>{runs}</w:p>")
    document = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body>'
                + "".join(body) +
                '<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
                '<w:pgMar w:top="1440" w:right="1440" w:bottom="1440" w:left="1440" w:header="708" w:footer="708" w:gutter="0"/>'
                "</w:sectPr></w:body></w:document>")
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", _DOCX_TYPES)
        z.writestr("_rels/.rels", _DOCX_RELS)
        z.writestr("word/_rels/document.xml.rels", _DOCX_DOC_RELS)
        z.writestr("word/styles.xml", _DOCX_STYLES)
        z.writestr("word/document.xml", document)


def _pdf_font() -> str:
    """Arial from Windows (any script it covers), else the built-in Helvetica (Latin only)."""
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont

    if "JobLensArial" in pdfmetrics.getRegisteredFontNames():
        return "JobLensArial"
    arial = Path(r"C:\Windows\Fonts\arial.ttf")
    try:
        pdfmetrics.registerFont(TTFont("JobLensArial", str(arial)))
        return "JobLensArial"
    except Exception:
        return "Helvetica"


def write_pdf(path: Path, text: str, title: str = "Cover note") -> None:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.units import cm
    from reportlab.platypus import Paragraph, SimpleDocTemplate

    style = ParagraphStyle("note", fontName=_pdf_font(), fontSize=11, leading=15.5, spaceAfter=9)
    doc = SimpleDocTemplate(str(path), pagesize=A4, leftMargin=2.5 * cm, rightMargin=2.5 * cm,
                            topMargin=2.5 * cm, bottomMargin=2.5 * cm, title=title, author="", creator="JobLens")
    doc.build([Paragraph("<br/>".join(escape(line) for line in lines), style) for lines in _paragraphs(text)])


def export_cover_note(path: Path, fmt: str, text: str, title: str = "Cover note") -> None:
    if fmt not in FORMATS:
        raise ValueError(f"Format must be one of {', '.join(FORMATS)}")
    {"txt": write_txt, "docx": write_docx, "pdf": lambda p, t: write_pdf(p, t, title)}[fmt](Path(path), text)


def tracker_file_name() -> str:
    return file_name("JobLens jobs", date.today().isoformat(), ext="csv")
