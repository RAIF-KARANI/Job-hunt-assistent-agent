"""
Tests for the update check (13b). GitHub is replaced by a stand-in, so no
network is used; the release data has the shape the real API returns.
"""

import json

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
