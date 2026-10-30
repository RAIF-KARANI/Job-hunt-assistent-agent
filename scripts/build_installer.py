"""
Build JobLens end to end:
    front end -> WebView2 bootstrapper -> PyInstaller -> self-test + window test -> installer

Run (venv activated, from the repo root):
    python scripts/build_installer.py                  # the real installer
    python scripts/build_installer.py --test-install   # + install, test, uninstall a TEST build

Produces:
    desktop_web/web/                         the built React UI (from frontend/)
    dist/JobLens/JobLens.exe                 the app folder
    dist/JobLens-Setup-<version>.exe         the installer (Inno Setup)
    dist/JobLens-TestBuild-Setup-<version>.exe   with --test-install

Needs: Node.js (only to build, D13), Inno Setup 6, internet for the first
build (the WebView2 bootstrapper is downloaded once into build/webview2/).

The version comes from job_agent/__init__.py (one place), and the frozen app
must pass its --self-test AND open its window (--smoke) before an installer
is made: never ship a build that can't start.

--test-install (12h) builds "JobLens Test Build" (own AppId, folder and
shortcut: see installer/joblens.iss), installs it silently into a temp
folder, runs the INSTALLED copy's self-test, uninstalls it and checks that
nothing is left. A real JobLens installed on the build PC is never touched.
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import winreg
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from job_agent import __version__  # noqa: E402

WEBVIEW2_URL = "https://go.microsoft.com/fwlink/p/?LinkId=2124703"  # Evergreen bootstrapper
WEBVIEW2_EXE = ROOT / "build" / "webview2" / "MicrosoftEdgeWebview2Setup.exe"
TEST_APP_ID = "{C4A7D2E1-8B3F-4E6A-9D5C-1F2E3A4B5C6D}_is1"  # = TheAppId in joblens.iss (TestBuild)
REAL_APP_ID = "{6B0E5A3C-2F1D-4C8B-9E7A-4A1F2D3C5B6E}_is1"


def find_iscc() -> Path:
    for base in (os.getenv("LOCALAPPDATA", ""), os.getenv("ProgramFiles(x86)", ""),
                 os.getenv("ProgramFiles", "")):
        candidate = Path(base) / ("Programs" if "Local" in base else "") / "Inno Setup 6" / "ISCC.exe"
        if candidate.exists():
            return candidate
    sys.exit("Inno Setup 6 not found. Install it: winget install JRSoftware.InnoSetup")


def step(title: str, cmd: list, **kw) -> None:
    print(f"\n=== {title} ===\n$ {' '.join(map(str, cmd))}", flush=True)
    subprocess.run(cmd, check=True, cwd=kw.pop("cwd", ROOT), **kw)


def build_front_end() -> None:
    npm = shutil.which("npm")
    if not npm:
        sys.exit("Node.js is needed to build the UI (not to run the app): winget install OpenJS.NodeJS.LTS")
    # `npm ci`: exactly the versions in package-lock.json, from a clean folder.
    step("1/5 Front end: install exact packages", [npm, "ci", "--no-audit", "--no-fund"], cwd=ROOT / "frontend")
    step("1/5 Front end: typecheck + build", [npm, "run", "build"], cwd=ROOT / "frontend")
    built = ROOT / "desktop_web" / "web" / "index.html"
    if not built.exists():
        sys.exit(f"The front-end build didn't produce {built}")


def signer(path: Path) -> tuple[str, str]:
    """(status, signer) of a file's Authenticode signature, via PowerShell."""
    out = subprocess.run(
        ["powershell", "-NoProfile", "-Command",
         f"$s = Get-AuthenticodeSignature -LiteralPath '{path}'; "
         "\"$($s.Status)|$($s.SignerCertificate.Subject)\""],
        capture_output=True, text=True, timeout=60).stdout.strip()
    status, _, subject = out.partition("|")
    return status, subject


def webview2_bootstrapper() -> None:
    """Download Microsoft's WebView2 bootstrapper once; refuse it unless it is
    validly signed by Microsoft (it runs on users' PCs)."""
    print("\n=== 2/5 WebView2 bootstrapper ===", flush=True)
    if not WEBVIEW2_EXE.exists():
        WEBVIEW2_EXE.parent.mkdir(parents=True, exist_ok=True)
        print(f"Downloading {WEBVIEW2_URL}")
        with urllib.request.urlopen(WEBVIEW2_URL, timeout=60) as r, open(WEBVIEW2_EXE, "wb") as f:
            shutil.copyfileobj(r, f)
    status, subject = signer(WEBVIEW2_EXE)
    if status != "Valid" or "O=Microsoft Corporation" not in subject:
        WEBVIEW2_EXE.unlink(missing_ok=True)
        sys.exit(f"The WebView2 bootstrapper's signature isn't valid ({status}, {subject}): deleted, not shipped.")
    print(f"OK: {WEBVIEW2_EXE.name}, {WEBVIEW2_EXE.stat().st_size / 1e6:.1f} MB, signed by Microsoft")


