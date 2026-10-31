"""
Tests for the version-2 window entry point (Phase 12c) - no window is opened.
The real window is checked with:  python -m desktop_web --smoke out.json
"""

from desktop_web import app


def test_missing_build_gives_a_clear_message(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(app, "WEB_DIR", tmp_path)     # no index.html here
    assert app.main([]) == 1
    assert "npm run build" in capsys.readouterr().out


def test_window_background_matches_the_theme(monkeypatch):
    # No white flash: the native window starts in the page's --bg color.
    monkeypatch.setattr(app.settings, "read_settings", lambda: {"UI_THEME": "light"})
    assert app._background() == "#F4F6FA"
    monkeypatch.setattr(app.settings, "read_settings", lambda: {"UI_THEME": "system"})
    assert app._background() == "#0A0F1C"


class FakeEvent(list):
    def __iadd__(self, handler):
        self.append(handler)
        return self


class FakeWindow:
    def __init__(self):
        self.events = type("Events", (), {})()
        self.events.closed = FakeEvent()
        self.destroyed = False

    def destroy(self):
        self.destroyed = True


def test_closing_the_main_window_also_closes_the_quick_box(monkeypatch):
    # 1.0.2: pywebview only exits when EVERY window is closed. The hidden quick
    # box stayed, so JobLens kept running with no window and couldn't be opened.
    from desktop_web import hotkey

    box = FakeWindow()
    monkeypatch.setattr(app.webview, "create_window", lambda *a, **k: box)
    monkeypatch.setattr(hotkey.HotkeyListener, "start", lambda self, key: None)
    main = FakeWindow()
    app._start_quick_box("C:/x/index.html", main, api=type("Api", (), {})(), tray=None)
    assert len(main.events.closed) == 1
    for handler in main.events.closed:
        handler()
    assert box.destroyed
