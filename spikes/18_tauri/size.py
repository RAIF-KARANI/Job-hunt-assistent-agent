"""Phase 18b: how big a Tauri JobLens would be, against v1.2.0.

Today's app folder (dist/JobLens, the v1.2.0 build) is taken apart into:
  - what stays with the Python side: Python, the agent and its libraries
  - what only the window and tray need, and would move to Rust:
      webview, pythonnet, clr_loader (the pywebview window), pystray and
      PIL (the tray icon), desktop_web/web (the UI: Tauri builds it into
      its own program)
The Tauri version = the part that stays + the spike's Rust program.

Both are compressed the same way (LZMA, as Inno Setup does), so the
difference is fair even though no real Tauri installer with Python was made.

    .venv/Scripts/python spikes/18_tauri/size.py
"""

import io
import lzma
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
APP = ROOT / "dist" / "JobLens"
TAURI_EXE = ROOT / "spikes" / "18_tauri" / "src-tauri" / "target" / "release" / "joblens-spike.exe"
WINDOW_ONLY = ["webview", "pythonnet", "clr_loader", "pystray", "PIL", "desktop_web/web"]
WINDOW_ONLY_GLOBS = ["pywebview-*.dist-info", "pystray-*.dist-info", "pythonnet-*.dist-info", "clr_loader-*.dist-info", "pillow-*.dist-info"]
MB = 1024 * 1024


def window_only(path: Path) -> bool:
    rel = path.relative_to(APP / "_internal").as_posix() if (APP / "_internal") in path.parents else ""
    if any(rel == p or rel.startswith(p + "/") for p in WINDOW_ONLY):
        return True
    top = rel.split("/")[0]
    return any(Path(top).match(g) for g in WINDOW_ONLY_GLOBS)


def packed(files: list[tuple[Path, str]]) -> int:
    buffer = io.BytesIO()
    with lzma.open(buffer, "wb", preset=6) as xz, tarfile.open(fileobj=xz, mode="w") as tar:
        for path, name in files:
            tar.add(path, arcname=name)
    return buffer.tell()


def main() -> None:
    files = [p for p in APP.rglob("*") if p.is_file()]
    stays = [p for p in files if not window_only(p)]
    moves = [p for p in files if window_only(p)]
    size = lambda ps: sum(p.stat().st_size for p in ps)
    print(f"v1.2.0 app folder: {size(files) / MB:.1f} MB")
    print(f"  only for the window and tray: {size(moves) / MB:.1f} MB")
    print(f"  stays with Python: {size(stays) / MB:.1f} MB")
    print(f"Tauri program (UI built in): {TAURI_EXE.stat().st_size / MB:.1f} MB")

    today = packed([(p, p.relative_to(APP).as_posix()) for p in files])
    tauri = packed([(p, p.relative_to(APP).as_posix()) for p in stays] + [(TAURI_EXE, "joblens.exe")])
    print(f"Compressed: today {today / MB:.1f} MB, Tauri {tauri / MB:.1f} MB "
          f"({(tauri - today) / today * 100:+.0f}%)")


if __name__ == "__main__":
    main()
