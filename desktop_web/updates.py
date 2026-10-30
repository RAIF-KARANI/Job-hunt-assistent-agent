"""
The update check (13b, D26): is there a newer JobLens on GitHub Releases?

    at most once a day, in the background after the window opened
    GET https://api.github.com/repos/<repo>/releases/latest   (public, no account)
    newer than __version__?  -> "Update available: v1.0.0" in the sidebar

What GitHub sees: one request with the User-Agent "JobLens/<version>". No
personal data, no device id. The answer is cached in update_check.json in
the data folder; after a network error the next try is an hour later.
Drafts and pre-releases are never offered (the "latest" endpoint skips them).

The rules are pure functions (parse_version, pick_installer, check_due),
so they're tested without the network (tests/test_updates.py). 13d will
download the installer named here and check it against `sha256`.
"""

import json
import os
import re
import time
from pathlib import Path

REPO = "RAIF-KARANI/Job-hunt-assistent-agent"
LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"
RELEASES_PAGE = f"https://github.com/{REPO}/releases"
CHECK_EVERY = 24 * 3600      # seconds: once a day
RETRY_AFTER_ERROR = 3600     # an hour, so a PC without internet doesn't ask at every start

_VERSION = re.compile(r"^v?(\d+)\.(\d+)\.(\d+)$")


def parse_version(text: str) -> tuple[int, int, int] | None:
    """'v1.2.3' / '1.2.3' -> (1, 2, 3); anything else (e.g. '1.0.0-rc1') -> None."""
    match = _VERSION.match((text or "").strip())
    return tuple(int(part) for part in match.groups()) if match else None


def is_newer(latest: str, current: str) -> bool:
    a, b = parse_version(latest), parse_version(current)
    return bool(a and b and a > b)


def pick_installer(release: dict) -> dict | None:
    """The release's installer: JobLens-Setup-<version>.exe (not the portable
    zip, not a test build), with its size and SHA-256 for 13d's check."""
    version = (release.get("tag_name") or "").lstrip("v")
    for asset in release.get("assets") or []:
        if asset.get("name") == f"JobLens-Setup-{version}.exe":
            digest = asset.get("digest") or ""
            return {"name": asset["name"], "size": int(asset.get("size") or 0),
                    "url": asset.get("browser_download_url"),
                    "sha256": digest.split(":", 1)[1] if digest.startswith("sha256:") else None}
    return None


def summarize(release: dict, current: str) -> dict:
    """What the app keeps and shows: plain data, no raw API response."""
    latest = (release.get("tag_name") or "").strip()
    return {"current": current, "latest": latest, "newer": is_newer(latest, current),
            "name": release.get("name") or latest, "page": release.get("html_url") or RELEASES_PAGE,
            "published_at": release.get("published_at"), "notes": (release.get("body") or "")[:4000],
            "installer": pick_installer(release)}


def check_due(saved: dict | None, now: float, current: str) -> bool:
    """Ask GitHub again? Not if the last answer is fresh, unless the app was
    updated since (then the cached "newer" is stale)."""
    if not saved:
        return True
    if saved.get("current") != current:
        return True
    wait = RETRY_AFTER_ERROR if saved.get("error") else CHECK_EVERY
    return now - float(saved.get("checked_at") or 0) >= wait


# ---------------------------------------------------------------------------
# The check itself (network + the cache file)
# ---------------------------------------------------------------------------


def _fetch(current: str) -> dict:
    import requests

    r = requests.get(LATEST_URL, timeout=10,
                     headers={"Accept": "application/vnd.github+json", "User-Agent": f"JobLens/{current}"})
    if r.status_code == 404:
        return {}  # no published release yet
    r.raise_for_status()
    return r.json()


