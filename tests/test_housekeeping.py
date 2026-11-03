"""15h: leftover WebView2 profiles in %TEMP% and old checkpoints."""

import os
import sqlite3
import time

from desktop_web import housekeeping


def make_profile(root, name, age_hours, extra=None):
    folder = root / name / "EBWebView" / "Default"
    folder.mkdir(parents=True)
    f = folder / "Cache.bin"
    f.write_bytes(b"x" * 1000)
    if extra:
        (root / name / extra).write_text("other app")
    old = time.time() - age_hours * 3600
    for p in [f, folder, folder.parent, folder.parent.parent]:
        os.utime(p, (old, old))
    return root / name


def test_only_old_pywebview_profiles_are_removed(tmp_path):
    old = make_profile(tmp_path, "tmpabc123", age_hours=48)
    fresh = make_profile(tmp_path, "tmpdef456", age_hours=1)           # maybe in use
    mixed = make_profile(tmp_path, "tmpghi789", age_hours=48, extra="notes.txt")  # not only EBWebView
    other = tmp_path / "SomeAppCache" / "EBWebView"
    other.mkdir(parents=True)
    removed, freed = housekeeping.clean_webview_temp(tmp_path)
    assert (removed, freed) == (1, 1000)
    assert not old.exists() and fresh.exists() and mixed.exists() and other.exists()


def make_dbs(tmp_path, runs, threads):
    jobs, cp = tmp_path / "jobs.db", tmp_path / "checkpoints.db"
    with sqlite3.connect(jobs) as db:
        db.execute("CREATE TABLE runs (run_id TEXT, started_at TEXT, interface TEXT)")
        db.executemany("INSERT INTO runs VALUES (?, ?, ?)", runs)
    with sqlite3.connect(cp) as db:
        db.execute("CREATE TABLE checkpoints (thread_id TEXT, checkpoint BLOB)")
        db.execute("CREATE TABLE writes (thread_id TEXT, value BLOB)")
        for t in threads:
            db.executemany("INSERT INTO checkpoints VALUES (?, ?)", [(t, b"y" * 5000)] * 20)
            db.execute("INSERT INTO writes VALUES (?, ?)", (t, b"z" * 2000))
    return jobs, cp


def threads_left(cp):
    with sqlite3.connect(cp) as db:
        return {r[0] for r in db.execute("SELECT DISTINCT thread_id FROM checkpoints")} | \
               {r[0] for r in db.execute("SELECT DISTINCT thread_id FROM writes")}


def test_only_the_latest_desktop_run_and_other_interfaces_are_kept(tmp_path):
    runs = [("old1", "2026-11-01 10:00", "desktop"), ("old2", "2026-11-02 10:00", "desktop"),
            ("latest", "2026-11-03 10:00", "desktop"), ("web1", "2026-10-30 10:00", "web")]
    jobs, cp = make_dbs(tmp_path, runs, ["old1", "old2", "latest", "web1", "not-in-the-log"])
    result = housekeeping.prune_checkpoints(cp, jobs)
    assert result["runs_removed"] == 2
    assert threads_left(cp) == {"latest", "web1", "not-in-the-log"}
    assert result["bytes_after"] < result["bytes_before"]


def test_a_run_in_progress_is_kept(tmp_path):
    runs = [("running", "2026-11-02 10:00", "desktop"), ("newer", "2026-11-03 10:00", "desktop")]
    jobs, cp = make_dbs(tmp_path, runs, ["running", "newer"])
    housekeeping.prune_checkpoints(cp, jobs, keep={"running"})
    assert threads_left(cp) == {"running", "newer"}


def test_no_databases_yet_is_fine(tmp_path):
    assert housekeeping.prune_checkpoints(tmp_path / "none.db", tmp_path / "jobs.db")["runs_removed"] == 0


def test_a_run_while_langfuse_is_down_is_not_traced_and_says_so(monkeypatch):
    # 3 Nov: 40 runs were saved as "langfuse" while it was down; their links
    # said "Session not found", and the SDK kept retrying in the background.
    import requests

    from job_agent import tracing

    def refused(url, timeout):
        raise requests.ConnectionError("refused")
    monkeypatch.setattr(tracing, "TRACING", "langfuse")
    monkeypatch.setattr(tracing, "_reachable", {"at": 0.0, "ok": False})
    monkeypatch.setattr(requests, "get", refused)
    config = tracing.tracing_config("run-1", "desktop")
    assert len(config["callbacks"]) == 1                  # only the local run log
    assert config["callbacks"][0].tracing == tracing.LANGFUSE_DOWN
    assert "metadata" not in config

    class Up:
        status_code = 200
    monkeypatch.setattr(requests, "get", lambda url, timeout: Up())
    monkeypatch.setattr(tracing, "_reachable", {"at": 0.0, "ok": False})
    assert tracing.langfuse_reachable() is True
