"""Settings + data storage (plain JSON in the user's config folder)."""
from __future__ import annotations

import copy
import json
import os
import tempfile
import uuid
from datetime import datetime

from PySide6.QtCore import QStandardPaths

from .workmode import DEFAULT_MODE

DEFAULT_SETTINGS = {
    "character": "capy",          # capy | capybara | cat | dog | dots | custom
    "color": "#1F2A5A",          # main colour (hoodie colour for Capy)
    "custom_path": "",
    "sprite_frames": 0,           # 0 = auto-detect square frames
    "speed_source": "mix",        # cpu | tasks | mix
    "show_tray": True,
    "show_pet": True,
    "pet_size": 96,               # height of the pet in px
    "pet_width": 100,             # width as a % of the height (100 = as drawn; 70 = slimmer, 140 = wider)
    "pet_lift": 0,                # px above the bottom of the screen for the running line and the seat
    "pet_pos": None,              # [x, y]
    # ---- where he sits when he joins in (calls, work modes, music, videos…) ---- #
    "seat_side": "right",         # right | left | center | stay (right where he is)
    "seat_screen": "same",        # same (the screen he is on) | main (the main screen)
    # ---- look of the app windows (see uitheme.py) ------------------------------ #
    "ui_theme": "system",         # system | light | dark | capytech | ocean | forest | sakura | fiesta
    "pet_ghost": False,           # fully click-through: can't be touched at all (control it from the tray)
    "activity_mode": "auto",      # auto | listen | watch | movie | study | read : how he joins in
    "activity_caption": True,     # small line above him with the mode icon and what is playing
    "study_words": [],            # extra words / channel names that mean "this is a tutorial or podcast"
    "bubble_font": 13,            # speech bubble text size in px (10-18)
    "activity_react": True,       # headphones for music, popcorn for videos, a book when you read
    # ---- wellbeing ------------------------------------------------------ #
    "break_remind": True,         # suggest a stretch after a long time at the screen
    "break_every": 50,            # …this many minutes
    "breathe_minutes": 2,         # length of the breathing exercise (1-5)
    "focus_minutes": 25,          # length of a focus session
    "focus_quiet_system": True,   # focus session also holds other apps' pop-ups (mako do-not-disturb)
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
    # ---- weekday adventures (see themes.py) ----------------------------- #
    "day_theme": "auto",          # auto = follow the week plan | classic | hike | space | jungle | fiesta
    "week_themes": ["classic", "hike", "space", "jungle", "fiesta", "classic", "classic"],   # Monday … Sunday
    "adventure_talk": True,       # tells the story of the day in the speech bubble
    # ---- Jeo, the friend, and dance showdowns (see dance.py) ------------- #
    "friend_on": True,            # Jeo turns up for dance showdowns
    # ---- 3D avatars and voices (see model3d.py, voice.py, avatar_studio.py) ---- #
    "avatar_3d": True,            # Primo and the friend in 3D (run, jump, nap, talk); other poses stay drawn
    "look3d_main": None,          # the 3D look, part by part (None = made from the 2D avatar)
    "look3d_friend": None,
    "voice_on": False,            # read the speech bubbles out loud
    "voice_volume": 0.9,
    "voice_min_ms": 2500,         # only bubbles that stay up at least this long (not "🔊 40%" or a countdown)
    "voice_main": None,           # {"voice", "pitch", "speed"} (None = the default voice)
    "voice_friend": None,
    "friend_name": "Jeo OngBack",
    "dance_songs": True,          # a showdown starts when a dance song is playing
    "dance_every": 30,            # …and every this many minutes Jeo turns up with a challenge (0 = never)
    "dance_extra": [],            # your own dance songs: words from the title or artist
    # ---- calls (see meeting.py) ------------------------------------------ #
    "meeting_look": True,         # in a call (Meet, Zoom, Teams…): office clothes and a headset
    "meeting_mic": True,          # …and he talks when the microphone hears you (loudness only, nothing is kept)
    "space_trip_day": "",
    # ---- work modes (see workmode.py): on the office chair with the laptop ------ #
    "work_on": True,
    "work_modes": [DEFAULT_MODE],
    # ---- avatars (see avatars.py): pet_name / color above are the on-screen avatar's name and jacket ---- #
    "avatar": "primo",            # primo | jeo | geelee | koko | luna | tito | custom
    "avatar_fur": "#C98A50",
    "avatar_acc": "",             # headwear: '' | bandana | bow | flower | cap | crown
    "avatar_acc_color": "#D62839",
    "friend_avatar": "jeo",       # the dance friend (friend_name above is his / her name)
    "friend_fur": "#E3B273",
    "friend_color": "#12857E",
    "friend_acc": "bandana",
    "friend_acc_color": "#D62839",
    "ride_friend": True,          # the friend rides along behind on the animals
    # ---- wardrobe, coffee, rides (see rides.py) ---------------------------- #
    "my_color_always": False,     # wear my jacket colour on adventure days too (instead of the day's outfit colour)
    "cup_color": "#E8762B",       # his coffee mug
    "coffee_breaks": True,        # some naps after a lap are a coffee break instead
    "dance_mood": True,           # upbeat / love songs start a dance too (style picked from the mood)
    "rides_on": True,
    "ride_every": 40,             # minutes between rides across the screen (0 = only when you ask)
    "ride_animals": ["dragon", "eagle", "parrot", "lion", "tiger", "wolf", "whale"],
    "ride_colors": {},            # animal -> colour, when changed from the default
    # ---- updates (see updater.py) ------------------------------------------ #
    "update_check": True,         # look for a new version once a day (reads GitHub's public release page)
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
        self.settings = {**copy.deepcopy(DEFAULT_SETTINGS), **_read(self.settings_path, {})}
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
