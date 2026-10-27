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
