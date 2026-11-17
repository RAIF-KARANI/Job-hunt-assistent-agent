"""18d1: the engine, the Python side of the Rust window (desktop_web/engine.py).

The protocol is checked here without a window and without the real Api, so
no user data is read or changed."""

import json
import threading
import time

from desktop_web.engine import Engine, Shell


class FakeApi:
    def app_info(self):
        return {"version": "test"}

    def add(self, a, b):
        return a + b

    def broken(self):
        raise ValueError("it broke")

    def _secret(self):
        return "hidden"


def make(on_page_loaded=lambda: None):
    out = []
    lock = threading.Lock()

    def write(message):
        with lock:
            out.append(message)

    shell = Shell(write)
    engine = Engine(FakeApi(), write, shell, on_page_loaded=on_page_loaded)
    return engine, shell, out


def wait_until(check, limit=3.0):
    end = time.time() + limit
    while time.time() < end:
        if check():
            return True
        time.sleep(0.01)
    return False


def line(message):
    return json.dumps(message) + "\n"


def test_a_call_gets_its_result():
    engine, _, out = make()
    engine.receive(line({"id": 1, "method": "add", "args": [2, 3]}))
    assert wait_until(lambda: {"id": 1, "result": 5} in out)


def test_an_error_comes_back_as_a_message():
    engine, _, out = make()
    engine.receive(line({"id": 2, "method": "broken", "args": []}))
    assert wait_until(lambda: {"id": 2, "error": "it broke"} in out)


def test_hidden_and_unknown_methods_are_refused():
    engine, _, out = make()
    engine.receive(line({"id": 3, "method": "_secret", "args": []}))
    engine.receive(line({"id": 4, "method": "nope", "args": []}))
    assert wait_until(lambda: len(out) == 2)
    assert all("error" in m and "result" not in m for m in out)
    assert "hidden" not in json.dumps(out)


def test_rubbish_lines_are_ignored():
    engine, _, out = make()
    engine.receive("not json\n")
    engine.receive("\n")
    time.sleep(0.05)
    assert out == []


def test_ask_waits_for_the_windows_answer():
    engine, shell, out = make()
    result = {}
    asker = threading.Thread(target=lambda: result.setdefault("v", shell.ask("pick_files", title="Resumes")))
    asker.start()
    assert wait_until(lambda: any("ask" in m for m in out))
    request = next(m for m in out if "ask" in m)
    assert request["do"] == "pick_files" and request["args"] == {"title": "Resumes"}
    engine.receive(line({"answer": request["ask"], "result": ["C:/a.pdf"]}))
    asker.join(2)
    assert result["v"] == ["C:/a.pdf"]


def test_an_answer_is_handled_even_while_every_worker_is_busy():
    """Answers skip the call queue: eight calls each waiting for the window
    must not stop the window's answers from getting through."""
    engine, shell, out = make()
    done = []

    class Waiting(FakeApi):
        def wait_for_window(self):
            return shell.ask("confirm", timeout=3)

    engine.api = Waiting()
    for n in range(8):
        engine.receive(line({"id": n, "method": "wait_for_window", "args": []}))
    assert wait_until(lambda: sum("ask" in m for m in out) == 8)
    for m in [m for m in out if "ask" in m]:
        engine.receive(line({"answer": m["ask"], "result": True}))
    assert wait_until(lambda: sum(1 for m in out if m.get("result") is True) == 8)


def test_a_window_error_is_raised_in_python():
    engine, shell, out = make()
    caught = {}

    def ask():
        try:
            shell.ask("save_file")
        except RuntimeError as e:
            caught["e"] = str(e)

    t = threading.Thread(target=ask)
    t.start()
    assert wait_until(lambda: any("ask" in m for m in out))
    engine.receive(line({"answer": out[-1]["ask"], "error": "cancelled"}))
    t.join(2)
    assert caught["e"] == "cancelled"


def test_when_the_window_is_gone_nobody_waits_forever():
    engine, shell, out = make()
    caught = {}

    def ask():
        try:
            shell.ask("pick_files")
        except RuntimeError as e:
            caught["e"] = str(e)

    t = threading.Thread(target=ask)
    t.start()
    assert wait_until(lambda: any("ask" in m for m in out))
    shell.give_up()
    t.join(2)
    assert "closed" in caught["e"]


def test_do_sends_a_request_without_waiting():
    _, shell, out = make()
    shell.do("navigate", page="tracker")
    assert out == [{"do": "navigate", "args": {"page": "tracker"}}]


def test_the_window_reports_whether_it_is_visible():
    engine, shell, _ = make()
    assert shell.visible
    engine.receive(line({"shell": "visibility", "visible": False}))
    assert shell.visible is False
    engine.receive(line({"shell": "visibility", "visible": True}))
    assert shell.visible is True


def test_page_loaded_starts_the_update_check_once():
    started = []
    engine, _, _ = make(on_page_loaded=lambda: started.append(1))
    engine.receive(line({"shell": "page_loaded"}))
    engine.receive(line({"shell": "page_loaded"}))  # a reload
    assert started == [1]


def test_the_bridge_no_longer_needs_a_window_library_to_load():
    """The engine imports bridge.py; pywebview must not be needed for that."""
    import ast
    from pathlib import Path

    tree = ast.parse(Path("desktop_web/bridge.py").read_text(encoding="utf-8"))
    top = [n for n in tree.body if isinstance(n, (ast.Import, ast.ImportFrom))]
    names = [a.name for n in top for a in n.names] + [getattr(n, "module", "") or "" for n in top]
    assert "webview" not in names


def test_smoke_reports_once_the_page_asks_for_app_info_then_closes(tmp_path):
    out = []
    shell = Shell(out.append)
    report = tmp_path / "smoke.json"
    engine = Engine(FakeApi(), out.append, shell, smoke=report)
    engine.receive(line({"id": 1, "method": "app_info", "args": []}))
    assert wait_until(lambda: report.exists())
    data = json.loads(report.read_text())
    assert data["ok"] is True and data["version"] == "test" and data["window"] == "tauri"
    assert wait_until(lambda: {"do": "quit", "args": {}} in out)
