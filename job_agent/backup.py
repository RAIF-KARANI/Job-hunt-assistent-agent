"""
19a (E7): back up everything you'd hate to lose, and put it back.

One .zip file:

    joblens-backup.json   what's inside (app, format, version, counts)
    jobs.db               the tracker + run log, a consistent snapshot
    settings.env          your settings WITHOUT API keys (E7: a backup is
                          a file you may copy anywhere; keys stay in .env)
    resumes/*.pdf         the resumes in the data folder
    cover_notes/*.md      the approved cover notes

Left out on purpose: paused runs (checkpoints.db: only the last run can be
continued, D30, and it's large), eval files, the WebView profile.

Restore is careful because the file may come from anywhere:
    - only the names above are accepted (no folders, no "..", no other files);
    - jobs.db must be a healthy SQLite file with a jobs table;
    - the unpacked size is capped (a "zip bomb" can't fill the disk);
    - settings: only known, non-secret keys, and no line breaks;
    - what's there NOW is backed up first ("before restore"), so a restore
      can itself be undone; then the files are replaced.

Automatic backups (in APP_HOME/backups, the last KEEP are kept): once a week
at start, and before an update installs. NO LLM here. Tests: tests/test_backup.py.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timedelta
from pathlib import Path, PurePosixPath

from job_agent import __version__, paths, providers, settings, tracker

MANIFEST = "joblens-backup.json"
FORMAT = 1                      # bump when the layout changes; newer formats are refused
KEEP = 4                        # automatic backups kept
AUTO_DAYS = 7                   # weekly
MAX_UNPACKED = 1_000_000_000    # 1 GB: far above any real tracker + resumes
SECRETS = (*providers.KEY_NAMES, "LANGFUSE_SECRET_KEY", "LANGSMITH_API_KEY")
REASONS = ("weekly", "before update", "before restore")


class BackupError(ValueError):
    """A file that can't be restored: the message says why, for the page."""


def backup_dir() -> Path:
    return paths.APP_HOME / "backups"


def file_name(when: datetime | None = None) -> str:
    return f"JobLens backup {(when or datetime.now()):%Y-%m-%d}.zip"


# ---------------------------------------------------------------------------
# Making a backup
# ---------------------------------------------------------------------------


def _resumes() -> list[Path]:
    return sorted(paths.DATA_DIR.glob("*.pdf"), key=lambda p: p.name.lower()) if paths.DATA_DIR.exists() else []


def _notes() -> list[Path]:
    folder = paths.NOTES_DIR
    return sorted(folder.glob("*.md")) if folder.exists() else []


def _settings_text() -> str:
    """The .env without secrets (and without empty lines or comments)."""
    if not settings.ENV_FILE.exists():
        return ""
    from dotenv import dotenv_values

    values = dotenv_values(settings.ENV_FILE)
    return "".join(f"{k}={v}\n" for k, v in values.items()
                   if v is not None and k not in SECRETS)


def _snapshot(dest: Path) -> int:
    """Copy jobs.db with SQLite's own backup (consistent even mid-write).
    Returns the number of jobs (0 when there's no tracker yet)."""
    if not tracker.DB_PATH.exists():
        return 0
    src = sqlite3.connect(tracker.DB_PATH)
    out = sqlite3.connect(dest)
    try:
        src.backup(out)
        try:
            return out.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        except sqlite3.OperationalError:
            return 0
    finally:
        out.close()
        src.close()


def create(dest: Path, reason: str = "manual") -> dict:
    """Write a backup to `dest`. Returns its manifest (+ the path)."""
    dest = Path(dest)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        db = Path(tmp) / "jobs.db"
        jobs = _snapshot(db)
        resumes, notes = _resumes(), _notes()
        manifest = {"app": "JobLens", "format": FORMAT, "version": __version__,
                    "created": datetime.now().isoformat(timespec="seconds"), "reason": reason,
                    "jobs": jobs, "resumes": [p.name for p in resumes], "cover_notes": len(notes)}
        part = dest.with_name(dest.name + ".part")  # never a half-written .zip under the real name
        with zipfile.ZipFile(part, "w", zipfile.ZIP_DEFLATED) as z:
            z.writestr(MANIFEST, json.dumps(manifest, indent=2))
            if db.exists():
                z.write(db, "jobs.db")
            z.writestr("settings.env", _settings_text())
            for p in resumes:
                z.write(p, f"resumes/{p.name}")
            for p in notes:
                z.write(p, f"cover_notes/{p.name}")
        os.replace(part, dest)
    return {**manifest, "path": str(dest)}


