"""
Tests for quick analyze (14f): the shortcut's parser, the quick box's rules,
the setting, and that a quick run is always told about. One test registers
a real (unusual) global hotkey on Windows and frees it again.
"""

import sys

import pytest

from desktop_web import hotkey
from desktop_web.bridge import WRITABLE_SETTINGS, Api
from desktop_web.quick import QuickApi, is_link
from desktop_web.tray import Tray
from job_agent import settings


@pytest.fixture(autouse=True)
def isolated(tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "APP_HOME", tmp_path)
    monkeypatch.setattr(settings, "ENV_FILE", tmp_path / ".env")
    for key in WRITABLE_SETTINGS:
        monkeypatch.setenv(key, settings.DEFAULTS.get(key, ""))


# ---- the shortcut ----------------------------------------------------------------

def test_parse_reads_the_usual_ways_of_writing_a_shortcut():
    assert hotkey.parse("Ctrl+Alt+J") == (hotkey.MOD_CONTROL | hotkey.MOD_ALT, 0x4A, "Ctrl+Alt+J")
    assert hotkey.parse(" alt + shift + 7 ")[2] == "Alt+Shift+7"
    assert hotkey.parse("ctrl+F9")[1:] == (0x78, "Ctrl+F9")
    assert hotkey.parse("Win+Alt+K")[2] == "Alt+Win+K"   # always written in the same order


@pytest.mark.parametrize("bad", ["J", "Shift+J", "Ctrl+Alt", "Ctrl+Alt+J+K", "Ctrl+Space", "Ctrl+F13", ""])
def test_parse_refuses_what_would_fire_while_typing_or_cant_work(bad):
    with pytest.raises(ValueError):
        hotkey.parse(bad)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows hotkeys")
def test_a_real_hotkey_is_registered_once_and_a_taken_one_is_explained():
    combo = "Ctrl+Alt+Shift+F11"   # unusual, so the test doesn't fight your own shortcuts
    first, second = hotkey.HotkeyListener(lambda: None), hotkey.HotkeyListener(lambda: None)
    try:
        first.start(combo)
        assert first.status() == {"key": combo, "error": None}
        second.start(combo)
        assert second.key is None and "already used by another program" in second.error
        first.change("off")
        for _ in range(50):
            if first.key is None:
                break
            import time
            time.sleep(0.02)
        assert first.status() == {"key": None, "error": None}
    finally:
        first.stop()
        second.stop()


# ---- the quick box ---------------------------------------------------------------

class FakeRunner:
    busy = False
    last_pause = None


class FakeApi:
    def __init__(self, llm_ok=True):
        self._runner = FakeRunner()
        self.llm_ok = llm_ok
        self.started = []

    def get_settings(self):
        return {"UI_THEME": "dark"}

    def llm_status(self):
        return {"ok": self.llm_ok, "message": "Ollama isn't running." if not self.llm_ok else "ok"}

    def start_run(self, url):
        self.started.append(url)
        return {"run_id": "r1"}


def quick(api=None, clipboard=""):
    told = []
    box = QuickApi(api or FakeApi(), hide=lambda: told.append("hidden"), on_started=lambda: told.append("started"),
                   clipboard=lambda: clipboard)
    return box, told


def test_analyze_starts_the_normal_run_and_marks_it_quick():
    api = FakeApi()
    box, told = quick(api)
    assert box.quick_start(" https://jobs.example/1 ") == {"run_id": "r1"}
    assert api.started == ["https://jobs.example/1"] and told == ["started"]
    box.close()
    assert told[-1] == "hidden"


def test_the_box_refuses_with_a_reason_and_starts_nothing():
    api = FakeApi()
    box, _ = quick(api)
    with pytest.raises(ValueError, match="web link"):
        box.quick_start("not a link")
    api._runner.busy = True
    with pytest.raises(RuntimeError, match="already analyzing"):
        box.quick_start("https://jobs.example/1")
    api._runner.busy, api._runner.last_pause = False, {"kind": "review"}
    with pytest.raises(RuntimeError, match="waiting for you"):
        box.quick_start("https://jobs.example/1")
    api._runner.last_pause, api.llm_ok = None, False
    with pytest.raises(RuntimeError, match="Ollama"):
        box.quick_start("https://jobs.example/1")
    assert api.started == []