def check_frozen_app(exe: Path, title: str) -> None:
    """--self-test (no window) and --smoke (the real window and page), with
    AppData pointed at a temp folder so the build PC's real data is never touched."""
    with tempfile.TemporaryDirectory() as fake_appdata:
        env = {**os.environ, "LOCALAPPDATA": fake_appdata}
        report = Path(fake_appdata) / "selftest.txt"
        print(f"\n=== {title}: self-test ===", flush=True)
        result = subprocess.run([str(exe), "--self-test", str(report)], env=env, timeout=600)
        print(report.read_text(encoding="utf-8") if report.exists() else "(no report written)")
        if result.returncode != 0:
            sys.exit("Self-test FAILED - not building an installer.")

        print(f"\n=== {title}: window test ===", flush=True)
        smoke = Path(fake_appdata) / "smoke.json"
        subprocess.run([str(exe), "--smoke", str(smoke)], env=env, timeout=120)
        data = json.loads(smoke.read_text()) if smoke.exists() else {"ok": False, "error": "no result"}
        print(json.dumps(data, indent=2))
        if not data.get("ok"):
            sys.exit("The window test FAILED - not building an installer.")


def uninstall_entry(app_id: str) -> dict | None:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            rf"Software\Microsoft\Windows\CurrentVersion\Uninstall\{app_id}") as k:
            return {name: winreg.QueryValueEx(k, name)[0]
                    for name in ("DisplayName", "DisplayVersion", "InstallLocation")}
    except OSError:
        return None


def test_install(setup: Path) -> None:
    """Install the TEST build silently, test the installed copy, uninstall, check it's gone."""
    real_before = uninstall_entry(REAL_APP_ID)
    if uninstall_entry(TEST_APP_ID):
        sys.exit("A JobLens Test Build is still installed from an earlier run: uninstall it first.")
    with tempfile.TemporaryDirectory() as tmp:
        target = Path(tmp) / "JobLens Test Build"
        log = Path(tmp) / "install.log"
        step("Test install (silent)", [str(setup), "/VERYSILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
                                       f"/DIR={target}", f"/LOG={log}"])
        entry = uninstall_entry(TEST_APP_ID)
        print(f"Installed: {entry}")
        if not entry or not (target / "JobLens.exe").exists():
            sys.exit("Test install FAILED: not registered or JobLens.exe missing.")
        webview2_lines = [line for line in log.read_text(encoding="utf-8", errors="replace").splitlines()
                          if "WebView2" in line]
        print("Installer log, WebView2:", *webview2_lines, sep="\n  ")

        check_frozen_app(target / "JobLens.exe", "Installed copy")

        step("Test uninstall (silent)", [str(target / "unins000.exe"), "/VERYSILENT", "/SUPPRESSMSGBOXES",
                                         "/NORESTART"])
        # Inno's uninstaller runs from a temp copy of itself, which deletes
        # unins000.exe only after the original exits: that took over 30 s here.
        for _ in range(90):
            if not target.exists() and not uninstall_entry(TEST_APP_ID):
                break
            time.sleep(1)
        left = list(target.rglob("*")) if target.exists() else []
        if uninstall_entry(TEST_APP_ID) or left:
            sys.exit(f"Test uninstall FAILED: registry entry or files left ({left[:5]})")
        print("Uninstalled: no files, no registry entry left.")
    if uninstall_entry(REAL_APP_ID) != real_before:
        sys.exit("The REAL JobLens install changed during the test - this must never happen.")
    print(f"The real JobLens install was not touched: {real_before}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--test-install", action="store_true",
                        help="build a separate Test Build, install it, test it, uninstall it")
    args = parser.parse_args()

    print(f"Building JobLens {__version__}")
    build_front_end()
    webview2_bootstrapper()
    step("3/5 PyInstaller: app folder",
         [sys.executable, "-m", "PyInstaller", "joblens.spec", "--noconfirm", "--log-level", "WARN"])
    check_frozen_app(ROOT / "dist" / "JobLens" / "JobLens.exe", "4/5 Frozen app")

    defines = [f"/DAppVersion={__version__}"] + (["/DTestBuild"] if args.test_install else [])
    step("5/5 Inno Setup: installer", [str(find_iscc()), *defines, "/Q", "installer/joblens.iss"])
    name = f"JobLens-{'TestBuild-' if args.test_install else ''}Setup-{__version__}.exe"
    setup = ROOT / "dist" / name
    app_mb = sum(f.stat().st_size for f in (ROOT / "dist" / "JobLens").rglob("*") if f.is_file()) / 1e6
    print(f"\nDone: {setup} ({setup.stat().st_size / 1e6:.0f} MB; app folder {app_mb:.0f} MB)")

    if args.test_install:
        test_install(setup)


if __name__ == "__main__":
    main()
