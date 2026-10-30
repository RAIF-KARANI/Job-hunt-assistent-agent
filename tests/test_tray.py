"""
Tests for the tray (13a): its decisions follow the same events the page
gets; one JobLens at a time. No tray icon or window is created.
"""

import json
import socket
import threading

import pytest

from desktop_web.instance import SingleInstance
from desktop_web.tray import RunState, Tray, close_action, notification, status_text


def follow(*events):
    state = RunState()
    for e in events:
        state.update(e)
    return state


STARTED = {"type": "started", "run_id": "r", "url": "https://x"}
BUSY, IDLE = {"type": "busy", "busy": True}, {"type": "busy", "busy": False}
REVIEW = {"type": "paused", "kind": "review", "summary": {"title": "AI Engineer", "company": "Northwind"}}


def test_closing_the_window_while_the_agent_works_hides_it():
    assert close_action(follow(STARTED, BUSY, {"type": "step", "step": 2})) == "hide"


def test_closing_it_while_a_draft_waits_for_you_hides_it_too():
    assert close_action(follow(STARTED, BUSY, IDLE, REVIEW)) == "hide"  # not busy, but you'd lose the draft


@pytest.mark.parametrize("end", [{"type": "finished", "decision": "approve"}, {"type": "failed", "error": "x"},
                                 {"type": "stopped", "run_id": "r"}])
def test_closing_it_after_the_run_quits(end):
    assert close_action(follow(STARTED, BUSY, IDLE, end)) == "quit"


def test_closing_it_when_nothing_ever_ran_quits():
    assert close_action(RunState()) == "quit"


def test_the_status_line():
    assert status_text(follow(STARTED, BUSY, {"type": "step", "step": 3})) == \
        "Working: researching the company (step 3 of 5)"
    assert status_text(follow(STARTED, BUSY, IDLE, REVIEW)) == "Your cover note is ready to review"
    assert status_text(RunState()) == "Idle"


def test_notifications_name_the_job():
    state = follow(STARTED, {"type": "step_detail", "step": 1, "text": "AI Engineer @ Northwind (Remote)"})
    assert notification(REVIEW, follow(STARTED, REVIEW))[1].startswith("The draft for AI Engineer @ Northwind")
    assert notification({"type": "finished", "decision": "approve"}, state) == \
        ("Run finished", "AI Engineer @ Northwind (Remote): saved to the tracker.")
    assert notification({"type": "log", "text": "x"}, state) is None


class FakeIcon:
    def __init__(self):
        self.notes, self.title = [], ""

    def notify(self, message, title):
        self.notes.append((title, message))

    def update_menu(self):
        pass

    def stop(self):
        pass


def tray_with_fake_icon():
    tray = Tray("icon.png", show=lambda: None, stop_run=lambda: None, quit_app=lambda: None)
    tray._icon = FakeIcon()
    return tray


def test_hidden_window_gets_one_tray_explanation_then_job_notifications():
    tray = tray_with_fake_icon()
    hidden = []
    for e in (STARTED, BUSY):
        tray.on_event(e)
    assert tray.window_closing(hide=lambda: hidden.append(1)) is False   # keep running
    assert tray.window_closing(hide=lambda: hidden.append(1)) is False
    assert hidden == [1, 1] and [t for t, _ in tray._icon.notes] == ["JobLens is still working"]  # said once
    tray.on_event(IDLE)
    tray.on_event(REVIEW)
    assert tray._icon.notes[-1][0] == "Cover note ready"
    assert "JobLens · Your cover note is ready to review" == tray._icon.title


def test_no_notifications_while_the_window_is_open():
    tray = tray_with_fake_icon()
    for e in (STARTED, BUSY, IDLE, REVIEW):
        tray.on_event(e)
    assert tray._icon.notes == []


def test_without_a_tray_icon_closing_always_quits():
    tray = Tray("icon.png", show=lambda: None, stop_run=lambda: None, quit_app=lambda: None)
    tray.on_event(BUSY)
    assert tray.window_closing(hide=lambda: pytest.fail("must not hide with no icon")) is True


# ---- one JobLens at a time ----------------------------------------------------

def test_a_second_start_brings_the_first_one_back(tmp_path):
    shown = threading.Event()
    first = SingleInstance(tmp_path)
    assert first.ask_running_copy_to_show() is False          # nobody else running
    first.listen(on_show=shown.set)
    try:
        assert SingleInstance(tmp_path).ask_running_copy_to_show() is True
        assert shown.wait(2)
    finally:
        first.close()
    assert not (tmp_path / "instance.json").exists()


def test_a_wrong_token_is_ignored(tmp_path):
    shown = threading.Event()
    first = SingleInstance(tmp_path)
    first.listen(on_show=shown.set)
    try:
        port = json.loads((tmp_path / "instance.json").read_text())["port"]
        with socket.create_connection(("127.0.0.1", port), timeout=2) as conn:
            conn.sendall(b"guessed-token show")
            assert conn.recv(2) == b""                         # no answer
        assert not shown.wait(0.5)
    finally:
        first.close()


def test_a_stale_file_from_a_crash_doesnt_block_starting(tmp_path):
    (tmp_path / "instance.json").write_text(json.dumps({"port": 1, "token": "old"}))
    assert SingleInstance(tmp_path).ask_running_copy_to_show() is False
