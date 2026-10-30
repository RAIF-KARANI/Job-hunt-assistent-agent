"""
Test-wide setup: tests must not depend on the developer's own .env.

In developer mode the app reads the repo's .env (paths.py). Since the
settings fix of 31 Oct 2026 that file really applies (before, the defaults
silently won), so a developer's TRACING=langfuse would make every agent
test try to reach a Langfuse server. A real environment variable beats the
.env file, so pinning it here, before any job_agent module is imported
(job_agent/tracing.py reads TRACING once, at import), keeps the tests the
same on every PC. Tests that need another value use monkeypatch as usual.
"""

import os

os.environ["TRACING"] = "off"
os.environ.setdefault("UPDATE_CHECK", "false")  # tests never ask GitHub on their own
