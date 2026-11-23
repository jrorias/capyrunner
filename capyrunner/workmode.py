"""Work modes: while you work in a chosen app, Primo sits on his office chair and types on his laptop.

The first one is "Storyline time" (Articulate Storyline), and you can add your own: give it a name, the apps
(words from the program name or the window title), the days it is on, and how Primo looks.

Seen from the window in front (Windows; Hyprland or X11 with xdotool on Linux), or, if you choose,
from any open window. Only names and titles are compared; nothing is kept or sent.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import date

from . import winwatch

LOOKS = {"hoodie": "His own hoodie", "office": "Office: blazer and tie, headset", "adventure": "The outfit of the day"}
DAY_SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
# where he sits to join in (calls, work modes, music…): setting value, label
SEAT_SIDES = (("right", "↘  Bottom right"), ("left", "↙  Bottom left"), ("center", "⬇  Bottom middle"),
              ("top_right", "↗  Top right"), ("top_left", "↖  Top left"), ("stay", "📍  Right where he is"))
GRACE = 45                    # seconds a mode stays on after the app leaves the front (a quick look at email…)

DEFAULT_MODE = {
    "on": True,
    "name": "Storyline time",
    "apps": ["Articulate Storyline", "Storyline 360", "Storyline.exe"],
    "days": [0, 1, 2, 3, 4],              # Monday … Friday
    "when": "front",                      # front = while the app is the window in front | open = while it is open
    "look": "hoodie",
    "chair": "#3B4A63",
    "glasses": True,
    "say": "💻 {mode}! Let's build a great course.",
    "icon": "💻",
}


def new_mode(name: str = "New work mode") -> dict:
    return {**DEFAULT_MODE, "name": name, "apps": [], "say": "💻 {mode}!"}


def modes(settings: dict) -> list[dict]:
    """The user's modes, each filled up with defaults for anything missing."""
    out = []
    for m in settings.get("work_modes") or []:
        if isinstance(m, dict):
            out.append({**DEFAULT_MODE, **m})
    return out


@dataclass
class Work:
    index: int = -1           # which mode (position in the list); -1 = none
    name: str = ""
    app: str = ""             # the word that matched, as the user typed it

    def __bool__(self) -> bool:
        return self.index >= 0


def _run(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=1).stdout
    except Exception:
        return ""


def _front() -> tuple[str, str]:
    """(program / class, title) of the window in front, lower-cased."""
    if sys.platform == "win32":
        return winwatch.foreground()
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        try:
            w = json.loads(_run("hyprctl", "activewindow", "-j") or "{}")
        except ValueError:
            return "", ""
        return str(w.get("class", "")).lower(), str(w.get("title", "")).lower()
    if os.environ.get("DISPLAY") and shutil.which("xdotool"):
        return "", _run("xdotool", "getactivewindow", "getwindowname").strip().lower()
    return "", ""


def _open_windows() -> list[tuple[str, str]]:
    if sys.platform == "win32":
        return winwatch.windows()
    if os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        try:
            return [(str(c.get("class", "")).lower(), str(c.get("title", "")).lower())
                    for c in json.loads(_run("hyprctl", "clients", "-j") or "[]")]
        except ValueError:
            return []
    return [_front()]


def _match(apps: list[str], wins: list[tuple[str, str]]) -> str:
    for word in apps:
        w = word.strip().lower()
        if w and any(w in prog or w in title for prog, title in wins):
            return word.strip()
    return ""


class WorkWatch:
    """Remembers the mode a little after its app leaves the front, so a quick alt-tab does not end it."""

    def __init__(self):
        self.current = Work()
        self.seen = 0.0

    def poll(self, settings: dict, today: date | None = None) -> Work:
        if not settings.get("work_on", True):
            self.current = Work()
            return self.current
        ms = modes(settings)
        day = (today or date.today()).weekday()
        live = [(i, m) for i, m in enumerate(ms) if m.get("on", True) and day in (m.get("days") or []) and m.get("apps")]
        found = Work()
        if live:
            front = [_front()]
            wins = None
            for i, m in live:
                if m.get("when") == "open":
                    wins = wins if wins is not None else _open_windows()
                    hit = _match(m["apps"], wins)
                else:
                    hit = _match(m["apps"], front)
                if hit:
                    found = Work(i, m.get("name") or "Work", hit)
                    break
        now = time.time()
        if found:
            self.current, self.seen = found, now
        elif self.current and now - self.seen < GRACE and self.current.index < len(ms) \
                and ms[self.current.index].get("on", True):
            pass                                   # keep it a little longer
        else:
            self.current = Work()
        return self.current
