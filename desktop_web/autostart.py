r"""
"Start JobLens with Windows" (14e, D31).

    on  -> HKCU\...\CurrentVersion\Run\JobLens = "<JobLens.exe>" --tray
           Windows starts JobLens at sign-in, hidden in the tray, so the
           follow-up reminders can reach you without opening the app.
    off -> the value is removed.

Per user, no admin rights (the same place Task Manager's Startup tab lists).
The registry is the only record: Settings asks it each time, so turning it
off in Task Manager shows up as off here too. Only the installed app can do
this: in developer mode sys.executable is python.exe. The uninstaller
removes the value (installer/joblens.iss, [Registry]).
"""

import sys

from job_agent import paths

RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
VALUE = "JobLens"
TRAY_ARG = "--tray"


def supported() -> bool:
    return paths.IS_INSTALLED and sys.platform == "win32"


def command() -> str:
    return f'"{sys.executable}" {TRAY_ARG}'


def enabled(key: str = RUN_KEY) -> bool:
    """True if Windows will start this JobLens (this exe) at sign-in."""
    if sys.platform != "win32":
        return False
    import winreg
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key) as handle:
            value, _ = winreg.QueryValueEx(handle, VALUE)
    except OSError:  # no key or no value: off
        return False
    return sys.executable.lower() in str(value).lower()


def set_enabled(on: bool, key: str = RUN_KEY) -> bool:
    """Turn it on or off. Returns the new state."""
    if not supported():
        raise RuntimeError("Starting with Windows works in the installed JobLens only.")
    import winreg
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, key) as handle:
        if on:
            winreg.SetValueEx(handle, VALUE, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(handle, VALUE)
            except FileNotFoundError:
                pass
    return enabled(key)
