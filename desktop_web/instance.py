"""
One JobLens at a time (13a, D24). With a tray icon, people start JobLens
again because they think it's closed; a second copy would run a second
agent on the same database. So the second start just brings the first
one's window back and exits.

How: the first JobLens listens on 127.0.0.1 (a free port) and writes the
port plus a random token to instance.json in its data folder. A second
start connects and sends the token; the first checks it (so no other
program can trigger it) and shows its window.
"""

import json
import secrets
import socket
import threading
from pathlib import Path
from typing import Callable

MESSAGE = b"show"


class SingleInstance:
    def __init__(self, folder: Path):
        self.file = folder / "instance.json"
        self._server: socket.socket | None = None

    def ask_running_copy_to_show(self) -> bool:
        """True if another JobLens answered (this one should exit)."""
        try:
            info = json.loads(self.file.read_text(encoding="utf-8"))
            with socket.create_connection(("127.0.0.1", int(info["port"])), timeout=2) as conn:
                conn.sendall(info["token"].encode() + b" " + MESSAGE)
                return conn.recv(2) == b"ok"
        except (OSError, ValueError, KeyError):
            return False  # no file, a stale file, or nobody listening: we're the first

    def listen(self, on_show: Callable[[], None]) -> None:
        """Be the running copy: answer later starts on a background thread."""
        token = secrets.token_hex(16)
        server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server.bind(("127.0.0.1", 0))
        server.listen(4)
        self._server = server
        self.file.parent.mkdir(parents=True, exist_ok=True)
        self.file.write_text(json.dumps({"port": server.getsockname()[1], "token": token}), encoding="utf-8")

        def serve():
            while True:
                try:
                    conn, _ = server.accept()
                except OSError:
                    return  # closed
                with conn:
                    try:
                        conn.settimeout(2)
                        if conn.recv(64) == token.encode() + b" " + MESSAGE:
                            conn.sendall(b"ok")
                            on_show()
                    except OSError:
                        pass

        threading.Thread(target=serve, name="joblens-instance", daemon=True).start()

    def close(self) -> None:
        if self._server is not None:
            self._server.close()
            self._server = None
        try:
            self.file.unlink()
        except OSError:
            pass
