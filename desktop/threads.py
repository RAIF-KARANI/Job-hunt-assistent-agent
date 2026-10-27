"""
Run slow work off the GUI thread.

The golden rule of desktop GUIs: the GUI thread only draws and reacts to
clicks. Anything slow (network, LLM, disk scans) runs in a background
thread, or the window freezes and Windows shows "Not responding".

Qt widgets must ONLY be touched from the GUI thread. So a background task
never updates the UI directly; it emits a SIGNAL, and Qt delivers that
signal to the GUI thread (a "queued connection"), where the slot runs.
"""

from PySide6.QtCore import QObject, QRunnable, QThreadPool, Signal


class _Signals(QObject):
    # QRunnable can't have signals itself (it isn't a QObject), so it
    # carries this little helper object.
    done = Signal(object)
    failed = Signal(str)


class _Task(QRunnable):
    def __init__(self, fn, *args):
        super().__init__()
        self.fn, self.args = fn, args
        self.signals = _Signals()

    def run(self):  # runs in a pool thread
        try:
            result = self.fn(*self.args)
        except Exception as e:  # report, never crash the app
            self.signals.failed.emit(f"{type(e).__name__}: {e}")
        else:
            self.signals.done.emit(result)


# Tasks that are still running. Without this, Python could garbage-collect a
# task (and its signals object) as soon as run_in_background() returns - the
# thread keeps running, then crashes with "Signal source has been deleted"
# when it tries to report back. (Found by the packaging self-test, 9f.)
_running: set = set()


def run_in_background(fn, *args, on_done=None, on_error=None) -> None:
    """Call fn(*args) in Qt's thread pool; on_done(result) runs on the GUI thread."""
    task = _Task(fn, *args)
    task.setAutoDelete(False)  # Python owns the task's lifetime, not Qt
    _running.add(task)

    def finished(*_):
        _running.discard(task)  # runs on the GUI thread, after the result arrived

    if on_done:
        task.signals.done.connect(on_done)
    if on_error:
        task.signals.failed.connect(on_error)
    task.signals.done.connect(finished)
    task.signals.failed.connect(finished)
    QThreadPool.globalInstance().start(task)
