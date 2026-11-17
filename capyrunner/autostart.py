"""Start-on-login for Linux (XDG autostart) and Windows (HKCU Run key)."""
from __future__ import annotations

import os
import shutil
import sys

APP = "CapyRunner"


def _launch_command() -> list[str]:
    exe = shutil.which("capyrunner")
    if getattr(sys, "frozen", False):          # PyInstaller build
        return [sys.executable]
    if exe:
        return [exe]
    py = sys.executable
    if sys.platform == "win32" and py.lower().endswith("python.exe"):
        py = py[:-10] + "pythonw.exe"
    return [py, "-m", "capyrunner"]


def _linux_file() -> str:
    base = os.environ.get("XDG_CONFIG_HOME", os.path.expanduser("~/.config"))
    return os.path.join(base, "autostart", "capyrunner.desktop")


def set_enabled(enabled: bool) -> str | None:
    """Returns an error message, or None on success."""
    try:
        if sys.platform.startswith("linux"):
            path = _linux_file()
            if enabled:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                cmd = " ".join(f'"{c}"' if " " in c else c for c in _launch_command())
                with open(path, "w", encoding="utf-8") as f:
                    f.write("[Desktop Entry]\nType=Application\nName=CapyRunner\n"
                            f"Exec={cmd}\nIcon=capyrunner\nX-GNOME-Autostart-enabled=true\n"
                            "X-GNOME-Autostart-Delay=5\nComment=Running mascot for tasks & notifications\n")
            elif os.path.exists(path):
                os.remove(path)
        elif sys.platform == "win32":
            import winreg
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                                 r"Software\Microsoft\Windows\CurrentVersion\Run", 0, winreg.KEY_SET_VALUE)
            if enabled:
                cmd = " ".join(f'"{c}"' for c in _launch_command())
                winreg.SetValueEx(key, APP, 0, winreg.REG_SZ, cmd)
            else:
                try:
                    winreg.DeleteValue(key, APP)
                except FileNotFoundError:
                    pass
            winreg.CloseKey(key)
        else:
            return "Autostart is only set up for Linux and Windows."
    except OSError as e:
        return f"Could not change autostart: {e}"
    return None
