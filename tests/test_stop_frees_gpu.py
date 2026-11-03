"""15g: Stop and Quit free the GPU at once.

On 1 Nov Ollama spent 25 minutes READING a prompt (GPU busy with other apps).
It sends nothing while it reads, so the Stop button (which acts on the next
word) waited, and quitting didn't end it either. These tests use the real
ChatOllama client against a fake Ollama that accepts the request and never
answers - the same situation, in a second."""

import socket
import threading
import time

import pytest
from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel

from desktop_web.runner import StopSignal
from job_agent import llm
from job_agent.llm import RunStopped


class Answer(BaseModel):
    text: str


@pytest.fixture
def silent_ollama(monkeypatch):
    """A server that accepts connections and never replies ("reading the prompt")."""
    server = socket.socket()
    server.bind(("127.0.0.1", 0))
    server.listen(4)
    held = []

    def accept():
        while True:
            try:
                held.append(server.accept())
            except OSError:
                return
    threading.Thread(target=accept, daemon=True).start()
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("OLLAMA_BASE_URL", f"http://127.0.0.1:{server.getsockname()[1]}")
    yield held
    server.close()
    for conn, _ in held:
        conn.close()


def start_call(stop: StopSignal) -> tuple[threading.Thread, dict]:
    result = {}

    def call():
        started = time.perf_counter()
        try:
            llm.structured_llm(Answer).invoke("hello", RunnableConfig(callbacks=[stop]))
            result["outcome"] = "answered"
        except Exception as e:  # what the run thread would see
            result["outcome"] = type(e).__name__
        result["seconds"] = time.perf_counter() - started
    thread = threading.Thread(target=call, daemon=True)
    thread.start()
    return thread, result


def wait_for_connection(held, timeout=5.0):
    end = time.time() + timeout
    while not held and time.time() < end:
        time.sleep(0.05)
    assert held, "the client never connected"


def test_stop_while_the_model_reads_the_prompt_ends_the_call_at_once(silent_ollama):
    stop = StopSignal()
    thread, result = start_call(stop)
    wait_for_connection(silent_ollama)
    time.sleep(0.3)  # the request is sent and waiting for an answer
    stop.stop()                    # the flag, as the Stop button sets it...
    assert llm.abort_requests() >= 1  # ...then the connection is closed
    thread.join(5)
    assert not thread.is_alive()
    assert result["outcome"] == "RunStopped"   # a stopped run, not an error
    assert result["seconds"] < 3


def test_without_closing_the_connection_the_flag_alone_waits(silent_ollama):
    # The old behaviour, kept as a test so the reason for abort_requests stays visible.
    stop = StopSignal()
    thread, result = start_call(stop)
    wait_for_connection(silent_ollama)
    stop.stop()
    thread.join(1.5)
    assert thread.is_alive()      # still waiting for a word that never comes
    llm.abort_requests()          # clean up
    thread.join(5)
    assert result["outcome"] == "RunStopped"


def test_abort_with_nothing_open_is_harmless():
    llm.abort_requests()
    assert llm.abort_requests() == 0


def test_unload_only_when_this_process_used_ollama(monkeypatch):
    calls = []
    import requests

    monkeypatch.setattr(requests, "post", lambda url, json, timeout: calls.append((url, json)))
    monkeypatch.setenv("LLM_PROVIDER", "ollama")
    monkeypatch.setenv("LLM_MODEL", "qwen3:8b")
    monkeypatch.setattr(llm, "_model_used", threading.Event())
    assert llm.unload_model() is False and calls == []
    llm.get_llm()  # a client was made: the model was (about to be) used
    assert llm.unload_model() is True
    assert calls[0][1] == {"model": "qwen3:8b", "keep_alive": 0}
    monkeypatch.setenv("LLM_PROVIDER", "anthropic")
    assert llm.unload_model() is False


def test_quit_stops_the_run_and_frees_the_model(monkeypatch):
    from desktop_web import app

    events = []

    class Runner:
        def shut_down(self, grace):
            events.append(("shut_down", grace))
            return True

    class Api:
        _runner = Runner()
    monkeypatch.setattr(llm, "unload_model", lambda: events.append("unload"))
    app._free_the_gpu(Api())
    assert events == [("shut_down", 5.0), "unload"]


def test_quit_exits_even_if_the_step_does_not_end(monkeypatch):
    from desktop_web import app

    class Runner:
        def shut_down(self, grace):
            return False
    monkeypatch.setattr(llm, "unload_model", lambda: None)
    exited = []
    monkeypatch.setattr("os._exit", lambda code: exited.append(code))
    app._free_the_gpu(type("Api", (), {"_runner": Runner()})())
    assert exited == [0]
