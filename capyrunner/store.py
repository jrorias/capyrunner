"""Settings + data storage (plain JSON in the user's config folder)."""
from __future__ import annotations

import json
import os
import tempfile
import uuid
from datetime import datetime

from PySide6.QtCore import QStandardPaths

DEFAULT_SETTINGS = {
    "character": "capy",          # capy | capybara | cat | dog | dots | custom
    "color": "#1F2A5A",          # main colour (hoodie colour for Capy)
    "custom_path": "",
    "sprite_frames": 0,           # 0 = auto-detect square frames
    "speed_source": "mix",        # cpu | tasks | mix
    "show_tray": True,
    "show_pet": True,
    "pet_size": 96,
    "pet_pos": None,              # [x, y]
    "pet_passthrough": True,      # pet never takes keyboard focus, clicks or scrolling (control it from the tray)
    "pet_roam": True,             # run back and forth along the bottom of the screen
    "greetings": False,           # say hello + friendly reminders in the speech bubble
    "max_fps": 14,
    "dnd": False,
    "webhook_enabled": False,
    "webhook_port": 8765,
    "webhook_token": "",
    "autostart": False,
    # ---- mascot personality -------------------------------------------- #
    "pet_name": "Primo",
    "rope_color": "#C79A5B",
    # words: {name} = the mascot's name, {greet} = Good morning / afternoon / evening. Empty = say nothing.
    "say_click": ["{greet}! 👋", "Hi hi! 🐾", "Need a task? Middle-click the tray 😉"],
    "say_cheers": ["Keep going! 💪", "You're doing great! ⭐", "Water break? 💧", "Stretch time! 🙆",
                   "Taco break? 🌮", "One task at a time 🐾", "Don't forget to save your work 💾",
                   "{name} believes in you! 🧡"],
    "say_hello": "{greet}! I'm {name} 👋",
    "say_top": "Tabi tabi po… 🤫",          # sneaking along the top edge
    "say_fall": "Ay! Oh no!! 😱",           # clicked off the rope
    "say_laugh": "Hahaha! 😂",              # laughing it off afterwards
    "say_grab": "Hey! Put me down! 😠",     # picked up with the mouse
    "say_tampo": "Hmp! Tampo ako. 😤",      # sulking after being put down
    "say_forgive": "Sige na nga… bati na tayo 🥺",   # clicked while sulking
    "grab_tampo": True,           # gets angry when grabbed, then sulks for a bit
    # ---- lap behaviour -------------------------------------------------- #
    "lap_falls": True,            # sometimes slips while climbing
    "lap_click_fall": True,       # clicking the pet on the rope knocks it off
    "lap_sneak": True,            # tiptoe and look around on the top edge
    "nap_seconds": 60,            # how long the nap after a lap lasts (roughly)
}


def config_dir() -> str:
    base = QStandardPaths.writableLocation(QStandardPaths.GenericConfigLocation)
    path = os.path.join(base, "CapyRunner")
    os.makedirs(path, exist_ok=True)
    return path


def _atomic_write(path: str, obj) -> None:
    fd, tmp = tempfile.mkstemp(dir=os.path.dirname(path), suffix=".tmp")
    with os.fdopen(fd, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)


def _read(path: str, default):
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return default


def now_iso() -> str:
    return datetime.now().replace(microsecond=0).isoformat()


def new_id() -> str:
    return uuid.uuid4().hex[:10]


class Store:
    def __init__(self, folder: str | None = None):
        self.folder = folder or config_dir()
        os.makedirs(self.folder, exist_ok=True)
        self.settings_path = os.path.join(self.folder, "settings.json")
        self.data_path = os.path.join(self.folder, "data.json")
        self.settings = {**DEFAULT_SETTINGS, **_read(self.settings_path, {})}
        data = _read(self.data_path, {})
        self.tasks: list[dict] = data.get("tasks", [])
        self.notes: list[dict] = data.get("notes", [])
        self.notifications: list[dict] = data.get("notifications", [])

    # ---- persistence --------------------------------------------------- #
    def save_settings(self) -> None:
        _atomic_write(self.settings_path, self.settings)

    def save_data(self) -> None:
        self.notifications = self.notifications[-300:]
        _atomic_write(self.data_path, {
            "tasks": self.tasks, "notes": self.notes, "notifications": self.notifications})

    # ---- tasks ---------------------------------------------------------- #
    def add_task(self, title: str, due: str | None = None, notes: str = "") -> dict:
        t = {"id": new_id(), "title": title, "notes": notes, "due": due,
             "done": False, "reminded": False, "created": now_iso()}
        self.tasks.append(t)
        self.save_data()
        return t

    def task(self, tid: str) -> dict | None:
        return next((t for t in self.tasks if t["id"] == tid), None)

    def delete_task(self, tid: str) -> None:
        self.tasks = [t for t in self.tasks if t["id"] != tid]
        self.save_data()

    def task_counts(self) -> tuple[int, int, int]:
        """(overdue, due_today, open)"""
        now = datetime.now()
        overdue = today = open_ = 0
        for t in self.tasks:
            if t.get("done"):
                continue
            open_ += 1
            if t.get("due"):
                try:
                    d = datetime.fromisoformat(t["due"])
                except ValueError:
                    continue
                if d <= now:
                    overdue += 1
                elif d.date() == now.date():
                    today += 1
        return overdue, today, open_

    # ---- notes ---------------------------------------------------------- #
    def add_note(self, title: str = "New note", body: str = "") -> dict:
        n = {"id": new_id(), "title": title, "body": body, "updated": now_iso()}
        self.notes.insert(0, n)
        self.save_data()
        return n

    # ---- notifications -------------------------------------------------- #
    def add_notification(self, title: str, body: str = "", source: str = "app") -> dict:
        n = {"id": new_id(), "title": title, "body": body, "source": source,
             "time": now_iso(), "read": False}
        self.notifications.append(n)
        self.save_data()
        return n

    def unread(self) -> int:
        return sum(1 for n in self.notifications if not n.get("read"))

    def mark_all_read(self) -> None:
        for n in self.notifications:
            n["read"] = True
        self.save_data()
