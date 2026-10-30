"""
Tests for the update check (13b). GitHub is replaced by a stand-in, so no
network is used; the release data has the shape the real API returns.
"""

import json
import threading

import pytest

from desktop_web import updates
from desktop_web.updates import UpdateChecker, check_due, is_newer, parse_version, pick_installer


def release(tag="v1.0.0", assets=None):
    version = tag.lstrip("v")
    return {
        "tag_name": tag, "name": f"JobLens {tag}", "prerelease": False, "draft": False,
        "html_url": f"https://github.com/{updates.REPO}/releases/tag/{tag}",
        "published_at": "2026-11-05T10:00:00Z", "body": "What's new...",
        "assets": assets if assets is not None else [
            {"name": f"JobLens-v{version}-windows-x64-portable.zip", "size": 71, "digest": "sha256:aa",
             "browser_download_url": "https://x/zip"},
            {"name": f"JobLens-Setup-{version}.exe", "size": 57793533, "digest": "sha256:70114c39",
             "browser_download_url": f"https://github.com/{updates.REPO}/releases/download/{tag}/JobLens-Setup-{version}.exe"},
        ],
    }


@pytest.mark.parametrize("text, parsed", [("v1.2.3", (1, 2, 3)), ("0.3.1", (0, 3, 1)), (" v10.0.0 ", (10, 0, 0)),
                                          ("1.0.0-rc1", None), ("latest", None), ("", None), (None, None)])
def test_versions(text, parsed):
    assert parse_version(text) == parsed


@pytest.mark.parametrize("latest, current, newer", [
    ("v1.0.0", "0.3.1", True), ("v0.3.10", "0.3.9", True),   # numbers, not text: 10 > 9
    ("v0.3.1", "0.3.1", False), ("v0.3.0", "0.3.1", False),
    ("v1.0.0-rc1", "0.3.1", False), ("garbage", "0.3.1", False)])
def test_newer(latest, current, newer):
    assert is_newer(latest, current) is newer


def test_the_installer_is_picked_not_the_zip():
    picked = pick_installer(release())
    assert picked["name"] == "JobLens-Setup-1.0.0.exe" and picked["size"] == 57793533
    assert picked["sha256"] == "70114c39"
    assert pick_installer(release(assets=[])) is None
    test_build = [{"name": "JobLens-TestBuild-Setup-1.0.0.exe", "size": 1}]
    assert pick_installer(release(assets=test_build)) is None   # never offer the test build


DAY, HOUR = 24 * 3600, 3600


def test_once_a_day():
    assert check_due(None, 0, "0.3.1")                                       # never checked
    fresh = {"current": "0.3.1", "checked_at": 1000, "error": None}
    assert not check_due(fresh, 1000 + DAY - 1, "0.3.1")
    assert check_due(fresh, 1000 + DAY, "0.3.1")
    assert check_due(fresh, 1001, "1.0.0")                                   # updated since: ask again


def test_after_an_error_try_again_in_an_hour():
    failed = {"current": "0.3.1", "checked_at": 1000, "error": "ConnectionError"}
    assert not check_due(failed, 1000 + HOUR - 1, "0.3.1")
    assert check_due(failed, 1000 + HOUR, "0.3.1")


class Clock:
    def __init__(self, t=1_000_000.0):
        self.t = t

    def __call__(self):
        return self.t


def test_the_checker_asks_once_a_day_and_caches(tmp_path):
    calls, clock = [], Clock()
    checker = UpdateChecker(tmp_path, "0.3.1", fetch=lambda current: calls.append(current) or release(), clock=clock)
    first = checker.check()
    assert first["newer"] and first["latest"] == "v1.0.0" and first["installer"]["name"] == "JobLens-Setup-1.0.0.exe"
    clock.t += HOUR
    assert checker.check()["newer"] and len(calls) == 1                     # from the cache
    assert json.loads((tmp_path / "update_check.json").read_text())["latest"] == "v1.0.0"
    clock.t += DAY
    checker.check()
    assert len(calls) == 2
    assert calls == ["0.3.1", "0.3.1"]                                       # only the version goes to GitHub


def test_offline_doesnt_crash_and_keeps_the_last_answer(tmp_path):
    clock = Clock()
    good = UpdateChecker(tmp_path, "0.3.1", fetch=lambda c: release(), clock=clock)
    good.check()

    def offline(current):
        raise ConnectionError("no internet")
    clock.t += DAY
    after = UpdateChecker(tmp_path, "0.3.1", fetch=offline, clock=clock).check()
    assert after["error"].startswith("ConnectionError") and after["newer"] is True   # still shown