class UpdateChecker:
    def __init__(self, folder: Path, current: str, fetch=None, clock=time.time):
        self.file = folder / "update_check.json"
        self.current = current
        self._fetch = fetch or _fetch
        self._clock = clock

    def saved(self) -> dict | None:
        try:
            return json.loads(self.file.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None

    def status(self) -> dict:
        """The last known answer, without asking GitHub."""
        saved = self.saved()
        if not saved or saved.get("current") != self.current:
            return {"current": self.current, "latest": None, "newer": False, "checked_at": None, "error": None}
        return saved

    def check(self, force: bool = False) -> dict:
        """Ask GitHub if it's time (or `force`); never raises."""
        now = self._clock()
        if not force and not check_due(self.saved(), now, self.current):
            return self.status()
        try:
            release = self._fetch(self.current)
            result = {**summarize(release, self.current), "error": None} if release else \
                {"current": self.current, "latest": None, "newer": False, "error": None}
        except Exception as e:  # offline, GitHub down, rate limit: try again later
            result = {**(self.status()), "error": f"{type(e).__name__}: {str(e)[:200]}"}
        result["checked_at"] = now
        try:
            self.file.parent.mkdir(parents=True, exist_ok=True)
            self.file.write_text(json.dumps(result, indent=2), encoding="utf-8")
        except OSError:
            pass
        return result


# ---------------------------------------------------------------------------
# 13d: download, verify, install (D27)
# ---------------------------------------------------------------------------

DOWNLOAD_PREFIX = f"https://github.com/{REPO}/releases/download/"
_INSTALLER_NAME = re.compile(r"^JobLens-Setup-\d+\.\d+\.\d+\.exe$")


class UpdateRefused(RuntimeError):
    """The download isn't what GitHub published (or isn't from GitHub): never run it."""


def check_source(installer: dict) -> None:
    """Only this repo's release downloads, only a file named like our
    installer, and only with a published SHA-256. Checked before downloading."""
    name, url = installer.get("name") or "", installer.get("url") or ""
    if not _INSTALLER_NAME.match(name):
        raise UpdateRefused(f"'{name}' isn't a JobLens installer.")
    if not (url.startswith(DOWNLOAD_PREFIX) and url.endswith("/" + name)):
        raise UpdateRefused("The download isn't on JobLens' GitHub releases.")
    if not re.fullmatch(r"[0-9a-f]{64}", installer.get("sha256") or ""):
        raise UpdateRefused("GitHub publishes no checksum for this file: download it from the release page instead.")


def sha256_of(path: Path) -> str:
    import hashlib

    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def verify(path: Path, installer: dict) -> None:
    """Size and SHA-256 must both match what GitHub published."""
    size = path.stat().st_size
    if installer.get("size") and size != installer["size"]:
        raise UpdateRefused(f"The download has {size:,} bytes, GitHub says {installer['size']:,}.")
    if sha256_of(path) != installer["sha256"]:
        raise UpdateRefused("The download's SHA-256 doesn't match the one GitHub published.")


def download(installer: dict, folder: Path, progress=None, get=None) -> Path:
    """Fetch the installer to `folder`, verify it, and return its path. A
    file that fails a check is deleted. `progress(done, total)` while it runs."""
    check_source(installer)
    if get is None:
        import requests
        get = requests.get
    folder.mkdir(parents=True, exist_ok=True)
    final = folder / installer["name"]
    part = folder / (installer["name"] + ".part")
    try:
        with get(installer["url"], stream=True, timeout=(10, 60)) as r:  # follows GitHub's redirect
            r.raise_for_status()
            total, done = installer.get("size") or int(r.headers.get("Content-Length") or 0), 0
            with open(part, "wb") as f:
                for chunk in r.iter_content(1 << 16):
                    f.write(chunk)
                    done += len(chunk)
                    if progress:
                        progress(done, total)
        verify(part, installer)
        part.replace(final)
        return final
    finally:
        part.unlink(missing_ok=True)  # a failed or refused download leaves nothing behind


def launch_installer(path: Path, installer: dict, run=None) -> None:
    """Check the file once more (it sat on disk since the download), then start
    it detached, silently: Inno Setup upgrades in place (same AppId, your
    data untouched) and starts the new JobLens when it's done (/RELAUNCH=1)."""
    verify(path, installer)
    import subprocess

    flags = getattr(subprocess, "DETACHED_PROCESS", 0) | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0)
    log = path.with_name("install.log")  # what the installer did, for troubleshooting
    (run or subprocess.Popen)([str(path), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH=1",
                               f"/LOG={log}"], creationflags=flags, close_fds=True)


def clean_downloads(folder: Path, keep: str | None = None) -> None:
    """Delete old installers (after an update they're no longer needed)."""
    if folder.exists():
        for f in folder.iterdir():
            if f.name != keep:
                f.unlink(missing_ok=True)


def enabled() -> bool:
    """The UPDATE_CHECK setting (on by default; the switch is in Settings, 13c)."""
    return os.getenv("UPDATE_CHECK", "true").lower() != "false"