def test_only_a_copied_link_is_filled_in():
    assert quick(clipboard="https://www.linkedin.com/jobs/view/123")[0].clipboard_link() == "https://www.linkedin.com/jobs/view/123"
    assert quick(clipboard="my password")[0].clipboard_link() == ""
    assert quick(clipboard="https://x.com/a b")[0].clipboard_link() == ""
    assert not is_link("file:///C:/secret.txt") and not is_link("javascript:alert(1)")


# ---- the setting -----------------------------------------------------------------

class FakeListener:
    def __init__(self):
        self.changes = []

    def change(self, key):
        self.changes.append(key)

    def status(self):
        return {"key": "Ctrl+Alt+K", "error": None}


def test_a_new_shortcut_is_checked_saved_tidied_and_registered():
    api = Api(send=lambda e: None, graph=object())
    assert api.quick_key_status()["key"] is None            # no listener (tests, --smoke)
    api._hotkey = FakeListener()
    assert api.save_settings({"QUICK_KEY": "ctrl+alt+k"})["QUICK_KEY"] == "Ctrl+Alt+K"
    api.save_settings({"QUICK_KEY": "off"})
    assert api._hotkey.changes == ["Ctrl+Alt+K", "off"]
    with pytest.raises(ValueError, match="Ctrl or Alt"):
        api.save_settings({"QUICK_KEY": "Shift+J"})
    assert settings.read_settings()["QUICK_KEY"] == "off"   # the bad one wasn't saved


# ---- the notification ------------------------------------------------------------

def test_a_quick_run_is_told_about_even_with_the_window_open():
    tray = Tray("icon.png", show=lambda: None, stop_run=lambda: None, quit_app=lambda: None)
    told = []
    tray._icon = type("Icon", (), {"notify": lambda self, m, t: told.append(t), "update_menu": lambda self: None})()
    review = {"type": "paused", "kind": "review", "summary": {"title": "AI Engineer", "company": "Acme"}}
    tray.on_event(review)
    assert told == []                                      # window open, normal run: the page shows it
    tray.quick = True
    tray.on_event(review)
    assert told == ["Cover note ready"] and tray.quick is False
    tray.on_event({"type": "finished", "decision": "approve"})
    assert told == ["Cover note ready"]                    # from there on you're in the window


# ---- 1.0.3: keep in tray while the shortcut is on; notification clicks --------

def test_closing_keeps_joblens_in_the_tray_while_the_shortcut_works():
    from desktop_web.app import keeps_tray

    class Api:
        _hotkey = None

    api = Api()
    assert keeps_tray(api, lambda: False) is False                 # no shortcut: closing quits, as before
    api._hotkey = type("L", (), {"key": "Ctrl+Alt+J"})()
    assert keeps_tray(api, lambda: False) is True                  # the shortcut needs JobLens running
    api._hotkey.key = None                                         # off, or taken by another program
    assert keeps_tray(api, lambda: False) is False
    assert keeps_tray(api, lambda: True) is True                   # Start with Windows (14e)


def test_clicking_a_notification_opens_the_screen_it_is_about():
    from pystray._util import win32

    from desktop_web.tray import NIN_BALLOONUSERCLICK

    opened, icon_clicks = [], []
    tray = Tray("icon.png", show=lambda: None, stop_run=lambda: None, quit_app=lambda: None,
                open_page=opened.append)
    tray._icon = type("Icon", (), {"_message_handlers": {win32.WM_NOTIFY: lambda w, l: icon_clicks.append(l)},
                                   "notify": lambda self, m, t: None, "update_menu": lambda self: None})()
    tray._catch_notification_clicks()
    handler = tray._icon._message_handlers[win32.WM_NOTIFY]
    tray.hidden = True
    tray.notify("Cover note ready", "The draft is waiting.")
    handler(0, NIN_BALLOONUSERCLICK)
    assert opened == ["analyze"] and tray.hidden is False
    tray.notify("Time to follow up", "2 applications...")
    handler(0, NIN_BALLOONUSERCLICK)
    assert opened[-1] == "tracker"
    handler(0, win32.WM_LBUTTONUP)                                 # a click on the icon still works as before
    assert icon_clicks == [win32.WM_LBUTTONUP]