def test_no_release_yet(tmp_path):
    result = UpdateChecker(tmp_path, "0.3.1", fetch=lambda c: {}).check()
    assert result["newer"] is False and result["error"] is None


def test_force_asks_even_if_fresh(tmp_path):
    calls = []
    checker = UpdateChecker(tmp_path, "0.3.1", fetch=lambda c: calls.append(1) or release("v0.3.1"))
    checker.check()
    checker.check(force=True)
    assert len(calls) == 2


# ---- the bridge ---------------------------------------------------------------

@pytest.fixture()
def api(tmp_path, monkeypatch):
    from desktop_web.bridge import Api
    from job_agent import settings

    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / ".env")
    monkeypatch.setenv("UPDATE_CHECK", "true")
    events = []
    a = Api(send=events.append)
    a._updates = UpdateChecker(tmp_path, "0.3.1", fetch=lambda c: release())
    return a, events


def test_startup_check_tells_the_page(api):
    a, events = api
    a._startup_update_check()
    assert events == [{"type": "update_available", "latest": "v1.0.0",
                       "page": f"https://github.com/{updates.REPO}/releases/tag/v1.0.0"}]
    status = a.update_status()
    json.dumps(status, allow_nan=False)
    assert status["newer"] and status["enabled"] is True


def test_switched_off_means_no_request(api, monkeypatch):
    a, events = api
    monkeypatch.setenv("UPDATE_CHECK", "false")
    a._updates._fetch = lambda c: pytest.fail("must not ask GitHub")
    a._startup_update_check()
    assert events == [] and a.update_status()["enabled"] is False


def test_check_now_works_even_when_switched_off_and_tells_the_sidebar(api, monkeypatch):
    a, events = api
    monkeypatch.setenv("UPDATE_CHECK", "false")
    result = a.check_for_updates()  # you asked: so ask, even with the daily check off
    assert result["newer"] and result["enabled"] is False
    assert events[-1]["type"] == "update_available" and events[-1]["latest"] == "v1.0.0"


def test_the_setting_is_writable(api):
    a, _ = api
    assert a.save_settings({"UPDATE_CHECK": "false"})["UPDATE_CHECK"] == "false"
    with pytest.raises(ValueError):
        a.save_settings({"UPDATE_CHECK": "sometimes"})


# ---- 13d: download, verify, install ---------------------------------------------

import hashlib  # noqa: E402

from desktop_web.updates import UpdateRefused, check_source, download, launch_installer, verify  # noqa: E402

GOOD = b"MZ" + b"\x00" * 5000  # stands in for an installer
GOOD_SHA = hashlib.sha256(GOOD).hexdigest()
URL = f"https://github.com/{updates.REPO}/releases/download/v1.0.0/JobLens-Setup-1.0.0.exe"


def installer(**change):
    return {"name": "JobLens-Setup-1.0.0.exe", "size": len(GOOD), "url": URL, "sha256": GOOD_SHA, **change}


class FakeResponse:
    def __init__(self, body):
        self.body, self.headers = body, {"Content-Length": str(len(body))}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def raise_for_status(self):
        pass

    def iter_content(self, size):
        for i in range(0, len(self.body), size):
            yield self.body[i:i + size]


def serving(body):
    asked = []

    def get(url, **kwargs):
        asked.append(url)
        return FakeResponse(body)
    return get, asked


@pytest.mark.parametrize("change, why", [
    ({"name": "JobLens-Setup-1.0.0.exe.bat"}, "isn't a JobLens installer"),
    ({"name": "evil.exe"}, "isn't a JobLens installer"),
    ({"url": "https://example.com/JobLens-Setup-1.0.0.exe"}, "isn't on JobLens' GitHub"),
    ({"url": "https://github.com/someone-else/Job-hunt-assistent-agent/releases/download/v1.0.0/JobLens-Setup-1.0.0.exe"},
     "isn't on JobLens' GitHub"),
    ({"url": URL.replace("JobLens-Setup-1.0.0.exe", "other.exe")}, "isn't on JobLens' GitHub"),
    ({"sha256": None}, "no checksum"),
    ({"sha256": "abc"}, "no checksum"),
])
def test_only_our_installer_from_our_releases_with_a_checksum(change, why):
    with pytest.raises(UpdateRefused, match=why):
        check_source(installer(**change))


def test_a_good_download_is_verified_and_kept(tmp_path):
    get, asked = serving(GOOD)
    seen = []
    path = download(installer(), tmp_path, progress=lambda done, total: seen.append((done, total)), get=get)
    assert path.read_bytes() == GOOD and asked == [URL]
    assert seen[-1] == (len(GOOD), len(GOOD))
    assert [p.name for p in tmp_path.iterdir()] == ["JobLens-Setup-1.0.0.exe"]   # no .part left