# ---------------------------------------------------------------------------
# Checking a backup
# ---------------------------------------------------------------------------

_SAFE_NAME = re.compile(r"^[^<>:\"/\\|?*\x00-\x1f]{1,200}$")
_RESERVED = {"CON", "PRN", "AUX", "NUL", *(f"COM{i}" for i in range(1, 10)), *(f"LPT{i}" for i in range(1, 10))}


def _allowed(name: str) -> bool:
    """Only the files a backup is made of, each a plain file name Windows accepts."""
    if name in (MANIFEST, "jobs.db", "settings.env"):
        return True
    if "\\" in name or name.startswith("/"):
        return False
    parts = name.split("/")
    if len(parts) != 2:
        return False
    folder, leaf = parts
    if (not _SAFE_NAME.match(leaf) or leaf != leaf.strip() or leaf.endswith(".")
            or leaf.split(".")[0].upper() in _RESERVED):
        return False
    return (folder == "resumes" and leaf.lower().endswith(".pdf")) or \
           (folder == "cover_notes" and leaf.lower().endswith(".md"))


def _check_db(path: Path) -> int:
    """A healthy SQLite file with a jobs table; returns the number of jobs."""
    try:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            if conn.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise BackupError("The tracker in this backup is damaged.")
            return conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        finally:
            conn.close()
    except sqlite3.DatabaseError as e:
        raise BackupError("The tracker in this backup can't be read.") from e


def inspect(path: Path) -> dict:
    """What's in a backup, or BackupError saying why it can't be restored."""
    try:
        z = zipfile.ZipFile(path)
    except (zipfile.BadZipFile, OSError) as e:
        raise BackupError("This isn't a JobLens backup (not a readable .zip file).") from e
    with z:
        infos = z.infolist()
        names = [i.filename for i in infos if not i.is_dir()]
        if MANIFEST not in names:
            raise BackupError("This isn't a JobLens backup (joblens-backup.json is missing).")
        strange = [n for n in names if not _allowed(n)]
        if strange:
            raise BackupError(f"This backup holds files JobLens doesn't make ({strange[0]}), so it isn't restored.")
        if len(set(names)) != len(names):
            raise BackupError("This backup holds the same file twice, so it isn't restored.")
        if sum(i.file_size for i in infos) > MAX_UNPACKED:
            raise BackupError("This backup is too large to be a JobLens backup.")
        try:
            manifest = json.loads(z.read(MANIFEST))
        except ValueError as e:
            raise BackupError("This backup's joblens-backup.json can't be read.") from e
    if not isinstance(manifest, dict) or manifest.get("app") != "JobLens":
        raise BackupError("This isn't a JobLens backup.")
    if not isinstance(manifest.get("format"), int) or manifest["format"] > FORMAT:
        raise BackupError(f"This backup was made by a newer JobLens ({manifest.get('version', '?')}). Update JobLens first.")
    return {"created": str(manifest.get("created", "")), "version": str(manifest.get("version", "")),
            "jobs": int(manifest.get("jobs") or 0), "has_tracker": "jobs.db" in names,
            "resumes": sorted(PurePosixPath(n).name for n in names if n.startswith("resumes/")),
            "cover_notes": sum(1 for n in names if n.startswith("cover_notes/"))}


# ---------------------------------------------------------------------------
# Restoring
# ---------------------------------------------------------------------------


def _settings_from(text: str, allowed: set[str]) -> dict:
    out = {}
    for line in text.splitlines():
        key, sep, value = line.partition("=")
        key, value = key.strip(), value.strip()
        if not sep or key in SECRETS or key not in allowed:
            continue
        if any(ord(ch) < 32 for ch in value) or len(value) > 2000:
            continue
        out[key] = value
    return out


