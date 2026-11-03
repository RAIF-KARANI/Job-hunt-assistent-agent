"""
15h: what JobLens leaves on disk.

1. WebView2 profiles in %TEMP%. pywebview's default "private mode" makes a
   new temporary browser profile at every start and tries to delete it at
   exit, which fails while WebView2's helper processes still hold its files:
   20 folders, 162 MB, on 3 Nov. JobLens now uses one fixed profile in its
   own folder (`WEBVIEW_DIR`), and removes the old leftovers once they are a
   day old (`clean_webview_temp`, installed app only).
2. checkpoints.db keeps every run's saved state forever (43 runs, 713
   checkpoints, 8.5 MB with its log on 3 Nov), though only the latest run
   can be continued (D30). `prune_checkpoints` keeps the latest desktop run
   (and any other interface's runs) and compacts the file, at exit.
"""

from __future__ import annotations

import shutil
import sqlite3
import tempfile
import time
from pathlib import Path

from job_agent import paths

WEBVIEW_DIR = paths.APP_HOME / "webview"  # the one browser profile (cache, local storage)


def folder_size(folder: Path) -> int:
    return sum(f.stat().st_size for f in folder.rglob("*") if f.is_file())


def clean_webview_temp(temp_dir: Path | None = None, min_age_hours: float = 24) -> tuple[int, int]:
    """Delete leftover pywebview profiles: %TEMP%\\tmpXXXX folders that hold
    nothing but an EBWebView folder and haven't changed for a day (one in use
    by a running copy changes all the time, and is locked anyway).
    Returns (folders removed, bytes freed)."""
    temp_dir = Path(temp_dir or tempfile.gettempdir())
    removed = freed = 0
    cutoff = time.time() - min_age_hours * 3600
    for folder in temp_dir.glob("tmp*"):
        try:
            if not folder.is_dir() or [c.name for c in folder.iterdir()] != ["EBWebView"]:
                continue
            if max((f.stat().st_mtime for f in folder.rglob("*")), default=folder.stat().st_mtime) > cutoff:
                continue
            size = folder_size(folder)
            shutil.rmtree(folder, ignore_errors=True)
            if not folder.exists():
                removed, freed = removed + 1, freed + size
        except OSError:
            continue  # vanished or locked: leave it
    return removed, freed


def _desktop_runs(jobs_db: Path) -> list[str]:
    """Desktop run ids, newest first (from the run log)."""
    if not jobs_db.exists():
        return []
    with sqlite3.connect(jobs_db) as db:
        try:
            rows = db.execute("SELECT run_id FROM runs WHERE interface = 'desktop' "
                              "ORDER BY started_at DESC").fetchall()
        except sqlite3.OperationalError:  # no run log yet
            return []
    return [r[0] for r in rows]


def prune_checkpoints(checkpoint_db: Path | None = None, jobs_db: Path | None = None,
                      keep: set[str] | None = None) -> dict:
    """Delete the saved state of desktop runs that can't be continued any more:
    every desktop run except the newest one and those in `keep`. Runs from
    other interfaces (the web UI) are left alone. Then compact the file."""
    checkpoint_db = Path(checkpoint_db or paths.CHECKPOINT_DB)
    jobs_db = Path(jobs_db or paths.DB_PATH)
    if not checkpoint_db.exists():
        return {"runs_removed": 0, "bytes_before": 0, "bytes_after": 0}
    wal = checkpoint_db.with_name(checkpoint_db.name + "-wal")
    before = checkpoint_db.stat().st_size + (wal.stat().st_size if wal.exists() else 0)
    desktop = _desktop_runs(jobs_db)
    old = set(desktop[1:]) - set(keep or ())
    with sqlite3.connect(checkpoint_db, timeout=10) as db:
        tables = {r[0] for r in db.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
        stored = {r[0] for r in db.execute("SELECT DISTINCT thread_id FROM checkpoints")} \
            if "checkpoints" in tables else set()
        doomed = sorted(stored & old)
        for table in ("checkpoints", "writes"):
            if table in tables and doomed:
                db.executemany(f"DELETE FROM {table} WHERE thread_id = ?", [(t,) for t in doomed])
        db.commit()
    db = sqlite3.connect(checkpoint_db, timeout=10, isolation_level=None)  # VACUUM can't run in a transaction
    try:
        if doomed:
            db.execute("VACUUM")
        # After VACUUM: in WAL mode the compacted pages go to the -wal file
        # first, so it must be folded back into the database (and emptied).
        db.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    finally:
        db.close()
    after = checkpoint_db.stat().st_size + (wal.stat().st_size if wal.exists() else 0)
    return {"runs_removed": len(doomed), "bytes_before": before, "bytes_after": after}
