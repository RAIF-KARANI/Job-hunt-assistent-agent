"""
Phase 2a: load resumes from the data/ folder.

Plain code, no AI: PDF -> text. Every *.pdf in data/ is treated as a resume,
so adding a third resume later needs no code change.
"""

from pathlib import Path

from pypdf import PdfReader

from job_agent.paths import DATA_DIR  # one place decides where files live (Phase 9a)


def load_resumes(folder: Path = DATA_DIR) -> dict[str, str]:
    """Return {resume_name: resume_text} for every PDF in the folder."""
    resumes = {}
    for pdf_path in sorted(folder.glob("*.pdf")):
        reader = PdfReader(pdf_path)
        text = "\n".join(page.extract_text() or "" for page in reader.pages)
        if text.strip():
            # Use the file name without ".pdf" as a readable label.
            resumes[pdf_path.stem] = text
        else:
            # Scanned/image PDFs have no text layer; they'd need OCR.
            print(f"  ! Skipping {pdf_path.name}: no extractable text")

    if not resumes:
        raise FileNotFoundError(f"No readable resume PDFs found in {folder}")
    return resumes


# ---------------------------------------------------------------------------
# 14b: which resumes to compare with a job (D28)
# ---------------------------------------------------------------------------

SEPARATOR = "|"  # can't appear in a Windows file name


def default_choice() -> list[str]:
    """The default set from Settings (RESUMES_DEFAULT); [] = all of them."""
    import os

    return [n for n in os.getenv("RESUMES_DEFAULT", "").split(SEPARATOR) if n.strip()]


def choose_resumes(resumes: dict[str, str], wanted: list[str] | None) -> tuple[dict[str, str], str | None]:
    """The resumes to score for this run, and a note if the choice had to change.

    `wanted`: file names ("CV.pdf") or labels ("CV") picked for this job;
    None = the default set from Settings; an empty set = all. Resumes that
    no longer exist are skipped; if none of the wanted ones exist, all are
    used, with a note saying so (never fail silently).
    """
    names = default_choice() if wanted is None else list(wanted)
    if not names:
        return resumes, None
    labels = {Path(n).stem if n.lower().endswith(".pdf") else n for n in names}
    picked = {label: text for label, text in resumes.items() if label in labels}
    if not picked:
        return resumes, "none of the chosen resumes exist any more: comparing with all of them"
    missing = labels - set(picked)
    note = f"skipped (not found): {', '.join(sorted(missing))}" if missing else None
    return picked, note
