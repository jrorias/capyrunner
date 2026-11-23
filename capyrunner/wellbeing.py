"""Wellbeing helpers: is the user at the keyboard, the breathing rhythm, quiet mode for other apps.

Everything stays on this computer: nothing here is saved or sent anywhere.
"""
from __future__ import annotations

import os
import shutil
import signal
import subprocess
import sys
import time

IDLE_AFTER = 60          # seconds without input before the compositor calls it "idle"
MEETING_WORDS = ("zoom", "meet.google", "google meet", "meet - ", "meet – ", "microsoft teams", "teams meeting",
                 "webex", "jitsi", "huddle", "whereby", "skype", "bigbluebutton", "gather.town")
MAKO_MODE = "do-not-disturb"


def fmt_clock(seconds: float) -> str:
    seconds = max(0, int(seconds + 0.999))
    return f"{seconds // 60}:{seconds % 60:02d}"


def in_meeting(wclass: str, wtitle: str) -> bool:
    text = f"{wclass} {wtitle}"
    return any(w in text for w in MEETING_WORDS)


# --------------------------------------------------------------------------- #
# breathing: "cyclic sighing" = two inhales through the nose, then one long slow exhale
# --------------------------------------------------------------------------- #
BREATH_STEPS = ((2.0, 0.0, 0.7, "Breathe in…"), (1.0, 0.7, 1.0, "…a little more"), (6.0, 1.0, 0.0, "Breathe out slowly…"))
BREATH_CYCLE = sum(step[0] for step in BREATH_STEPS)


def breath(elapsed: float) -> tuple[float, bool, str]:
    """(how full the lungs are 0..1, exhaling?, what to say) at `elapsed` seconds into the exercise."""
    t = elapsed % BREATH_CYCLE
    for dur, a, b, text in BREATH_STEPS:
        if t < dur:
            k = t / dur
            k = k * k * (3 - 2 * k)                   # ease in and out
            return a + (b - a) * k, b < a, text
        t -= dur
    return 0.0, True, BREATH_STEPS[-1][3]


# --------------------------------------------------------------------------- #
# idle time
# --------------------------------------------------------------------------- #
class IdleWatch:
    """How long since the last key press or mouse move.

    Hyprland: a private `hypridle` (it can run next to the system one) writes a small flag file when the
    session goes idle and removes it on the next input. Windows: GetLastInputInfo. Elsewhere: we only
    see the mouse pointer move.
    """

    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.flag = ""
        self._cursor = None
        self._cursor_t = time.time()
        if sys.platform.startswith("linux") and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE") and shutil.which("hypridle"):
            self._start_hypridle()

    def _start_hypridle(self):
        folder = os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "capyrunner")
        try:
            os.makedirs(folder, exist_ok=True)
            self.flag = os.path.join(folder, "idle")
            conf = os.path.join(folder, "hypridle.conf")
            if os.path.exists(self.flag):
                os.remove(self.flag)
            with open(conf, "w", encoding="utf-8") as f:
                f.write("general {\n    ignore_dbus_inhibit = true\n    ignore_systemd_inhibit = true\n"
                        "    inhibit_sleep = 0\n}\n"
                        f"listener {{\n    timeout = {IDLE_AFTER}\n    ignore_inhibit = true\n"
                        f"    on-timeout = date +%s > '{self.flag}'\n    on-resume = rm -f '{self.flag}'\n}}\n")
            self.proc = subprocess.Popen(["hypridle", "-c", conf], stdout=subprocess.DEVNULL,
                                         stderr=subprocess.DEVNULL, preexec_fn=_die_with_parent)
        except OSError:
            self.proc, self.flag = None, ""

    @property
    def exact(self) -> bool:
        """True when keyboard input is seen too (not just the mouse)."""
        return self.proc is not None or sys.platform == "win32"

    def seconds(self) -> float:
        if self.proc is not None:
            if self.proc.poll() is not None:          # it died: fall back to the mouse pointer
                self.proc = None
            else:
                try:
                    with open(self.flag, encoding="utf-8") as f:
                        return max(0.0, time.time() - int(f.read().strip())) + IDLE_AFTER
                except (OSError, ValueError):
                    return 0.0
        if sys.platform == "win32":
            try:
                import ctypes

                class LASTINPUTINFO(ctypes.Structure):
                    _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]
                info = LASTINPUTINFO()
                info.cbSize = ctypes.sizeof(info)
                if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(info)):
                    return max(0.0, ((ctypes.windll.kernel32.GetTickCount() - info.dwTime) & 0xFFFFFFFF) / 1000.0)
            except Exception:
                pass
        from PySide6.QtGui import QCursor
        pos = QCursor.pos()
        cur = (pos.x(), pos.y())
        if cur != self._cursor:
            self._cursor, self._cursor_t = cur, time.time()
        return time.time() - self._cursor_t

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
        self.proc = None


def _die_with_parent():
    """Linux: the helper must not outlive Primo, even if he is killed."""
    try:
        import ctypes
        ctypes.CDLL("libc.so.6").prctl(1, signal.SIGTERM)        # PR_SET_PDEATHSIG
    except Exception:
        pass


# --------------------------------------------------------------------------- #
# quiet mode for other apps' notifications during a focus session (mako only)
# --------------------------------------------------------------------------- #
def _mako_modes() -> list[str] | None:
    if not (sys.platform.startswith("linux") and shutil.which("makoctl")):
        return None
    try:
        r = subprocess.run(["makoctl", "mode"], capture_output=True, text=True, timeout=1)
    except Exception:
        return None
    return r.stdout.split() if r.returncode == 0 else None


def _marker() -> str:
    return os.path.join(os.environ.get("XDG_RUNTIME_DIR") or "/tmp", "capyrunner", "quiet")


def quiet_on() -> bool:
    """Hold other apps' pop-ups. Returns True when we switched it on (so we must switch it off)."""
    modes = _mako_modes()
    if modes is None or MAKO_MODE in modes:
        return False                                  # no mako, or you already had it on: leave it alone
    try:
        subprocess.run(["makoctl", "mode", "-a", MAKO_MODE], capture_output=True, timeout=1)
        os.makedirs(os.path.dirname(_marker()), exist_ok=True)
        open(_marker(), "w").close()
    except Exception:
        return False
    return True


def quiet_off() -> None:
    try:
        subprocess.run(["makoctl", "mode", "-r", MAKO_MODE], capture_output=True, timeout=1)
    except Exception:
        pass
    try:
        os.remove(_marker())
    except OSError:
        pass


def quiet_recover() -> None:
    """At start-up: if Primo died during a focus session, give the notifications back."""
    if os.path.exists(_marker()):
        quiet_off()
