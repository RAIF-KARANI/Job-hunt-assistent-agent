"""Phase 18 spike: JobLens's Python side, for a Tauri (Rust) window.

The Rust window starts this script and talks to it over a pipe, one JSON
object per line:

    Rust -> Python   {"id": 7, "method": "list_jobs", "args": []}
    Python -> Rust   {"id": 7, "result": [...]}       or {"id": 7, "error": "..."}
    Python -> Rust   {"event": {"type": "log", ...}}  (the same events the
                                                       pywebview window gets)

It reuses desktop_web.bridge.Api unchanged: the page calls exactly the same
methods as in the normal app. The script stops when the window closes its
end of the pipe.

Not in the spike: native file dialogs (Add PDFs...), the tray, the global
shortcut, the updater. Those belong to the window, so they would be
rewritten in Rust if the spike were adopted (step 18d).
"""

import io
import json
import os
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

STARTED = time.perf_counter()
ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

# The pipe is ours alone: anything the agent prints goes to stderr instead,
# or one stray print() would break the protocol.
_pipe = os.fdopen(os.dup(sys.stdout.fileno()), "w", encoding="utf-8", buffering=1)
sys.stdout = sys.stderr
_write_lock = threading.Lock()


def _write(message: dict) -> None:
    line = json.dumps(message, default=str)
    with _write_lock:
        _pipe.write(line + "\n")
        _pipe.flush()


def main() -> int:
    from desktop_web.bridge import Api

    # The same start-up work as the normal app (desktop_web/app.py), so the
    # timing compares like with like: runs cut off last time, and saved
    # scores from an older formula.
    from job_agent import runlog
    from job_agent.tracker import rescore_all

    for job in (runlog.mark_interrupted, rescore_all):
        try:
            job()
        except Exception as e:
            print(f"! start-up: {e}", file=sys.stderr)

    api = Api(send=lambda event: _write({"event": event}))
    print(f"[sidecar] ready after {(time.perf_counter() - STARTED) * 1000:.0f} ms", file=sys.stderr)
    _write({"event": {"type": "sidecar_ready", "ms": round((time.perf_counter() - STARTED) * 1000)}})

    # Calls can take seconds (llm_status waits on the network): each runs on
    # its own worker, so a slow one never holds up the others.
    pool = ThreadPoolExecutor(max_workers=8, thread_name_prefix="joblens-call")

    def handle(message: dict) -> None:
        call_id = message.get("id")
        name = str(message.get("method", ""))
        try:
            if name.startswith("_") or not callable(getattr(api, name, None)):
                raise AttributeError(f"JobLens has no '{name}'")
            result = getattr(api, name)(*message.get("args", []))
            _write({"id": call_id, "result": result})
        except Exception as e:  # the page shows the message, like a pywebview error
            _write({"id": call_id, "error": str(e) or e.__class__.__name__})

    stdin = io.TextIOWrapper(sys.stdin.buffer, encoding="utf-8")
    for line in stdin:
        line = line.strip()
        if not line:
            continue
        try:
            message = json.loads(line)
        except json.JSONDecodeError:
            continue
        pool.submit(handle, message)
    # The window closed its end: stop at once (a run's threads must not keep us alive).
    os._exit(0)


if __name__ == "__main__":
    sys.exit(main())
