"""
Tests for the version-2 window entry point (Phase 12c) - no window is opened.
The real window is checked with:  python -m desktop_web --smoke out.json
"""

from desktop_web import app


def test_missing_build_gives_a_clear_message(tmp_path, monkeypatch, capsys):
    from desktop_web import instance

    # A JobLens running from this repo would answer the single-instance check
    # (its window popped up and main() returned 0: found 3 Nov 2026).
    monkeypatch.setattr(instance.SingleInstance, "ask_running_copy_to_show", lambda self: False)
    monkeypatch.setattr(instance.SingleInstance, "listen", lambda self, on_show: None)
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


class ClosableWindow:
    """Like pywebview: destroy() asks the `closing` handlers first, and any of
    them can refuse. That's what made the update's "close" only hide JobLens."""

    def __init__(self):
        self.events = type("Events", (), {})()
        self.events.closing = FakeEvent()
        self.events.loaded = FakeEvent()
        self.hidden = self.destroyed = False

    def hide(self):
        self.hidden = True

    def destroy(self):
        if all(handler() for handler in self.events.closing):
            self.destroyed = True


def tray_with_shortcut_on(monkeypatch):
    from desktop_web import autostart, tray as tray_module

    monkeypatch.setattr(tray_module.Tray, "start", lambda self: setattr(self, "_icon", object()))
    monkeypatch.setattr(tray_module.Tray, "_refresh", lambda self: None)
    monkeypatch.setattr(tray_module.Tray, "notify", lambda self, *a: None)
    monkeypatch.setattr(autostart, "enabled", lambda: False)
    window = ClosableWindow()
    api = type("Api", (), {"stop_run": None, "_hotkey": type("Hotkey", (), {"key": "Ctrl+Alt+J"})()})()
    return window, app._start_tray(window, api, {"send": lambda event: None})


def test_the_x_button_hides_but_quitting_for_an_update_really_closes(monkeypatch):
    # 6 Nov: Install now hid JobLens instead of closing it, so the installer
    # met a running JobLens and gave up, on every try.
    window, tray = tray_with_shortcut_on(monkeypatch)
    window.destroy()                             # the X button: same path as window.destroy
    assert window.hidden and not window.destroyed

    app._quit_action(window, tray)()             # what install_update calls
    assert window.destroyed


def test_without_a_tray_quitting_is_just_closing():
    window = ClosableWindow()
    app._quit_action(window, None)()
    assert window.destroyed


def test_only_windows_itself_overrules_hiding_to_the_tray():
    assert app.windows_is_closing_us("WindowsShutDown")
    assert not app.windows_is_closing_us("UserClosing")
    assert not app.windows_is_closing_us("None")


def test_a_shutdown_takes_the_refusal_back(monkeypatch):
    window = ClosableWindow()
    form_closing = FakeEvent()
    window.native = type("Form", (), {"FormClosing": form_closing})()
    app._close_when_windows_asks(window)
    for _ in range(2):                           # `loaded` fires on every reload
        for handler in window.events.loaded:
            handler()
    assert len(form_closing) == 1
    args = type("Args", (), {"CloseReason": "WindowsShutDown", "Cancel": True})()
    form_closing[0](None, args)
    assert args.Cancel is False
    args = type("Args", (), {"CloseReason": "UserClosing", "Cancel": True})()
    form_closing[0](None, args)
    assert args.Cancel is True                   # the X button still hides
