"""
JobLens version 2: open the window (Phase 12c).

    python -m desktop_web                 # the built UI (frontend -> npm run build)
    python -m desktop_web --dev           # the Vite dev server: edit React, see it live
    python -m desktop_web --smoke out.json [--screenshot shot.png]
                                          # open, check the page is alive, close

The page is static files in desktop_web/web/ (built from frontend/). pywebview
serves them from a local http server and shows them in Edge WebView2.
"""

import argparse
import json
import sys
import threading
import time
from pathlib import Path

import webview

from job_agent import paths, settings
from desktop_web.bridge import Api, window_sender

DEV_URL = "http://localhost:5173"
WEB_DIR = paths.resource_path("desktop_web/web")
BACKGROUND = {"dark": "#0A0F1C", "light": "#F4F6FA"}  # = --bg in tokens.css: no white flash


def _background() -> str:
    theme = settings.read_settings().get("UI_THEME", "system")
    return BACKGROUND["light" if theme == "light" else "dark"]


def _smoke(window, out: Path, screenshot: Path | None) -> None:
    """Wait for the React app to say it's alive (window.__joblens_ready), then close."""
    result = {"ok": False}
    try:
        end = time.time() + 30
        while time.time() < end:
            ready = window.evaluate_js("window.__joblens_ready || null")
            if ready:
                result = {"ok": True, **ready,
                          "theme": window.evaluate_js("document.documentElement.dataset.theme"),
                          "nav_items": window.evaluate_js("document.querySelectorAll('.nav-link').length"),
                          "title": window.evaluate_js("document.title")}
                break
            time.sleep(0.25)
        else:
            result["error"] = "the page never reported ready"
        if screenshot:
            time.sleep(1.5)  # let the model status and fonts settle
            _screenshot(screenshot)
            result["screenshot"] = str(screenshot)
    except Exception as e:
        result["error"] = repr(e)
    out.write_text(json.dumps(result, indent=2))
    window.destroy()


def _screenshot(path: Path) -> None:
    """Grab the JobLens window from the screen (developer check, Windows only)."""
    import ctypes
    from ctypes import wintypes

    from PIL import ImageGrab

    user32 = ctypes.windll.user32
    hwnd = user32.FindWindowW(None, "JobLens")
    rect = wintypes.RECT()
    # DWMWA_EXTENDED_FRAME_BOUNDS = 9: the visible window, without the shadow.
    ctypes.windll.dwmapi.DwmGetWindowAttribute(hwnd, 9, ctypes.byref(rect), ctypes.sizeof(rect))
    ImageGrab.grab(bbox=(rect.left, rect.top, rect.right, rect.bottom), all_screens=True).save(path)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="desktop_web")
    parser.add_argument("--dev", action="store_true", help="load the Vite dev server")
    parser.add_argument("--smoke", type=Path, metavar="OUT", help="open, check, close; write OUT json")
    parser.add_argument("--screenshot", type=Path, help="with --smoke: save a PNG of the window")
    args = parser.parse_args(argv)

    if args.dev:
        url = DEV_URL
    else:
        index = WEB_DIR / "index.html"
        if not index.exists():
            print("The UI isn't built yet. Run:  cd frontend && npm install && npm run build")
            return 1
        url = str(index)

    # The window needs the API, and the API's sender needs the window: break
    # the loop with a holder that is filled in once the window exists.
    holder = {}
    api = Api(send=lambda event: holder["send"](event))
    window = webview.create_window("JobLens", url, js_api=api, width=1360, height=880,
                                   min_size=(720, 560), background_color=_background(),
                                   on_top=bool(args.smoke))
    holder["send"] = window_sender(window)

    if args.smoke:
        webview.start(_smoke, (window, args.smoke, args.screenshot), gui="edgechromium")
    else:
        webview.start(gui="edgechromium", debug=args.dev)  # debug = F12 dev tools
    return 0


if __name__ == "__main__":
    sys.exit(main())
