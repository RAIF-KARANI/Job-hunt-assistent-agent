"""
The quick-analyze shortcut (14f, D32): Ctrl+Alt+J anywhere in Windows opens
the small "paste a link" box, even with the JobLens window in the tray.

Windows delivers a global hotkey (RegisterHotKey) as a WM_HOTKEY message to
the thread that registered it, so the listener owns a thread with its own
message loop. A new key from Settings is handed to that thread with a
posted message: only it may unregister and register again.

parse() is a pure function (tests/test_quick.py); the listener needs Windows.
"""

import ctypes
import sys
import threading
from ctypes import wintypes
from typing import Callable

DEFAULT = "Ctrl+Alt+J"

MOD_ALT, MOD_CONTROL, MOD_SHIFT, MOD_WIN, MOD_NOREPEAT = 0x1, 0x2, 0x4, 0x8, 0x4000
MODIFIERS = {"ctrl": MOD_CONTROL, "alt": MOD_ALT, "shift": MOD_SHIFT, "win": MOD_WIN}
ORDER = ("Ctrl", "Alt", "Shift", "Win")
WM_HOTKEY, WM_APP_REREGISTER, WM_QUIT = 0x0312, 0x8001, 0x0012
HOTKEY_ID = 1


def _key_code(name: str) -> int | None:
    """'J' -> 0x4A, '7' -> 0x37, 'F9' -> 0x78. Letters, digits and F1-F12 only."""
    name = name.upper()
    if len(name) == 1 and (name.isascii() and name.isalnum()):
        return ord(name)
    if name.startswith("F") and name[1:].isdigit() and 1 <= int(name[1:]) <= 12:
        return 0x70 + int(name[1:]) - 1
    return None


def parse(text: str) -> tuple[int, int, str]:
    """'ctrl + alt + j' -> (modifiers, virtual key, 'Ctrl+Alt+J').

    Needs Ctrl or Alt (a plain letter would fire while you type) and one key.
    Raises ValueError with a message for the Settings screen."""
    parts = [p.strip() for p in (text or "").split("+") if p.strip()]
    mods, keys = 0, []
    for part in parts:
        if part.lower() in MODIFIERS:
            mods |= MODIFIERS[part.lower()]
        else:
            keys.append(part)
    if len(keys) != 1 or _key_code(keys[0]) is None:
        raise ValueError("Use one letter, digit or F1-F12 key with Ctrl and/or Alt, e.g. Ctrl+Alt+J.")
    if not mods & (MOD_CONTROL | MOD_ALT):
        raise ValueError("The shortcut needs Ctrl or Alt, so it doesn't fire while you type.")
    names = [name for name in ORDER if mods & MODIFIERS[name.lower()]]
    return mods, _key_code(keys[0]), "+".join([*names, keys[0].upper()])


class HotkeyListener:
    """One global hotkey. `on_press` runs on the listener's thread: keep it short."""

    def __init__(self, on_press: Callable[[], None]):
        self._on_press = on_press
        self._thread_id = None
        self._ready = threading.Event()
        self._wanted: str | None = None
        self.key: str | None = None      # the registered key, e.g. "Ctrl+Alt+J"
        self.error: str | None = None    # why it isn't registered

    def start(self, key: str | None) -> None:
        if sys.platform != "win32":
            self.error = "Global shortcuts work on Windows only."
            return
        self._wanted = key
        threading.Thread(target=self._loop, name="joblens-hotkey", daemon=True).start()
        self._ready.wait(5)

    def change(self, key: str | None) -> None:
        """A new key from Settings (None or "off" = no shortcut). Returns at once;
        status() shows the outcome a moment later."""
        self._wanted = key
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_APP_REREGISTER, 0, 0)

    def status(self) -> dict:
        return {"key": self.key, "error": self.error}

    def stop(self) -> None:
        if self._thread_id:
            ctypes.windll.user32.PostThreadMessageW(self._thread_id, WM_QUIT, 0, 0)

    # -- the listener's own thread --
    def _register(self) -> None:
        user32 = ctypes.windll.user32
        if self.key:
            user32.UnregisterHotKey(None, HOTKEY_ID)
            self.key = None
        self.error = None
        wanted = (self._wanted or "").strip()
        if not wanted or wanted.lower() == "off":
            return
        try:
            mods, vk, name = parse(wanted)
        except ValueError as e:
            self.error = str(e)
            return
        if user32.RegisterHotKey(None, HOTKEY_ID, mods | MOD_NOREPEAT, vk):
            self.key = name
        else:
            self.error = f"{name} is already used by another program. Choose another shortcut in Settings."

    def _loop(self) -> None:
        user32 = ctypes.windll.user32
        self._thread_id = ctypes.windll.kernel32.GetCurrentThreadId()
        msg = wintypes.MSG()
        user32.PeekMessageW(ctypes.byref(msg), None, 0, 0, 0)  # creates this thread's message queue
        self._register()
        self._ready.set()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            if msg.message == WM_HOTKEY and msg.wParam == HOTKEY_ID:
                try:
                    self._on_press()
                except Exception as e:  # a shortcut is never worth a crash
                    print(f"! quick analyze: {e}")
            elif msg.message == WM_APP_REREGISTER:
                self._register()
        if self.key:
            user32.UnregisterHotKey(None, HOTKEY_ID)
