"""Is the user in a call, and are they speaking right now?

In a call:  a meeting window is open (Google Meet, Zoom, Teams…; Hyprland only), or a meeting app or
            browser is recording from the microphone (PipeWire / PulseAudio, via `pactl`).
Speaking:   only while in a call, the loudness of the default microphone is measured. The sound is read
            in small pieces, turned into one number (how loud) and thrown away: nothing is recorded,
            saved or sent anywhere. A muted microphone is silent, so Primo stays quiet too.
            It cannot see the mute button inside the meeting app, only the system microphone.

Windows: a meeting window title (Zoom Meeting, Meet - …, … | Microsoft Teams) or a meeting app / browser
            using the microphone (from the Windows privacy registry). Talking is not measured on Windows yet.
macOS: the answer is simply "no".
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import threading
import time
from array import array

from .wellbeing import MEETING_WORDS, _die_with_parent

CALL_APPS = ("zoom", "teams", "webex", "skype", "discord", "slack", "jitsi", "whereby", "telegram", "signal",
             "element", "mumble", "teamspeak", "wire")
BROWSERS = ("chromium", "chrome", "firefox", "brave", "edge", "vivaldi", "opera", "zen", "librewolf", "floorp",
            "epiphany", "helium", "thorium")
OWN = "capyrunner-mic"


def _run(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=1).stdout
    except Exception:
        return ""


def _meeting_window() -> str:
    """Name of a meeting found among the open windows ('' = none). Hyprland only."""
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return ""
    try:
        clients = json.loads(_run("hyprctl", "clients", "-j") or "[]")
    except ValueError:
        return ""
    for c in clients:
        text = f"{c.get('class', '')} {c.get('title', '')}".lower()
        for w in MEETING_WORDS:
            if w in text:
                return "Google Meet" if w.startswith(("meet", "google meet")) else w.strip(" -–").title()
    return ""


def _mic_user() -> str:
    """Name of a meeting app or browser that is recording from the microphone right now ('' = none)."""
    if not shutil.which("pactl"):
        return ""
    try:
        outs = json.loads(_run("pactl", "-f", "json", "list", "source-outputs") or "[]")
    except ValueError:
        return ""
    for o in outs:
        props = o.get("properties") or {}
        name = " ".join(str(props.get(k, "")) for k in ("application.name", "application.process.binary")).lower()
        if OWN in name or not name.strip():
            continue
        if any(a in name for a in CALL_APPS + BROWSERS):
            return str(props.get("application.name") or "a call")
    return ""


# Windows: meeting windows are told apart from the app's main window by their title
WIN_MEETING_TITLES = (("zoom meeting", "Zoom"), ("zoom webinar", "Zoom"), ("meet - ", "Google Meet"),
                      ("meet – ", "Google Meet"), ("meeting | microsoft teams", "Teams"),
                      ("call | microsoft teams", "Teams"), ("meeting in ", "Teams"), ("webex meeting", "Webex"),
                      ("jitsi meet", "Jitsi"), ("whereby", "Whereby"), ("huddle", "Slack huddle"))


def _windows_call() -> str:
    from . import winwatch
    for prog, title in winwatch.windows():
        for words, name in WIN_MEETING_TITLES:
            if words in title:
                return name
    for prog in winwatch.mic_users():
        if any(a in prog for a in CALL_APPS + BROWSERS + ("ms-teams", "msteams")):
            return prog.rsplit(".", 1)[0].title() if prog.endswith(".exe") else "a call"
    return ""


def detect() -> str:
    """What call the user is in ('' = not in one)."""
    if sys.platform == "win32":
        return _windows_call()
    if not sys.platform.startswith("linux"):
        return ""
    return _meeting_window() or _mic_user()


class MicMeter:
    """Measures how loud the microphone is, to tell when the user is speaking."""
    RATE = 16000
    CHUNK = 1600                      # bytes: 800 samples = 50 ms

    def __init__(self):
        self.proc: subprocess.Popen | None = None
        self.level = 0.0              # loudness of the last piece (0..32767)
        self.floor = 200.0            # the room's background noise, learned as it goes
        self.loud_at = 0.0            # last time it was clearly louder than the room
        self.started = 0.0

    @property
    def running(self) -> bool:
        return self.proc is not None and self.proc.poll() is None

    def start(self) -> bool:
        if self.running:
            return True
        if not (sys.platform.startswith("linux") and shutil.which("parec")):
            return False
        try:
            self.proc = subprocess.Popen(
                ["parec", f"--client-name={OWN}", "--format=s16le", f"--rate={self.RATE}", "--channels=1",
                 "--latency-msec=50"],
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, preexec_fn=_die_with_parent)
        except OSError:
            self.proc = None
            return False
        self.started = time.time()
        threading.Thread(target=self._read, args=(self.proc,), daemon=True).start()
        return True

    def _read(self, proc: subprocess.Popen):
        while True:
            data = proc.stdout.read(self.CHUNK)
            if not data or len(data) < 2:
                break
            samples = array("h")
            samples.frombytes(data[: len(data) // 2 * 2])
            mean = sum(samples) / len(samples)        # some microphones sit off-centre: measure around the middle
            rms = (sum((v - mean) ** 2 for v in samples) / len(samples)) ** 0.5
            self.level = rms
            # the quietest it gets is the room; it creeps up slowly so a noisy room is learned too
            self.floor = min(max(rms, 60.0), self.floor * 1.01)
            if rms > max(self.floor * 2.8, 450.0) and time.time() - self.started > 0.8:   # (skip the click as it opens)
                self.loud_at = time.time()
        self.level = 0.0

    @property
    def speaking(self) -> bool:
        """True while speaking, and through the short gaps between words."""
        return self.running and time.time() - self.loud_at < 0.45

    def stop(self):
        if self.proc is not None and self.proc.poll() is None:
            self.proc.terminate()
        self.proc = None
        self.level = 0.0
