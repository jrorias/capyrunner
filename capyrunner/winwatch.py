"""Windows helpers: which window is in front, which windows are open, which apps use the microphone.

Only plain Win32 calls through ctypes and one registry read: no extra packages, nothing kept or sent.
Everywhere else every function returns an empty answer.
"""
from __future__ import annotations

import sys

IS_WIN = sys.platform == "win32"
_names: dict[int, str] = {}           # pid -> program name (cached; looking it up is the slow part)


def _proc_name(pid: int) -> str:
    name = _names.get(pid)
    if name is None:
        try:
            import psutil
            name = psutil.Process(pid).name().lower()
        except Exception:
            name = ""
        if len(_names) > 500:
            _names.clear()
        _names[pid] = name
    return name


if IS_WIN:
    import ctypes
    from ctypes import wintypes

    _user32 = ctypes.WinDLL("user32", use_last_error=True)
    _user32.GetForegroundWindow.restype = wintypes.HWND
    _user32.GetWindowTextLengthW.argtypes = [wintypes.HWND]
    _user32.GetWindowTextW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
    _user32.GetWindowThreadProcessId.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.DWORD)]
    _user32.IsWindowVisible.argtypes = [wintypes.HWND]
    _user32.IsIconic.argtypes = [wintypes.HWND]
    _ENUM = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    _user32.GetWindowRect.argtypes = [wintypes.HWND, ctypes.POINTER(wintypes.RECT)]
    _user32.MonitorFromWindow.restype = wintypes.HANDLE
    _user32.MonitorFromWindow.argtypes = [wintypes.HWND, wintypes.DWORD]
    _user32.GetShellWindow.restype = wintypes.HWND
    _user32.GetDesktopWindow.restype = wintypes.HWND

    class _MONITORINFO(ctypes.Structure):
        _fields_ = [("cbSize", wintypes.DWORD), ("rcMonitor", wintypes.RECT), ("rcWork", wintypes.RECT),
                    ("dwFlags", wintypes.DWORD)]

    _user32.GetMonitorInfoW.argtypes = [wintypes.HANDLE, ctypes.POINTER(_MONITORINFO)]

    def _title(hwnd) -> str:
        n = _user32.GetWindowTextLengthW(hwnd)
        if n <= 0:
            return ""
        buf = ctypes.create_unicode_buffer(n + 1)
        _user32.GetWindowTextW(hwnd, buf, n + 1)
        return buf.value

    def _pid(hwnd) -> int:
        pid = wintypes.DWORD()
        _user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        return pid.value


def foreground() -> tuple[str, str]:
    """(program name, window title) of the window in front, lower-cased. ('', '') if unknown."""
    if not IS_WIN:
        return "", ""
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd:
            return "", ""
        return _proc_name(_pid(hwnd)), _title(hwnd).lower()
    except Exception:
        return "", ""


def fullscreen() -> bool:
    """Is the window in front covering its whole screen (a film, a game, slides being presented)?"""
    if not IS_WIN:
        return False
    try:
        hwnd = _user32.GetForegroundWindow()
        if not hwnd or hwnd in (_user32.GetShellWindow(), _user32.GetDesktopWindow()):
            return False
        r = wintypes.RECT()
        _user32.GetWindowRect(hwnd, ctypes.byref(r))
        mi = _MONITORINFO()
        mi.cbSize = ctypes.sizeof(_MONITORINFO)
        _user32.GetMonitorInfoW(_user32.MonitorFromWindow(hwnd, 2), ctypes.byref(mi))
        m = mi.rcMonitor
        if _proc_name(_pid(hwnd)) == "explorer.exe":     # the desktop itself
            return False
        return r.left <= m.left and r.top <= m.top and r.right >= m.right and r.bottom >= m.bottom
    except Exception:
        return False


def media_key(cmd: str) -> None:
    """Press a media key: play-pause | next | previous (works with Spotify, browsers, any media app)."""
    if not IS_WIN:
        return
    vk = {"play-pause": 0xB3, "next": 0xB0, "previous": 0xB1}.get(cmd)
    if vk:
        _user32.keybd_event(vk, 0, 0, 0)
        _user32.keybd_event(vk, 0, 2, 0)            # KEYEVENTF_KEYUP


def windows() -> list[tuple[str, str]]:
    """(program name, title) of every visible, titled top-level window, lower-cased."""
    if not IS_WIN:
        return []
    out: list[tuple[str, str]] = []

    def cb(hwnd, _):
        try:
            if _user32.IsWindowVisible(hwnd):
                t = _title(hwnd)
                if t:
                    out.append((_proc_name(_pid(hwnd)), t.lower()))
        except Exception:
            pass
        return True

    try:
        _user32.EnumWindows(_ENUM(cb), 0)
    except Exception:
        return []
    return out


def mic_users() -> list[str]:
    """Programs using the microphone right now (Windows 10 1903+ keeps this in the registry), lower-cased."""
    if not IS_WIN:
        return []
    import winreg
    root = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone"
    found: list[str] = []

    def scan(path: str, nonpackaged: bool):
        try:
            key = winreg.OpenKey(winreg.HKEY_CURRENT_USER, path)
        except OSError:
            return
        with key:
            i = 0
            while True:
                try:
                    sub = winreg.EnumKey(key, i)
                except OSError:
                    break
                i += 1
                if sub == "NonPackaged":
                    continue
                try:
                    with winreg.OpenKey(key, sub) as k:
                        stop, _ = winreg.QueryValueEx(k, "LastUsedTimeStop")
                        start, _ = winreg.QueryValueEx(k, "LastUsedTimeStart")
                except OSError:
                    continue
                if stop == 0 and start:          # started and not stopped yet: in use now
                    name = sub.replace("#", "\\").rsplit("\\", 1)[-1] if nonpackaged else sub
                    found.append(name.lower())

    scan(root, False)
    scan(root + r"\NonPackaged", True)
    return found
