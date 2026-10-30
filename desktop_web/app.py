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


# Microsoft's id for the Evergreen WebView2 Runtime (the Edge engine the window uses).
WEBVIEW2_CLIENT = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
WEBVIEW2_DOWNLOAD = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"


def webview2_version() -> str | None:
    """The installed WebView2 Runtime version, or None. Windows 11 has it built
    in; some Windows 10 PCs don't (the installer adds it, 12h)."""
    import winreg

    for hive, key in [(winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\{WEBVIEW2_CLIENT}"),
                      (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\{WEBVIEW2_CLIENT}"),
                      (winreg.HKEY_CURRENT_USER, rf"Software\{WEBVIEW2_CLIENT}")]:
        try:
            with winreg.OpenKey(hive, key) as k:
                version = winreg.QueryValueEx(k, "pv")[0]
                if version and version != "0.0.0.0":
                    return version
        except OSError:
            continue
    return None


def _no_webview2() -> int:
    """Say what's missing in a normal Windows message box (there's no console)."""
    import ctypes
    import webbrowser

    answer = ctypes.windll.user32.MessageBoxW(
        None, "JobLens needs Microsoft Edge WebView2 Runtime, which isn't on this PC.\n\n"
              "Click OK to open Microsoft's download page, install it, then start JobLens again.",
        "JobLens", 0x1 | 0x30)  # OK/Cancel + warning icon
    if answer == 1:
        webbrowser.open(WEBVIEW2_DOWNLOAD)
    return 1


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
    parser.add_argument("--self-test", type=Path, metavar="REPORT", help="check the app, no window")
    args = parser.parse_args(argv)

    if args.self_test:
        from desktop_web.selftest import self_test
        return self_test(str(args.self_test))
    if not webview2_version():
        return _no_webview2()
    # 12j: runs still marked "running" were cut off when the app last closed.
    from job_agent import runlog
    try:
        runlog.mark_interrupted()
    except Exception as e:  # the run log must never stop the app from opening
        print(f"! run log: {e}")

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
    api._attach(window)  # native dialogs (resume PDFs) need the window

    if args.smoke:
        webview.start(_smoke, (window, args.smoke, args.screenshot), gui="edgechromium")
    else:
        webview.start(gui="edgechromium", debug=args.dev)  # debug = F12 dev tools
    return 0


if __name__ == "__main__":
    sys.exit(main())