def restore(path: Path, allowed_settings: set[str]) -> dict:
    """Replace the tracker, resumes, cover notes and settings with the
    backup's. What's there now is backed up first. API keys are kept."""
    info = inspect(path)
    paths.ensure_dirs()
    before = auto_backup("before restore")  # so this can be undone
    with tempfile.TemporaryDirectory(dir=paths.APP_HOME) as tmp:
        tmp = Path(tmp)
        with zipfile.ZipFile(path) as z:
            for name in z.namelist():
                if name.endswith("/"):
                    continue
                target = tmp.joinpath(*PurePosixPath(name).parts)  # names were checked by inspect()
                target.parent.mkdir(parents=True, exist_ok=True)
                with z.open(name) as src, open(target, "wb") as out:
                    shutil.copyfileobj(src, out)
        if info["has_tracker"]:
            jobs = _check_db(tmp / "jobs.db")
        else:
            jobs = 0
        # Everything is checked and unpacked: now replace, the tracker first.
        if info["has_tracker"]:
            for extra in ("-wal", "-shm", "-journal"):
                Path(str(tracker.DB_PATH) + extra).unlink(missing_ok=True)
            os.replace(tmp / "jobs.db", tracker.DB_PATH)
        else:
            tracker.DB_PATH.unlink(missing_ok=True)
        for old in _resumes():
            old.unlink()
        for new in sorted((tmp / "resumes").glob("*.pdf")) if (tmp / "resumes").exists() else []:
            os.replace(new, paths.DATA_DIR / new.name)
        notes = paths.NOTES_DIR
        if notes.exists():
            shutil.rmtree(notes)
        if (tmp / "cover_notes").exists():
            shutil.move(str(tmp / "cover_notes"), str(notes))
        restored = {}
        if (tmp / "settings.env").exists():
            restored = _settings_from((tmp / "settings.env").read_text(encoding="utf-8", errors="replace"),
                                      allowed_settings)
            if restored:
                settings.save_settings(restored)
    from job_agent import runlog

    runlog.init_db()  # an older backup gets today's columns (tracker + run log)
    return {**info, "jobs": jobs, "settings": len(restored), "before": str(before) if before else None}


# ---------------------------------------------------------------------------
# Automatic backups
# ---------------------------------------------------------------------------


def automatic() -> list[Path]:
    """The automatic backups, newest first."""
    folder = backup_dir()
    return sorted(folder.glob("auto *.zip"), key=lambda p: p.stat().st_mtime, reverse=True) if folder.exists() else []


def auto_backup(reason: str) -> Path | None:
    """Back up into APP_HOME/backups and keep the newest KEEP. None when
    there's nothing to back up yet (a brand-new install)."""
    if reason not in REASONS:
        raise ValueError(f"Unknown reason '{reason}'")
    if not tracker.DB_PATH.exists() and not _resumes():
        return None
    when, n = datetime.now(), 1
    dest = backup_dir() / f"auto {when:%Y-%m-%d %H%M%S} {reason}.zip"
    while dest.exists():  # two in the same second (an update right after the weekly one)
        n += 1
        dest = backup_dir() / f"auto {when:%Y-%m-%d %H%M%S}-{n} {reason}.zip"
    create(dest, reason)
    for old in automatic()[KEEP:]:
        old.unlink(missing_ok=True)
    return dest


def auto_backup_if_due(now: datetime | None = None) -> Path | None:
    """Once a week: when the newest automatic backup is AUTO_DAYS old (or there's none)."""
    newest = automatic()[:1]
    now = now or datetime.now()
    if newest and now - datetime.fromtimestamp(newest[0].stat().st_mtime) < timedelta(days=AUTO_DAYS):
        return None
    return auto_backup("weekly")


def status() -> dict:
    """For Settings: the last automatic backup and where they are."""
    autos = automatic()
    last = autos[0] if autos else None
    return {"folder": str(backup_dir()), "count": len(autos), "keep": KEEP,
            "last": datetime.fromtimestamp(last.stat().st_mtime).isoformat(timespec="minutes") if last else None,
            "last_reason": last.stem.split(" ", 3)[-1] if last else None}
