"""
Phase 1: read a job posting.

Two separate steps, on purpose:
  1. fetch_page_text()     -> plain Python, no AI. Download HTML, keep the text.
  2. extract_job_posting() -> the LLM turns messy text into a JobPosting.

Rule of thumb for agents: use normal code for anything deterministic
(downloading, parsing, saving) and the LLM only for the "understanding" part.
It's cheaper, faster and far more reliable.
"""

import requests
from bs4 import BeautifulSoup
from langchain_core.messages import HumanMessage, SystemMessage

from job_agent.llm import get_llm
from job_agent.models import JobPosting

# Some sites block requests that don't look like a browser.
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/130.0 Safari/537.36"
    )
}

# Keep the prompt within the model's context window (~4 chars per token).
MAX_CHARS = 30_000


def fetch_page_text(url: str) -> str:
    """Download a web page and return only its readable text."""
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()  # turn 404/403/500 into a Python error

    soup = BeautifulSoup(response.text, "html.parser")

    # Remove parts that are never job content: code, styling, menus, footers.
    for tag in soup(["script", "style", "noscript", "nav", "footer", "header", "svg"]):
        tag.decompose()

    # One line per text block, dropping empty lines.
    lines = (line.strip() for line in soup.get_text(separator="\n").splitlines())
    text = "\n".join(line for line in lines if line)

    if len(text) < 200:
        # Usually means the page is built by JavaScript or behind a login.
        raise ValueError(
            "Page returned almost no text (JavaScript-only or login-protected). "
            "Copy the job description into a .txt file and use that instead."
        )
    return text[:MAX_CHARS]


SYSTEM_PROMPT = """You extract structured data from job postings.
Rules:
- Use ONLY information present in the text. Never invent details.
- If a field is not mentioned, write 'Not specified' (or an empty list).
- Ignore unrelated page content: cookie banners, other job listings, ads."""


def extract_job_posting(page_text: str) -> JobPosting:
    """Ask the LLM to fill in the JobPosting form from raw page text."""
    # with_structured_output() sends the JobPosting schema to the model and
    # parses its reply back into a JobPosting object (or raises if invalid).
    structured_llm = get_llm().with_structured_output(JobPosting)

    return structured_llm.invoke(
        [
            SystemMessage(content=SYSTEM_PROMPT),
            HumanMessage(content=f"Job posting text:\n\n{page_text}"),
        ]
    )