def test_a_tampered_download_is_refused_and_deleted(tmp_path):
    evil = b"MZ" + b"\x01" * 5000  # same size, different bytes
    get, _ = serving(evil)
    with pytest.raises(UpdateRefused, match="SHA-256 doesn't match"):
        download(installer(), tmp_path, get=get)
    assert list(tmp_path.iterdir()) == []                                      # nothing left to run


def test_a_cut_off_download_is_refused(tmp_path):
    get, _ = serving(GOOD[:1000])
    with pytest.raises(UpdateRefused, match="bytes, GitHub says"):
        download(installer(), tmp_path, get=get)


def test_nothing_is_downloaded_from_a_wrong_place(tmp_path):
    get, asked = serving(GOOD)
    with pytest.raises(UpdateRefused):
        download(installer(url="https://example.com/JobLens-Setup-1.0.0.exe"), tmp_path, get=get)
    assert asked == []                                                          # refused before any request


def test_the_file_is_checked_again_right_before_it_runs(tmp_path):
    get, _ = serving(GOOD)
    path = download(installer(), tmp_path, get=get)
    path.write_bytes(b"MZ" + b"\x02" * 5000)     # swapped on disk after the download
    started = []
    with pytest.raises(UpdateRefused):
        launch_installer(path, installer(), run=lambda *a, **k: started.append(a))
    assert started == []


def test_a_verified_installer_starts_silently_and_reopens_joblens(tmp_path):
    get, _ = serving(GOOD)
    path = download(installer(), tmp_path, get=get)
    started = []
    launch_installer(path, installer(), run=lambda args, **kw: started.append((args, kw)))
    args, kw = started[0]
    assert args[0] == str(path) and {"/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART", "/RELAUNCH=1"} <= set(args)
    assert kw["creationflags"]  # detached: it outlives JobLens, which closes for it


def newer_api(tmp_path, monkeypatch, body=GOOD):
    from desktop_web.bridge import Api
    from job_agent import paths

    monkeypatch.setattr(paths, "APP_HOME", tmp_path)
    events = []
    a = Api(send=events.append)
    rel = release()
    rel["assets"][1].update({"size": len(GOOD), "digest": f"sha256:{GOOD_SHA}", "browser_download_url": URL})
    a._updates = UpdateChecker(tmp_path, "0.3.1", fetch=lambda c: rel)
    a._updates.check()
    a._http_get, _ = serving(body)  # the download is served by a stand-in
    return a, events


def test_bridge_download_then_install_closes_the_app(tmp_path, monkeypatch):
    a, events = newer_api(tmp_path, monkeypatch)
    assert a.download_update() == {"ok": True, "latest": "v1.0.0", "verified": True}
    kinds = [e["type"] for e in events]
    assert "update_progress" in kinds and kinds[-1] == "update_ready"
    started, quit_called = [], threading.Event()
    monkeypatch.setattr(updates, "launch_installer", lambda path, inst: started.append(path))
    a._on_quit(quit_called.set)
    assert a.install_update() == {"ok": True}
    assert started and started[0].name == "JobLens-Setup-1.0.0.exe"
    assert quit_called.wait(3)                                                 # JobLens closes for the installer


def test_no_install_during_a_run(tmp_path, monkeypatch):
    a, _ = newer_api(tmp_path, monkeypatch)
    a.download_update()
    a._runner.last_pause = {"type": "paused", "kind": "review"}               # a draft is waiting for you
    with pytest.raises(RuntimeError, match="Finish or stop the current run first"):
        a.install_update()


def test_install_needs_a_download_first(tmp_path, monkeypatch):
    a, _ = newer_api(tmp_path, monkeypatch)
    with pytest.raises(RuntimeError, match="Download the update first"):
        a.install_update()


def test_download_needs_a_newer_version(tmp_path, monkeypatch):
    from desktop_web.bridge import Api

    a = Api(send=lambda e: None)
    a._updates = UpdateChecker(tmp_path, "1.0.0", fetch=lambda c: release("v1.0.0"))
    a._updates.check()
    with pytest.raises(RuntimeError, match="no newer version"):
        a.download_update()


def test_old_downloads_are_cleaned_up(tmp_path):
    (tmp_path / "JobLens-Setup-0.3.1.exe").write_bytes(b"old")
    (tmp_path / "JobLens-Setup-1.0.0.exe.part").write_bytes(b"half")
    updates.clean_downloads(tmp_path)
    assert list(tmp_path.iterdir()) == []
