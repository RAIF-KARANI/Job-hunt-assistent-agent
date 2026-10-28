"""
Build JobLens end to end: PyInstaller app folder -> self-test -> installer.

Run (venv activated, from the repo root):
    python scripts/build_installer.py

Produces:
    dist/JobLens/JobLens.exe                 the app folder
    dist/JobLens-Setup-<version>.exe         the installer (Inno Setup)

The version comes from job_agent/__init__.py (one place), and the frozen
app must pass its --self-test before an installer is made: never ship a
build that can't start.
"""

import os
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from job_agent import __version__  # noqa: E402


def find_iscc() -> Path:
    for base in (os.getenv("LOCALAPPDATA", ""), os.getenv("ProgramFiles(x86)", ""),
                 os.getenv("ProgramFiles", "")):
        candidate = Path(base) / ("Programs" if "Local" in base else "") / "Inno Setup 6" / "ISCC.exe"
        if candidate.exists():
            return candidate
    sys.exit("Inno Setup 6 not found. Install it: winget install JRSoftware.InnoSetup")


def step(title: str, cmd: list[str], **kw) -> None:
    print(f"\n=== {title} ===\n$ {' '.join(map(str, cmd))}", flush=True)
    subprocess.run(cmd, check=True, cwd=ROOT, **kw)


def main() -> None:
    print(f"Building JobLens {__version__}")
    step("1/3 PyInstaller: app folder",
         [sys.executable, "-m", "PyInstaller", "joblens.spec", "--noconfirm", "--log-level", "WARN"])

    # Self-test in installed mode, with AppData pointed at a temp folder so
    # the build machine's real data is never touched.
    with tempfile.TemporaryDirectory() as fake_appdata:
        report = Path(fake_appdata) / "selftest.txt"
        env = {**os.environ, "LOCALAPPDATA": fake_appdata}
        print("\n=== 2/3 Self-test of the frozen app ===", flush=True)
        result = subprocess.run([str(ROOT / "dist/JobLens/JobLens.exe"), "--self-test", str(report)],
                                env=env, timeout=600)
        print(report.read_text(encoding="utf-8"))
        if result.returncode != 0:
            sys.exit("Self-test FAILED - not building an installer.")

    step("3/3 Inno Setup: installer",
         [str(find_iscc()), f"/DAppVersion={__version__}", "/Q", "installer/joblens.iss"])
    setup = ROOT / "dist" / f"JobLens-Setup-{__version__}.exe"
    print(f"\nDone: {setup} ({setup.stat().st_size / 1e6:.0f} MB)")


if __name__ == "__main__":
    main()
