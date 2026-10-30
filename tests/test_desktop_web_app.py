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
