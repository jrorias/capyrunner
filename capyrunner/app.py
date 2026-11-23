"""CapyRunner main controller: tray icon, floating pet, reminders, webhook."""
from __future__ import annotations

import argparse
import getpass
import math
import random
import shutil
import json
import os
import subprocess
import sys
import time
from datetime import date, datetime

import psutil
from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon, QPainter, QPixmap, QTransform
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QInputDialog, QMenu,
                               QMessageBox, QSystemTrayIcon)

from . import __version__, activity, autostart, avatars, dance, meeting, quickadd, rides, themes, uitheme, updater, wellbeing, workmode
from .controls import ControlPanel
from .characters import (BASE, BUILTIN, ROPE_X, FrameSet, desk_frames, friend_frames, load_frames, move_frames, office_frames,
                         friend_rider_frames, rider_frames,
                         poof_frames, with_badge)
from .panel import Panel
from .pet import PetWindow, RopeWindow
from .settings_dialog import SettingsDialog
from .store import Store
from .webhook import WebhookBridge, WebhookServer

IS_LINUX = sys.platform.startswith("linux")
SEAT_SIDES = workmode.SEAT_SIDES


class CapyRunner:
    def __init__(self, app: QApplication, store: Store):
        self.app = app
        self.store = store
        self.frames: FrameSet = FrameSet([])
        self.frame_i = 0
        self.level = 0.0
        self.sleeping = False
        self.excited_until = 0.0
        self.cpu = 0.0
        self._badge_cache: dict[tuple[int, int], QIcon] = {}

        self.panel = Panel(store)
        self.panel.changed.connect(self.update_stats)

        self.pet = PetWindow(store.settings["pet_size"])
        self.pet.open_panel.connect(self.panel.show_and_raise)
        self.pet.context_menu.connect(self.show_controls)
        self.pet.moved.connect(self._pet_moved)
        self.pet.clicked.connect(self._pet_clicked)
        self.pet.grabbed.connect(self._pet_grabbed)
        self.pet.released.connect(lambda: QTimer.singleShot(120, self._hypr_give_back))
        self.pet.missed.connect(self._pet_step_aside)
        self.pet.wheeled.connect(self._pet_step_aside)

        self.rope = RopeWindow()
        # Jeo, the friend who turns up for dance showdowns: a second pet window nobody can click
        # (same window title as the pet, so compositor rules written for the pet cover him too: no border,
        # no blur, no dimmed box behind him; Hyprland tells the two apart by his slightly wider window)
        self.friend = PetWindow(store.settings["pet_size"])
        self.friend.set_passthrough(True)
        self._size_friend()
        self.jeo_space: FrameSet | None = None
        self.jeo_space_flip: FrameSet | None = None
        self.trip: dict | None = None     # space day: Jeo is riding the rocket with Primo
        self.styles: dict = {}            # dance moves already drawn: (who, style, move) -> (frames, mirrored)
        self.last_style = ""
        self.poof: list = []              # the magician's puff shown while an outfit changes
        self.poof_until = 0.0
        # in a call: office look with a headset, talking when the microphone hears you (see meeting.py)
        self.meeting = ""                 # which call ('' = none)
        self.meeting_gone = 0             # polls in a row without one (a single miss does not end it)
        self.mic = meeting.MicMeter()
        self.office: dict | None = None
        self.office_flip: dict | None = None
        self.office_on = False            # wearing the office outfit right now
        # work modes (see workmode.py): on the office chair with the laptop while you work in Storyline…
        self.workwatch = workmode.WorkWatch()
        self.work = workmode.Work()
        self.desk: dict = {}              # (mode, look, theme) -> (frames, mirrored frames)
        self.jeo: FrameSet | None = None
        self.jeo_flip: FrameSet | None = None
        self.dance: dict | None = None    # the showdown going on right now (see dance.py)
        self.danced_label = ""            # the song the last showdown was for (no second one for the same song)
        self.next_dance = 0.0             # when they next dance just for fun
        # rides: now and then Primo crosses the screen on a dragon, an eagle, a lion, a whale… (see rides.py)
        self.ride_win = rides.RideWindow()
        self.ride_win.finished.connect(self._ride_done)
        self.next_ride = 0.0
        self.coffee = False               # this nap is a coffee break instead
        # updates: checked in the background once a day (see updater.py)
        self.update_info: dict | None = None
        self.updates = updater.Checker()
        self.updates.found.connect(self._update_found)
        self.updates.failed.connect(self._update_failed)
        self.updates.ready.connect(self.quit)
        self.updates.install_failed.connect(
            lambda why: QMessageBox.warning(None, "CapyRunner", f"The update could not finish:\n\n{why}"))
        self.controls = ControlPanel(self)

        # roaming state: one lap = run right along the bottom, climb the rope on the right edge
        # (sometimes slipping), run left along the top, slide down the left edge, jog a bit, nap.
        self.phase = "bottom_r"
        self.fall_v = 0.0
        self.fall_next = "bottom_r"
        self.falls: list[float] = []      # heights where this climb will slip (0, 1 or 2 of them)
        self.phase_until = 0.0
        self.seg_until = 0.0              # descent: end of the current move / freeze segment
        self.desc_moving = False
        self.desc_slip = False
        self.seg_start = 0.0
        self.top_moving = True            # top edge: tiptoe a bit, freeze and look around, repeat
        self.top_checks = 0
        self.laugh_after = False          # knocked off the rope by a click: laugh it off afterwards
        self.held = False                 # being dragged around right now (angry!)
        self.tampo_after = False          # …and sulking once put down
        self.spin = 0.0
        self.napping = False
        self.nap_until = 0.0
        self.nap_x = 0.0
        self.dir = 1                      # 1 = running right, -1 = left
        self.roam_x = 0.0
        self.roam_y: int | None = None
        self.roam_pause_until = 0.0
        self.next_break = time.time() + random.uniform(15, 35)
        self.next_chat = time.time() + random.uniform(90, 180)
        self.flipped: FrameSet = FrameSet([])
        # joining in with what the user is doing: music, a video, reading (see activity.py)
        self.activity = activity.Activity()
        self.act_seen = 0.0               # last time an activity was detected (short gaps don't end it)
        self.act_drop = False             # hopping down from the rope to join in: no dizzy stars
        # the adventure of the day (see themes.py): outfit, rope, what the lap looks like
        self.theme: str | None = None
        self.count_i = 0                  # rocket countdown: which line is next
        self.launch_v = 0.0               # rocket speed, building up

        # wellbeing: breathing exercise, break reminders, focus sessions (see wellbeing.py)
        wellbeing.quiet_recover()
        self.idle = wellbeing.IdleWatch()
        now = time.time()
        self.work_since = now             # start of this stretch at the keyboard
        self.away_since = 0.0             # 0 = at the keyboard
        self.next_stretch = 0.0           # when to suggest the next break (0 = work it out from work_since)
        self.break_asked = 0.0            # when he last suggested a break
        self.stretch_until = 0.0          # showing the stretch pose
        self.breathe_start = self.breathe_end = 0.0
        self.focus_start = self.focus_end = 0.0
        self.focus_minutes = 0
        self.focus_task: str | None = None        # task id
        self.focus_title = ""
        self.focus_held = 0               # notifications kept quiet during the session
        self.focus_quiet = False          # we silenced other apps' pop-ups (and must give them back)
        self.rest_end = 0.0               # the break after a focus session
        self.done_offer: str | None = None        # finished session: click him to tick this task

        self.tray = QSystemTrayIcon()
        self.tray.activated.connect(self._tray_activated)
        self.tray.messageClicked.connect(self.panel.show_notifications)
        self.menu = self._build_menu()
        self.tray.setContextMenu(self.menu)

        self.bridge = WebhookBridge()
        self.bridge.received.connect(lambda t, b, s: self.notify(t, b, s))
        self.webhook = WebhookServer(self.bridge)

        # timers
        self.anim = QTimer(singleShot=True, timeout=self._next_frame)
        self.stats_timer = QTimer(interval=1500, timeout=self.update_stats)
        self.remind_timer = QTimer(interval=15_000, timeout=self.check_reminders)
        self.roam_timer = QTimer(interval=33, timeout=self._roam)
        self.roam_timer.setTimerType(Qt.PreciseTimer)     # Windows rounds normal timers to 16 ms steps: jerky
        self.activity_timer = QTimer(interval=3000, timeout=self._poll_activity)
        self.well_timer = QTimer(interval=1000, timeout=self._tick_wellbeing)

        psutil.cpu_percent(None)  # prime
        self.apply_settings(first=True)
        self.update_stats()
        self.check_reminders()
        self.stats_timer.start()
        self.remind_timer.start()
        self.roam_timer.start()
        self.activity_timer.start()
        self.well_timer.start()
        self.anim.start(100)
        if store.settings.get("greetings", True):
            QTimer.singleShot(1200, lambda: self.chat(hello=True))

    # ================================================================== #
    # menu
    # ================================================================== #
    def _build_menu(self) -> QMenu:
        m = QMenu()
        self.act_controls = m.addAction("Primo controls…", lambda: self.show_controls())
        m.addAction("Open tasks && notes", self.panel.show_and_raise)
        m.addAction("Quick add task…", self.quick_add)
        self.act_notifs = m.addAction("Notifications", self.panel.show_notifications)
        m.addSeparator()
        self.act_breathe = m.addAction("🌿  Breathe with Primo (start / stop)", self.toggle_breathe)
        m.addAction("🎯  Focus session (start / stop)", self.toggle_focus)
        m.addAction("🕺  Dance showdown with Jeo (start / stop)", lambda: self.toggle_dance())
        m.addAction("💞  Touch by Touch: Jeo's solo, then the duet", lambda: self.toggle_dance("touch"))
        m.addAction("☕  Coffee break", self.coffee_break)
        m.addAction("🎭  Choose avatars (me and my dance friend)…", self.choose_avatars)
        rm = m.addMenu("🐉  Go for a ride")
        rm.addAction("🎲  Surprise me", lambda: self.start_ride())
        rm.addSeparator()
        for key, (label, _, _) in rides.RIDES.items():
            rm.addAction(label, lambda k=key: self.start_ride(k))
        m.addSeparator()

        sp = m.addMenu("Speed follows")
        self.speed_group = QActionGroup(sp)
        for label, k in [("Tasks + notifications + CPU", "mix"), ("Tasks + notifications", "tasks"), ("CPU only", "cpu")]:
            a = QAction(label, sp, checkable=True)
            a.setData(k)
            self.speed_group.addAction(a)
            sp.addAction(a)
        self.speed_group.triggered.connect(lambda a: self._set("speed_source", a.data()))

        ch = m.addMenu("Character")
        self.char_group = QActionGroup(ch)
        for k, label in BUILTIN.items():
            a = QAction(label, ch, checkable=True)
            a.setData(k)
            self.char_group.addAction(a)
            ch.addAction(a)
        a = QAction("Custom…", ch, checkable=True)
        a.setData("custom")
        self.char_group.addAction(a)
        ch.addAction(a)
        self.char_group.triggered.connect(self._char_chosen)

        ad = m.addMenu("Today's adventure")
        self.adv_group = QActionGroup(ad)
        for k, label in [("auto", "Follow the weekday (auto)")] + [
                (k, f"{themes.THEMES[k]['icon']}  {themes.THEMES[k]['label']}") for k in themes.ORDER]:
            a = QAction(label, ad, checkable=True)
            a.setData(k)
            self.adv_group.addAction(a)
            ad.addAction(a)
        self.adv_group.triggered.connect(lambda a: self._set("day_theme", a.data()))

        sm = self.act_seat_menu = m.addMenu("Where Primo sits (calls, work, music…)")
        self.seat_group = QActionGroup(sm)
        for k, label in SEAT_SIDES:
            a = QAction(label, sm, checkable=True)
            a.setData(k)
            self.seat_group.addAction(a)
            sm.addAction(a)
        self.seat_group.triggered.connect(lambda a: self._set("seat_side", a.data()))
        sm.addSeparator()
        self.act_seat_main = QAction("Always on the main screen", sm, checkable=True)
        self.act_seat_main.toggled.connect(lambda on: self._set("seat_screen", "main" if on else "same"))
        sm.addAction(self.act_seat_main)

        tm = m.addMenu("App theme")
        self.ui_group = QActionGroup(tm)
        for k in uitheme.ORDER:
            a = QAction(uitheme.THEMES[k]["label"], tm, checkable=True)
            a.setData(k)
            self.ui_group.addAction(a)
            tm.addAction(a)
        self.ui_group.triggered.connect(lambda a: self._set("ui_theme", a.data()))

        self.act_work = QAction("💻  Work modes (Storyline and my apps)", m, checkable=True)
        self.act_work.toggled.connect(lambda on: (self._set("work_on", on), self._poll_work()))
        m.addAction(self.act_work)

        self.act_pet = QAction("Show floating pet", m, checkable=True)
        self.act_pet.toggled.connect(lambda on: self._set("show_pet", on))
        m.addAction(self.act_pet)
        self.act_pass = QAction("Ghost mode (pet can't be touched)", m, checkable=True)
        self.act_pass.toggled.connect(lambda on: self._set("pet_ghost", on))
        m.aboutToHide.connect(lambda: QTimer.singleShot(150, self._hypr_give_back))
        m.addAction(self.act_pass)
        self.act_roam = QAction("Run around the screen", m, checkable=True)
        self.act_roam.toggled.connect(lambda on: self._set("pet_roam", on))
        m.addAction(self.act_roam)
        jm = m.addMenu("When something is playing, Primo…")
        self.join_group = QActionGroup(jm)
        for key, label in (("auto", "Decides by himself (auto)"), ("listen", "🎧 Listens with headphones"),
                           ("watch", "📱 Watches cosy, on his phone"), ("movie", "🍿 Watches with popcorn"),
                           ("study", "📝 Takes notes (tutorial / podcast)"), ("read", "📖 Reads a book")):
            a = QAction(label, jm, checkable=True)
            a.setData(key)
            self.join_group.addAction(a)
            jm.addAction(a)
        self.join_group.triggered.connect(lambda a: (self._set("activity_mode", a.data()), self._poll_activity()))

        mm = m.addMenu("Media && volume")
        mm.addAction("⏯  Play / pause", lambda: self._media("play-pause"))
        mm.addAction("⏭  Next", lambda: self._media("next"))
        mm.addAction("⏮  Previous", lambda: self._media("previous"))
        mm.addSeparator()
        mm.addAction("🔊  Volume up", lambda: self._volume(+10))
        mm.addAction("🔉  Volume down", lambda: self._volume(-10))
        mm.addAction("🔇  Mute / unmute", lambda: self._volume(mute=True))

        self.act_dnd = QAction("Do not disturb", m, checkable=True)
        self.act_dnd.toggled.connect(lambda on: self._set("dnd", on))
        m.addAction(self.act_dnd)
        m.addAction("Settings…", self.open_settings)
        m.addSeparator()
        m.addAction("Send test notification", lambda: self.notify("Hello from CapyRunner 👋", "Notifications are working.", "test"))
        self.act_update = m.addAction("⬆  Check for updates…", lambda: self.check_updates(manual=True))
        m.addAction("About CapyRunner (by Devjr)", self._about)
        m.addAction("Quit", self.quit)
        return m

    def _sync_menu(self):
        s = self.store.settings
        name = str(s.get("pet_name") or "Primo")
        self.act_controls.setText(f"{name} controls…")
        self.act_breathe.setText(f"🌿  Breathe with {name} (start / stop)")
        self.act_seat_menu.setTitle(f"Where {name} sits (calls, work, music…)")
        for a in self.speed_group.actions():
            a.setChecked(a.data() == s["speed_source"])
        for a in self.char_group.actions():
            a.setChecked(a.data() == s["character"])
        for a in self.join_group.actions():
            a.setChecked(a.data() == s.get("activity_mode", "auto"))
        for a in self.adv_group.actions():
            a.setChecked(a.data() == s.get("day_theme", "auto"))
        for a in self.seat_group.actions():
            a.setChecked(a.data() == s.get("seat_side", "right"))
        for a in self.ui_group.actions():
            a.setChecked(a.data() == s.get("ui_theme", "system"))
        for act, on in ((self.act_seat_main, s.get("seat_screen") == "main"), (self.act_work, s.get("work_on", True))):
            act.blockSignals(True)
            act.setChecked(bool(on))
            act.blockSignals(False)
        for act, key in ((self.act_pet, "show_pet"), (self.act_pass, "pet_ghost"),
                         (self.act_roam, "pet_roam"), (self.act_dnd, "dnd")):
            act.blockSignals(True)
            act.setChecked(bool(s.get(key)))
            act.blockSignals(False)

    def _char_chosen(self, a: QAction):
        if a.data() == "custom" and not self.store.settings.get("custom_path"):
            self.open_settings()
        else:
            self._set("character", a.data())

    def _set(self, key, value):
        self.store.settings[key] = value
        self.store.save_settings()
        self.apply_settings()

    # ================================================================== #
    # settings
    # ================================================================== #
    def apply_settings(self, first: bool = False):
        s = self.store.settings
        uitheme.apply(self.app, s.get("ui_theme", "system"))
        if first and s.get("update_check", True):
            QTimer.singleShot(90_000, self.check_updates)         # once a minute or so after starting…
            self._update_timer = QTimer(interval=24 * 3600 * 1000, timeout=lambda: (
                self.store.settings.get("update_check", True) and self.check_updates()))
            self._update_timer.start()                            # …and once a day after that
        bc = uitheme.bubble_colors(s.get("ui_theme", "system"))
        for w in (self.pet, self.friend):
            w.set_bubble_colors(bc["bubble"], bc["bubble_text"], bc["border"])
        self.desk.clear()
        # the friend may have a new look: draw him / her again when next needed
        if not (self.dance or self.trip):
            self.jeo = self.jeo_flip = self.jeo_space = self.jeo_space_flip = None
            self.styles.clear()
        err = self._load_look()
        who = (s.get("avatar"), s.get("pet_name"))
        if not first and who != getattr(self, "_last_avatar", who) and self.pet.isVisible():
            self._poof()
            self.excited_until = time.time() + 1.2
            self._say(f"✨ Hi! I'm {s.get('pet_name') or 'Primo'} now 👋", 3500)
        self._last_avatar = who
        if err and not first:
            QMessageBox.warning(None, "CapyRunner", f"Custom character problem:\n{err}\n\nUsing Primo for now.")

        tray_ok = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray.setVisible(bool(s["show_tray"]) and tray_ok)
        show_pet = bool(s["show_pet"]) or not self.tray.isVisible()   # never be invisible
        self.pet.set_pet_size(int(s["pet_size"]), int(s.get("pet_width", 100)))
        self._size_friend()
        self.pet.set_passthrough(bool(s.get("pet_ghost", False)))
        if show_pet:
            if first and s.get("pet_pos"):
                self.pet.move(*s["pet_pos"])
            elif first:
                g = self.app.primaryScreen().availableGeometry()
                self.pet.move(g.right() - self.pet.width() - 24, g.bottom() - self.pet.height() - 24)
            self.pet.show()
            self.rope.show()
            for ms in (400, 1500, 4000):      # the compositor needs a moment to map the windows
                QTimer.singleShot(ms, self._hypr_passthrough)
        else:
            self.pet.hide()
            self.rope.hide()

        if s["webhook_enabled"]:
            if not self.webhook.start(int(s["webhook_port"]), s.get("webhook_token", "")):
                self.notify("Webhook not started", self.webhook.error or "", "app", record=False)
        else:
            self.webhook.stop()

        if first and not s["autostart"] and autostart.is_enabled():
            s["autostart"] = True                 # ticked in the Windows installer: show it ticked in Settings
            self.store.save_settings()
        if not first or s["autostart"]:
            err = autostart.set_enabled(bool(s["autostart"]))
            if err and not first:
                QMessageBox.warning(None, "CapyRunner", err)
        self._sync_menu()
        self._update_caption()
        if self.controls.isVisible():
            self.controls.sync()
        self.panel.refresh_notifs()

    ROPE_COLORS = {"climb": "#2E8BC0", "vine": "#4E9A4A", "bunting": "#9A9A9A"}

    def _theme_now(self) -> str:
        """Only Primo dresses up; the other characters always do the classic lap."""
        s = self.store.settings
        return themes.current(s) if s.get("character", "capy") == "capy" else "classic"

    def _load_look(self) -> str | None:
        """(Re)build the frames for the current character, colour and adventure of the day."""
        s = self.store.settings
        self.frames, err = load_frames(s)
        mirror = QTransform().scale(-1, 1)
        flip = lambda fr: [f.transformed(mirror) for f in fr]  # noqa: E731
        self.flipped = FrameSet(flip(self.frames.run), self.frames.sleep, flip(self.frames.jump),
                                {k: flip(v) for k, v in self.frames.extra.items()})
        self.roam_y = None
        old, self.theme = self.theme, self._theme_now()
        th = themes.get(self.theme)
        self.rope.set_style("rope" if th["rope"] == "climb" else th["rope"])
        self.rope.set_color(self.ROPE_COLORS.get(th["rope"]) or s.get("rope_color", "#C79A5B"))
        self._badge_cache.clear()
        self.frame_i = 0
        if self.theme != old:             # a new day, a new chapter of the story
            QTimer.singleShot(7000 if (old is None and s.get("greetings", True)) else 2500,
                              lambda: self._tsay("story", 9000))
        return err

    def _tsay(self, key: str, ms: int = 3800):
        """Say a line from the adventure of the day (if it has one, and he is allowed to tell the story)."""
        line = themes.get(self.theme).get(key) if self.store.settings.get("adventure_talk", True) else None
        if line:
            self._say(line, ms)

    def _cheer(self) -> str:
        extra = themes.get(self.theme).get("cheers") if self.store.settings.get("adventure_talk", True) else None
        if extra and random.random() < 0.4:
            return random.choice(extra)
        return self._words("say_cheers")

    def open_settings(self):
        if getattr(self, "_settings_dlg", None) is not None:      # already open: just bring it forward
            self._settings_dlg.raise_()
            self._settings_dlg.activateWindow()
            return
        dlg = self._settings_dlg = SettingsDialog(self.store.settings, app=self)
        try:
            accepted = dlg.exec()
        finally:
            self._settings_dlg = None
        if accepted:
            self.store.settings.update(dlg.result_settings())
            self.store.save_settings()
            self.apply_settings()
        else:
            self._sync_menu()

    def _pet_moved(self, x, y):
        self._clip_bubble()
        self.store.settings["pet_pos"] = [x, y]
        self.store.save_settings()

    # ================================================================== #
    # state -> speed
    # ================================================================== #
    def update_stats(self):
        s = self.store.settings
        self.cpu = psutil.cpu_percent(None) / 100.0
        overdue, today, open_ = self.store.task_counts()
        unread = self.store.unread()
        task_level = min(1.0, overdue * 0.3 + today * 0.12 + unread * 0.15 + (0.05 if open_ else 0))
        task_idle = open_ == 0 and unread == 0

        src = s["speed_source"]
        if src == "cpu":
            level, sleeping = self.cpu, self.cpu < 0.05
        elif src == "tasks":
            level, sleeping = task_level, task_idle
        else:
            level, sleeping = max(task_level, self.cpu * 0.7), task_idle and self.cpu < 0.08
        if time.time() < self.excited_until:
            level, sleeping = 1.0, False
        self.level, self.sleeping = level, sleeping

        badge = unread + overdue
        self._badge = badge
        parts = []
        if overdue:
            parts.append(f"{overdue} overdue")
        if today:
            parts.append(f"{today} due today")
        if unread:
            parts.append(f"{unread} unread")
        parts.append(f"CPU {self.cpu * 100:.0f}%")
        self.tray.setToolTip("CapyRunner — " + " · ".join(parts))
        self.act_notifs.setText(f"Notifications ({unread})" if unread else "Notifications")

    def _next_frame(self):
        s = self.store.settings
        excited = time.time() < self.excited_until
        fs = self.flipped if (self.dir < 0 and self.flipped.run) else self.frames
        roaming = bool(s.get("pet_roam")) and self.pet.isVisible()
        asleep = self.napping if roaming else self.sleeping   # while roaming, naps are part of the lap
        level = max(self.level, 0.35) if roaming else self.level
        if excited and fs.jump:
            frames = fs.jump
        elif asleep and fs.sleep:
            frames = fs.sleep
        else:
            frames = fs.run
        if not frames:
            self.anim.start(500)
            return
        if frames is not getattr(self, "_cur_frames", None):
            self._cur_frames, self.frame_i = frames, -1
        self.frame_i = (self.frame_i + 1) % len(frames)
        pm = frames[self.frame_i]
        badge = getattr(self, "_badge", 0)
        tray_pm = self.frames.run[self.frame_i % len(self.frames.run)] if frames is self.flipped.run else pm
        if self._on_break() and not excited and not asleep:
            pm = frames[0]                                   # standing still while chatting
        special = self._special_frame(fs) if (roaming and not excited and not asleep) else None
        if not roaming and not excited and self._seated():         # staying put: join in right there
            pose = self._activity_frame(fs)
            if pose is not None:
                special, asleep = pose, False
        if roaming and self.coffee and self.phase == "nap" and not excited and fs.extra.get("sip"):
            sip = fs.extra["sip"]
            special, asleep = sip[int(time.time() * 2.2) % len(sip)], False
        if self.held and self.pet._press is not None and fs.extra.get("angry"):
            ang = fs.extra["angry"]
            special = ang[int(time.time() * 12) % len(ang)]
        if special is not None:
            pm = special

        if self.tray.isVisible():
            key = (id(tray_pm), badge)
            icon = self._badge_cache.get(key)
            if icon is None:
                icon = QIcon(with_badge(tray_pm, badge))
                if len(self._badge_cache) > 64:
                    self._badge_cache.clear()
                self._badge_cache[key] = icon
            self.tray.setIcon(icon)
        if self.pet.isVisible():
            hop = 0
            if excited and self.frames.jump:
                k = self.frame_i / max(1, len(frames) - 1)
                hop = int(max(0.0, math.sin((k - 0.18) / 0.82 * math.pi)) * self.pet.pet_size * 0.3) if k > 0.18 else 0
            elif excited:
                hop = int(abs(math.sin(time.time() * 9)) * self.pet.pet_size * 0.22)
            self.pet.set_frame(with_badge(self._poofed(pm, self.poof_until), badge,
                                          right=fs is self.flipped and not asleep), hop,
                               self.spin if roaming else 0.0)

        if excited and self.frames.jump:
            interval = 55
        elif asleep:
            interval = 900
        elif time.time() < self.poof_until or (roaming and self.phase in ("fall", "climb", "slip", "descend", "seat_go")):
            interval = 45
        elif special is not None:
            # sitting still (a call, work, music, coffee…): the poses change a few times a second at most,
            # so there is no need to redraw 20 times a second for hours: easy on the CPU and the battery
            interval = 45 if (self.dance or self.phase not in ("seat", "nap")) else 90
        else:
            max_fps = int(s["max_fps"])
            if IS_LINUX and self.tray.isVisible() and not self.pet.isVisible():
                max_fps = min(max_fps, 10)   # each tray frame is sent over D-Bus on Linux
            fps = 2.5 + level * (max_fps - 2.5)
            interval = int(1000 / max(1.0, fps))
        self.anim.start(interval)

    # ================================================================== #
    # roaming: run back and forth along the bottom of the screen
    # ================================================================== #
    def _on_break(self) -> bool:
        return time.time() < self.roam_pause_until

    def _pet_grabbed(self):
        self.roam_pause_until = time.time() + 1.5
        self.roam_y = None               # after a drag, drop to the floor and start a new lap
        self.napping = False
        self.rope.set_active(False)
        if self.store.settings.get("grab_tampo", True) and self.frames.extra.get("angry"):
            self.held = True
            self.spin = 0.0
            msg = self._words("say_grab")
            if msg:
                self.pet.say(msg, 2500)

    def _after_fall(self, now: float):
        """What happens once the stars stop spinning."""
        if self.laugh_after:                          # knocked off by a click: laugh it off
            self.laugh_after = False
            self.phase, self.phase_until = "laugh", now + 2.8
            msg = self._words("say_laugh")
            if msg:
                self.pet.say(msg, 2600)
        elif self.tampo_after:                        # was grabbed: sulk
            self._start_tampo(now)
        else:
            self.phase = self.fall_next

    def _start_tampo(self, now: float):
        self.tampo_after = False
        self.phase, self.phase_until = "tampo", now + random.uniform(7, 10)
        msg = self._words("say_tampo")
        if msg:
            self.pet.say(msg, 3000)

    # ---- Hyprland: the pet must never take typing or scrolling away -------------------------- #
    # Hyprland focuses whatever is under the mouse, so a pet running under the cursor would swallow
    # the keyboard. no_follow_mouse stops that while keeping the pet clickable; no_focus (ghost mode,
    # and the rope) makes Hyprland skip the window for keyboard and mouse altogether.
    @staticmethod
    def _on_hyprland() -> bool:
        return IS_LINUX and bool(os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"))

    @staticmethod
    def _hyprctl(*args: str) -> str:
        return subprocess.run(["hyprctl", *args], capture_output=True, text=True, timeout=1).stdout

    def _hypr_windows(self):
        """(clients, pet addresses, rope addresses) as Hyprland sees them."""
        clients = json.loads(self._hyprctl("clients", "-j"))
        pet_size = [self.pet.width(), self.pet.height()]
        pets, ropes = [], []
        for c in clients:
            if c.get("pid") != os.getpid() or c.get("title") != "CapyRunner":
                continue
            size = c.get("size") or [0, 0]
            if size[0] <= 2 * RopeWindow.WIDTH or size == [self.friend.width(), self.friend.height()]:
                # the rope and Jeo are decoration only: never focused
                ropes.append(c["address"])
            elif size == pet_size:
                pets.append(c["address"])       # anything else is the tasks panel: leave it alone
        return clients, pets, ropes

    def _hypr_passthrough(self, step_aside: bool = False):
        if not self._on_hyprland():
            return
        if not step_aside and time.time() < getattr(self, "_aside_until", 0.0):
            return
        ghost = bool(self.store.settings.get("pet_ghost", False)) or step_aside
        try:
            _, pets, ropes = self._hypr_windows()
            cmds = [f"dispatch setprop address:{a} no_focus 1" for a in ropes]      # decoration only
            for a in pets:
                cmds.append(f"dispatch setprop address:{a} no_follow_mouse 1")
                cmds.append(f"dispatch setprop address:{a} no_focus {int(ghost)}")
            if cmds:
                self._hyprctl("--batch", " ; ".join(cmds))
        except Exception:
            pass

    def _hypr_give_back(self):
        """After a click or drag, hand the keyboard back to the window that had it."""
        if not self._on_hyprland():
            return
        try:
            clients, pets, _ = self._hypr_windows()
            active = json.loads(self._hyprctl("activewindow", "-j") or "{}")
            if active.get("address") not in pets:
                return
            others = [c for c in clients if c.get("pid") != os.getpid() and c.get("mapped") and not c.get("hidden")
                      and c.get("focusHistoryID", -1) >= 0]
            if not others:
                return
            prev = min(others, key=lambda c: c["focusHistoryID"])
            warps = json.loads(self._hyprctl("getoption", "cursor:no_warps", "-j") or "{}").get("int", 0)
            self._hyprctl("--batch", f"keyword cursor:no_warps 1 ; dispatch focuswindow address:{prev['address']} ; "
                                     f"keyword cursor:no_warps {int(warps)}")       # keep the mouse where it is
        except Exception:
            pass

    def _pet_step_aside(self):
        """Scrolled over the pet, or clicked the empty space around it: let the mouse through for a moment."""
        if not self._on_hyprland():
            return
        self._aside_until = time.time() + 1.4
        self._hypr_passthrough(step_aside=True)
        self._hypr_give_back()
        QTimer.singleShot(1500, self._hypr_passthrough)

    def _work_area(self, screen):
        """Screen area without panels. Under XWayland on Hyprland Qt does not see the bar, so ask Hyprland."""
        g = screen.availableGeometry()
        if not (IS_LINUX and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")):
            return g
        now = time.time()
        cache = getattr(self, "_hypr_cache", None)
        if cache is None or now - cache[0] > 20:
            mons = []
            try:
                out = subprocess.run(["hyprctl", "monitors", "-j"], capture_output=True, text=True, timeout=1).stdout
                mons = json.loads(out)
            except Exception:
                pass
            cache = self._hypr_cache = (now, mons)
        full = screen.geometry()
        for m in cache[1]:
            if (m.get("x"), m.get("y")) == (full.x(), full.y()):
                l, t, r, b = (list(m.get("reserved") or []) + [0, 0, 0, 0])[:4]
                return full.adjusted(int(l), int(t), -int(r), -int(b))
        return g

    def _place(self, top_layout: bool = False):
        """roam_y is the window y in the normal layout (sprite top = roam_y + BUBBLE_H)."""
        self.pet.set_top_layout(top_layout)
        y = self.roam_y + (self.pet.BUBBLE_H if top_layout else 0)
        self.pet.move(int(self.roam_x), int(y))
        self._clip_bubble()

    def _clip_bubble(self):
        """Tell the pet how much of its window hangs off the screen, so the bubble stays readable."""
        pet = self.pet
        screen = self.app.screenAt(pet.frameGeometry().center()) or pet.screen() or self.app.primaryScreen()
        g = screen.geometry()
        pet.set_clip(g.left() - pet.x(), pet.x() + pet.width() - (g.right() + 1))

    CLIMB_RATE = 4.5      # rad/s; one full hand-over-hand cycle = 2*pi / CLIMB_RATE seconds

    # ---- joining in: headphones for music, popcorn for a video, a book when reading ---------- #
    ACT_FPS = {"happy": 9, "hype": 16, "chill": 5, "sad": 4, "love": 7}

    def _poll_meeting(self):
        s = self.store.settings
        call = ""
        if s.get("meeting_look", True) and self.pet.isVisible() and self.frames.extra.get("d_bob"):
            try:
                call = meeting.detect()
            except Exception:
                call = ""
        if call:
            self.meeting_gone = 0
        elif self.meeting:
            self.meeting_gone += 1
            if self.meeting_gone < 2:
                return
        if call == self.meeting:
            return
        was, self.meeting = self.meeting, call
        if call and not was:                          # the call starts: sit down, dress up, listen in
            if self.dance:
                self._end_dance()
            if s.get("meeting_mic", True):
                self.mic.start()
            self._sit_now()
        elif not call:                                # the call is over: back into the day's clothes
            self.mic.stop()
            if self.office_on:
                self.office_on = False
                self._poof()
        self._update_caption()

    def _work_mode(self) -> dict:
        ms = workmode.modes(self.store.settings)
        return ms[self.work.index] if 0 <= self.work.index < len(ms) else dict(workmode.DEFAULT_MODE)

    def _desk_frames(self, flipped: bool):
        """The office chair and laptop frames for the work mode on now, drawn once and kept."""
        m, s = self._work_mode(), self.store.settings
        look = m.get("look", "hoodie")
        outfit = themes.get(self.theme).get("outfit", "") if look == "adventure" else ""
        key = (look, outfit, m.get("chair"), bool(m.get("glasses", True)), s.get("color"))
        if key not in self.desk:
            fr = desk_frames(s.get("color", "#1F2A5A"), look, outfit, m.get("chair") or "#3B4A63",
                             bool(m.get("glasses", True)))
            mirror = QTransform().scale(-1, 1)
            if len(self.desk) > 8:
                self.desk.clear()
            self.desk[key] = (fr, [f.transformed(mirror) for f in fr])
        return self.desk[key][1 if flipped else 0]

    def _poll_work(self):
        s = self.store.settings
        if not (self.pet.isVisible() and self.frames.extra.get("watch")):
            new = workmode.Work()
        else:
            try:
                new = self.workwatch.poll(s)
            except Exception:
                new = workmode.Work()
        if (new.index, new.name) == (self.work.index, self.work.name):
            if new.app != self.work.app:
                self.work = new
                self._update_caption()
            return
        was, self.work = self.work, new
        if new:
            if self.dance:
                self._end_dance()
            self._sit_now()
            line = str(self._work_mode().get("say") or "")
            if line and not self.meeting:
                self._say(line.replace("{mode}", new.name).replace("{app}", new.app)
                          .replace("{name}", str(s.get("pet_name") or "Primo")), 4500)
        elif was and not self.meeting:
            self._say("💾 Saved? Nice work! 🐾", 3000)
        self._update_caption()

    def _poll_activity(self):
        s = self.store.settings
        self._poll_meeting()
        self._poll_work()
        if not s.get("activity_react", True) or not self.pet.isVisible():
            self.activity = activity.Activity()
            return
        try:
            new = activity.detect(s.get("study_words") or ())
        except Exception:
            new = activity.Activity()
        forced = s.get("activity_mode", "auto")
        if new and forced in activity.KINDS and forced != new.kind:      # you chose how he joins in
            new = activity.Activity(forced, new.title, new.artist, new.mood, new.music or new.kind == "listen")
        now = time.time()
        if new:
            self.act_seen = now
        elif self.activity and now - self.act_seen < 8:      # gap between songs, quick alt-tab…
            return
        old, self.activity = self.activity, new
        self._update_caption()
        if new.label != self.danced_label:
            self.danced_label = ""
            if s.get("dance_songs", True) and not self.dance and self._dance_song_on() and self.start_dance(song=True):
                self.danced_label = new.label         # a dance song came on: Jeo turns up for a showdown
                return
        if not new or not self.frames.extra.get("watch") or self._pose():
            return
        if new.kind != old.kind:
            self.pet.say({"listen": "Ooh, music! 🎧", "watch": "Comfy… let's watch! 📱",
                          "movie": "Movie time! 🍿", "study": "Notes ready! 📝",
                          "read": "Reading time… 📖"}[new.kind], 3500)
        elif new.kind == "listen" and new.label and new.label != old.label:
            face = {"hype": "🔥", "chill": "😌", "sad": "🥺", "love": "💕"}.get(new.mood, "🎵")
            self.pet.say(f"{face} New song!", 2500)

    ACT_ICON = {"listen": "🎧", "watch": "📱", "movie": "🍿", "study": "📝", "read": "📖"}

    def _short(self, text: str, n: int = 44) -> str:
        text = " ".join(text.split())
        return text if len(text) <= n else text[: n - 1].rstrip() + "…"

    def _update_caption(self):
        """The small standing line above the pet: mode icon + what is playing."""
        act, s = self.activity, self.store.settings
        self.pet.set_font_px(int(s.get("bubble_font", 13)))
        now = time.time()
        if now < self.breathe_end:
            text = wellbeing.breath(now - self.breathe_start)[2]
            self.pet.set_caption(f"🌿 {text}  {wellbeing.fmt_clock(self.breathe_end - now)}")
            return
        if self.focus_end:
            left = wellbeing.fmt_clock(self.focus_end - now)
            self.pet.set_caption(f"🎯 {left}" + (f" · {self._short(self.focus_title, 26)}" if self.focus_title else ""))
            return
        if self.rest_end:
            self.pet.set_caption(f"☕ Break {wellbeing.fmt_clock(self.rest_end - now)}")
            return
        if self.meeting:
            self.pet.set_caption(f"🎧 In a call · {self._short(self.meeting, 22)}")
            return
        if self.work and self._pose() == "work":
            m = self._work_mode()
            if s.get("activity_caption", True):
                self.pet.set_caption(f"{m.get('icon') or '💻'} {self._short(self.work.name, 24)} · {self._short(self.work.app, 18)}")
            else:
                self.pet.set_caption("")
            return
        if not act or not s.get("activity_caption", True) or not self.frames.extra.get("watch"):
            self.pet.set_caption("")
            return
        icon = self.ACT_ICON.get(act.kind, "")
        if act.kind == "read":
            text = f"{icon} Reading" + (f" · 🎧 {self._short(act.title, 26)}" if act.music and act.title else "")
        else:
            text = f"{icon} {self._short(act.title, 34)}" if act.title else icon
        self.pet.set_caption(text)

    # ---- media keys and volume ------------------------------------------------------------- #
    def _media(self, cmd: str):
        activity.media(cmd)
        QTimer.singleShot(500, self._poll_activity)

    def _volume(self, delta: int = 0, mute: bool = False):
        if mute:
            activity.toggle_mute()
        else:
            cur = activity.get_volume()
            if cur is None:
                return
            activity.set_volume(cur[0] + delta)
        cur = activity.get_volume()
        if cur and self.pet.isVisible():
            self.pet.say("🔇 Muted" if cur[1] else f"🔊 {cur[0]}%", 1500)
        self._sync_volume()

    def _sync_volume(self):
        if self.controls.isVisible():
            self.controls.sync_volume()

    def show_controls(self, pos=None):
        """The control panel: a normal window with a Close button (pop-up menus can get stuck on Wayland)."""
        if pos is None:
            pos = self.pet.frameGeometry().center() if self.pet.isVisible() else self.app.primaryScreen().geometry().center()
        self.controls.open_near(pos)

    def _pose(self) -> str:
        """The wellbeing pose that is on right now ('' = none); it wins over music / video poses."""
        now = time.time()
        if now < self.breathe_end:
            return "breathe"
        if now < self.stretch_until:
            return "stretch"
        if self.meeting:
            return "meet"
        if self.focus_end:
            return "focus"
        if self.work and self.frames.extra.get("watch"):
            return "work"
        return ""

    def _seated(self) -> bool:
        """Should he stop running around and sit (or stand) doing something with you?"""
        ex = self.frames.extra
        return bool(self.dance or (self._pose() and ex.get("breathe_in")) or (self.activity and ex.get("watch")))

    def _activity_frame(self, fs: FrameSet):
        act, ex, now = self.activity, fs.extra, time.time()
        if not ex:
            return None
        if self.dance:
            return self._dance_frame(fs)
        pose = self._pose()
        if pose == "meet":
            if self.office is None:
                self.office = office_frames()
                mirror = QTransform().scale(-1, 1)
                self.office_flip = {k: [f.transformed(mirror) for f in v] for k, v in self.office.items()}
            if not self.office_on:                    # sat down: poof, into the office clothes
                self.office_on = True
                self._poof()
            talk = self.mic.speaking
            fr = (self.office_flip if fs is self.flipped else self.office)["meet_talk" if talk else "meet_listen"]
            return fr[int(now * (9 if talk else 3)) % len(fr)]
        if pose == "work":
            fr = self._desk_frames(fs is self.flipped)
            if fr:
                step = int(now * 4)                   # typing, with a short pause for an idea now and then
                return fr[step % len(fr)]
        if pose == "breathe" and ex.get("breathe_in"):
            level, out, _ = wellbeing.breath(now - self.breathe_start)
            fr = ex["breathe_out" if out else "breathe_in"]
            return fr[min(len(fr) - 1, int(level * (len(fr) - 1) + 0.5))]
        if pose == "stretch" and ex.get("stretch"):
            return ex["stretch"][int(now * 5) % len(ex["stretch"])]
        if pose == "focus" and ex.get("study"):
            return ex["study"][int(now * 2.5) % len(ex["study"])]
        if not act:
            return None
        if act.kind == "listen":
            name, fps = f"listen_{act.mood}", self.ACT_FPS.get(act.mood, 9)
        elif act.kind == "watch":
            name, fps = "bed", 3
        elif act.kind == "movie":
            name, fps = "watch", 3
        elif act.kind == "study":
            name, fps = "study", 2.5
        else:
            name, fps = ("read_hp" if act.music else "read"), 4
        fr = ex.get(name)
        return fr[int(now * fps) % len(fr)] if fr else None

    def _special_frame(self, fs: FrameSet):
        """Rope poses (only characters that have them, i.e. Primo)."""
        ex, ph, now = fs.extra, self.phase, time.time()
        if not ex:
            return None
        if ph == "seat":
            return self._activity_frame(fs)

        def pick(name: str, fps: float):
            fr = ex.get(name)
            return fr[int(now * fps) % len(fr)] if fr else None

        th = themes.get(self.theme)
        both = bool(self.trip and self.trip["stage"] == "inside" and ex.get("rocket2"))     # Jeo is on board
        if ph == "prelaunch":
            return pick("pad2" if both else "pad", 6)
        if ph == "climb" and th["climb"] == "rocket" and ex.get("rocket"):
            return pick("rocket2" if both else "rocket", 14)
        if ph == "top" and th["top"] == "float":
            return pick("float", 8)
        if ph == "top" and th["top"] == "walk":
            return None                               # plain walking frames, in the outfit of the day
        if ph == "think" and th["top"] == "float":
            return pick("think", 8)
        if ph == "descend" and th["descend"] == "chute" and ex.get("chute"):
            return pick("chute", 7)
        if ph == "climb":
            fr = ex.get("climb")
            if fr:
                return fr[int((now * self.CLIMB_RATE) % (2 * math.pi) / (2 * math.pi) * len(fr)) % len(fr)]
        elif ph == "slip":
            return pick("slip", 12)
        elif ph == "fall":
            return pick("fall", 14)
        elif ph == "dizzy":
            return pick("dizzy", 9)
        elif ph == "think":
            return pick("think", 1.6)
        elif ph == "laugh":
            return pick("laugh", 11)
        elif ph == "tampo":
            return pick("tampo", 1.3)
        elif ph == "top":
            if not self.store.settings.get("lap_sneak", True):
                return None
            if self.top_moving:
                return pick("sneak", 7)
            span = max(0.1, self.seg_until - self.seg_start)
            frac = (now - self.seg_start) / span
            src = self.frames.extra if 0.3 < frac < 0.7 else ex       # glance back over the shoulder
            fr = src.get("peek")
            return fr[int(now * 2.5) % len(fr)] if fr else None
        elif ph == "descend":
            if self.desc_slip:
                return pick("slip", 12)
            return pick("slide", 7) if self.desc_moving else pick("cling", 16)
        return None

    def _pet_clicked(self):
        s = self.store.settings
        if self.dance:
            self._say("🕺 Watch this!", 2000)
            return
        if s.get("pet_roam") and self.phase == "tampo":   # a pat makes it all better
            msg = self._words("say_forgive")
            if msg:
                self.pet.say(msg, 3000)
            self.excited_until = time.time() + 1.3
            self.phase = self.fall_next if self.fall_next != "tampo" else "bottom_r"
            return
        if (s.get("pet_roam") and s.get("lap_click_fall", True) and self.phase == "climb"
                and themes.get(self.theme)["climb"] == "rope"):
            msg = self._words("say_fall")                 # poked while climbing: lose the grip
            if msg:
                self.pet.say(msg, 2200)
            self.laugh_after = True
            self.phase, self.phase_until = "slip", time.time() + 0.5
            return
        now = time.time()
        if now < self.breathe_end:
            self.stop_breathe()
            return
        if self.done_offer:
            self.finish_focus_task()
            return
        if self.focus_end:
            self.pet.say(f"🎯 {wellbeing.fmt_clock(self.focus_end - now)} left. You can do it! 💪", 3000)
            return
        if self._pose() == "work":
            self.pet.say(f"💻 {self.work.name} in {self.work.app}. Keep going! 💪", 3500)
            return
        act = self.activity
        if act and self.frames.extra.get("watch") and not self.store.unread():
            label = self._short(act.label, 60)
            msg = {"listen": f"🎧 {label}" if label else "🎧 Good song!",
                   "watch": f"📱 {label}" if label else "📱 So comfy…",
                   "movie": f"🍿 {label}" if label else "🍿 Shh, it's getting good!",
                   "study": f"📝 {label}" if label else "📝 Taking notes!",
                   "read": "📖 Shh… reading." + (f" (🎧 {label})" if act.music and label else "")}[act.kind]
            self.pet.say(msg, 4500)
            return
        self.chat(clicked=True)

    def _seat_screen(self, screen):
        if self.store.settings.get("seat_screen", "same") == "main":
            return self.app.primaryScreen()
        return screen

    def _seat_spot(self, screen, g, left: float, right: float, here: bool):
        """Where he sits to join in, and which way he faces: (x, dir). x is None when the seat is on another screen."""
        side = self.store.settings.get("seat_side", "right")
        if here:                                       # breathing / stretching: right where he stands
            return min(max(self.roam_x, left), right), self.dir
        if self._seat_screen(screen) is not screen:
            return None, -1 if side != "left" else 1
        S = self.pet.sprite_w
        if side in ("left", "top_left"):
            return left + S * 0.25, 1
        if side == "center":
            return (left + right) / 2, -1
        if side == "stay":
            x = min(max(self.roam_x, left), right)
            return x, (1 if x < (left + right) / 2 else -1)      # facing the middle of the screen
        return right - S * 0.25, -1

    def _start_fall(self, then: str):
        self.phase, self.fall_next, self.fall_v = "fall", then, 0.0

    def _roam(self):
        s = self.store.settings
        pet = self.pet
        self._dance_tick()
        self._trip_tick()
        if not (s.get("pet_roam") and pet.isVisible()):
            self.napping, self.spin = False, 0.0
            self.rope.set_active(False)
            return
        now = time.time()
        if pet._press is not None:
            return

        screen = self.app.screenAt(pet.frameGeometry().center()) or pet.screen() or self.app.primaryScreen()
        g = self._work_area(screen)
        W, H, S, SW = pet.width(), pet.height(), pet.pet_size, pet.sprite_w
        lift = max(0, int(s.get("pet_lift", 0)))
        left = g.left() - (W - SW) / 2                # sprite touching the left edge
        right = g.right() + 1 - W + (W - SW) / 2      # sprite touching the right edge
        bottom = g.bottom() + 1 - H - lift            # sprite standing on the bottom edge (or raised by the user)
        top = g.top() - pet.BUBBLE_H                  # sprite touching the top edge

        if self.roam_y is None:                       # first run / after a drag / settings change
            self.roam_x = min(max(float(pet.x()), left), right)
            self.roam_y = float(pet.y() - (pet.BUBBLE_H if pet.top_layout else 0))
            self.spin, self.napping = 0.0, False
            if self.held:                             # just put down after being carried
                self.held, self.tampo_after = False, True
            self.fall_next = "bottom_r"
            if self.phase == "seat" and self._seated():
                pass                                  # still sitting (maybe up in a top corner): stay put
            elif self.roam_y < bottom - 2:
                self._start_fall("bottom_r")
            elif self.tampo_after:
                self.roam_y = bottom
                self._start_tampo(now)
            else:
                self.roam_y, self.phase = bottom, "bottom_r"
        if self._on_break():
            return

        excited = now < self.excited_until
        speed = (0.8 + max(self.level, 0.35) * 4.2) * (S / 96) * (1.6 if excited else 1)
        ph = self.phase

        # something to join in with: go and sit on the right-hand side, facing the screen
        act = self._seated()
        th = themes.get(self.theme)
        here = self._pose() in ("breathe", "stretch")     # these happen right where he is standing
        if act and ph in ("bottom_r", "bottom_end", "nap", "prelaunch"):
            self.napping, self.phase = False, "seat_go"
            ph = "seat_go"
        elif act and ph in ("climb", "top", "think", "descend") and not self.act_drop:
            self.act_drop = True                      # up on the rope: hop down first
            self._start_fall("bottom_r")
            ph = self.phase
        if ph in ("seat_go", "seat"):
            seat_x, face = self._seat_spot(screen, g, left, right, here)
            # top corners: he sits up on the top edge (bubble below him), lowered by "Raise him by"
            high = not here and str(s.get("seat_side", "right")).startswith("top_")
            if seat_x is None:                        # sits on another screen: hop over there with a puff
                screen2 = self._seat_screen(screen)
                g2 = self._work_area(screen2)
                self.roam_x, _ = self._seat_spot(screen2, g2, g2.left() - (W - SW) / 2,
                                                 g2.right() + 1 - W + (W - SW) / 2, here)
                self.roam_y = (g2.top() - pet.BUBBLE_H + lift) if high else (g2.bottom() + 1 - H - lift)
                self.phase, self.dir = "seat", face
                self._poof()
                self._place(top_layout=high)
                return
            up_y = top + lift
            if not act:
                self.next_break = now + random.uniform(15, 35)
                if self.roam_y < bottom - 2:          # done up in the corner: hop down, land on his feet
                    self.act_drop, self.dir = True, 1
                    self._start_fall("bottom_r")
                    self._place()
                else:
                    self.phase, self.dir, self.roam_y = "bottom_r", 1, bottom
                return
            if ph == "seat_go":
                self.roam_y = bottom
                step = speed * 1.4
                if abs(seat_x - self.roam_x) <= step:
                    self.roam_x, self.phase = seat_x, "seat"
                    if not here:
                        self.dir = face
                    if high:                          # up into the corner with a puff of smoke
                        self.roam_y = up_y
                        self._poof()
                else:
                    self.dir = 1 if seat_x > self.roam_x else -1
                    self.roam_x += step * self.dir
            else:
                self.roam_x = seat_x
                self.roam_y = up_y if high else bottom
                if not here:
                    self.dir = face
            self.rope.set_active(False)
            self._place(top_layout=self.phase == "seat" and high)
            return

        if ph == "nap":
            if now >= self.nap_until or excited:
                self.napping, self.phase, self.dir, self.coffee = False, "bottom_r", 1, False
            return
        if ph in ("bottom_r", "bottom_end") and now >= self.next_break:
            self.next_break = now + random.uniform(20, 45)      # little pause now and then
            self.roam_pause_until = now + random.uniform(1.5, 3)
            if s.get("greetings", True) and now >= self.next_chat:
                self.next_chat = now + random.uniform(150, 300)
                self.chat()
            return

        if ph == "bottom_r":                          # run right along the bottom
            self.dir, self.roam_y = 1, bottom
            self.roam_x += speed
            if self.roam_x >= right:
                self.roam_x, self.phase = right, "climb"
                if th["climb"] == "rocket" and self.frames.extra.get("rocket"):
                    self.phase, self.phase_until, self.count_i, self.launch_v = "prelaunch", now + 0.6, 0, 0.0
                    self._start_trip()                # once a day Jeo is invited along
                else:
                    self._tsay("arrive", 3000)
                n = random.choices([0, 1, 2], [0.2, 0.4, 0.4])[0] if (s.get("lap_falls", True) and th["falls"]) else 0
                self.falls = sorted((top + (bottom - top) * random.uniform(0.15, 0.75) for _ in range(n)),
                                    reverse=True)
        elif ph == "prelaunch":                       # in the rocket on the pad: countdown, then lift-off
            self.dir, self.roam_x, self.roam_y = 1, right, bottom
            if now >= self.phase_until and not (self.trip and self.trip["stage"] == "board"):   # wait for Jeo
                count = th.get("count") or []
                if self.count_i < len(count):
                    if s.get("adventure_talk", True):
                        self._say(count[self.count_i], 1300)
                    self.count_i += 1
                    self.phase_until = now + 1.0
                else:
                    self.phase = "climb"
        elif ph == "climb":                           # hand over hand up the rope on the right edge
            self.dir, self.roam_x = 1, right
            if th["climb"] == "rocket" and self.frames.extra.get("rocket"):
                self.launch_v = min(self.launch_v + 0.22, 13.0)       # slow off the pad, then faster and faster
                self.roam_y -= self.launch_v * (S / 96)
            else:
                pull = math.sin(now * self.CLIMB_RATE) ** 2           # body rises as an arm pulls
                self.roam_y -= speed * 0.75 * (0.2 + 1.6 * pull)
            if self.falls and self.roam_y <= self.falls[0]:
                self.falls.pop(0)                     # oops — lose the grip
                self.phase, self.phase_until = "slip", now + 0.5
            elif self.roam_y <= top:
                self.roam_y, self.phase, self.dir = top, "top", -1
                self.top_moving, self.top_checks, self.seg_until = True, 0, now      # start with a look around
                if th["top"] != "sneak":
                    self._tsay("top_say", 3500)
        elif ph == "slip":
            if now >= self.phase_until:
                self._start_fall("climb")
        elif ph == "fall":
            self.fall_v += 0.9
            self.roam_y += self.fall_v
            self.spin = (self.spin + 13) % 360
            if self.roam_y >= bottom and self.act_drop:       # hopped down on purpose: lands on his feet
                self.act_drop = False
                self.roam_y, self.spin, self.phase = bottom, 0.0, "bottom_r"
                self.excited_until = now + 1.0
            elif self.roam_y >= bottom:               # thud: sit there seeing stars
                self.roam_y, self.spin, self.phase = bottom, 0.0, "dizzy"
                self.phase_until = now + random.uniform(2.4, 3.2)
        elif ph == "dizzy":
            if now >= self.phase_until:
                self._after_fall(now)
        elif ph == "laugh":
            if now >= self.phase_until:
                self._after_fall(now)
        elif ph == "tampo":
            if now >= self.phase_until:
                self.phase = self.fall_next
        elif ph == "top":                             # sneak left along the top: tiptoe, freeze, check, repeat
            self.dir, self.roam_y = -1, top
            has_sneak = (th["top"] == "sneak" and bool(self.frames.extra.get("sneak"))
                         and bool(s.get("lap_sneak", True)))
            if th["top"] == "float":                  # weightless: bobbing gently below the top edge
                self.roam_y = top + S * 0.10 * (1 + math.sin(now * 1.3))
            if has_sneak and now >= self.seg_until:
                self.top_moving = not self.top_moving
                self.seg_start = now
                if self.top_moving:
                    self.seg_until = now + random.uniform(2.5, 4.5)
                else:
                    self.seg_until = now + random.uniform(1.6, 2.6)
                    self.top_checks += 1
                    if self.top_checks % 3 == 1:      # politely excusing himself, Filipino style
                        story = th.get("top_say") if s.get("adventure_talk", True) else None
                        msg = story or self._words("say_top")
                        if msg:
                            self.pet.say(msg, 2800)
            if not has_sneak:
                self.roam_x -= speed * (0.5 if th["top"] in ("walk", "float") else 1)
            elif self.top_moving:
                self.roam_x -= 1.6 * (S / 96) * (1.6 if excited else 1)
            if self.roam_x <= left:
                self.roam_x, self.phase = left, "think"
                self.phase_until = now + random.uniform(3.0, 4.5)
                self._tsay("think", 4200)
        elif ph == "think":                           # look down the rope and think about it first
            self.dir, self.roam_x, self.roam_y = -1, left, top
            if now >= self.phase_until:
                self.phase, self.desc_moving, self.desc_slip, self.seg_until = "descend", False, False, now + 1.0
        elif ph == "descend":                         # nervously down the rope: inch, freeze, inch…
            self.dir, self.roam_x = -1, left
            chute = th["descend"] == "chute" and bool(self.frames.extra.get("chute"))
            if chute:                                 # floating down under the parachute, nice and steady
                self.desc_slip = self.desc_moving = False
                self.roam_y += 1.9 * (S / 96)
            elif now >= self.seg_until:
                if self.desc_slip:                    # just slipped a bit: hang on tight for a while
                    self.desc_slip, self.desc_moving = False, False
                    self.seg_until = now + random.uniform(1.6, 2.6)
                elif self.desc_moving:
                    self.desc_moving = False
                    self.seg_until = now + random.uniform(0.7, 1.8)
                else:
                    self.desc_moving = True
                    self.desc_slip = random.random() < 0.18
                    self.seg_until = now + (0.22 if self.desc_slip else random.uniform(0.9, 1.8))
            if self.desc_slip:
                self.roam_y += 7 * (S / 96)
            elif self.desc_moving:
                self.roam_y += 1.5 * (S / 96)
            if self.roam_y >= bottom:                 # made it! happy hop
                self.desc_slip = self.desc_moving = False
                self.excited_until = now + 1.3
                self.roam_y, self.phase, self.dir = bottom, "bottom_end", 1
                self.nap_x = left + (right - left) * random.uniform(0.25, 0.7)
                self._tsay("land", 4500)
        elif ph == "bottom_end":                      # jog to a nice spot, then sleep
            self.dir, self.roam_y = 1, bottom
            self.roam_x += speed
            if self.roam_x >= self.nap_x:
                self.phase, self.napping = "nap", True
                self.coffee = bool(s.get("coffee_breaks", True) and self.frames.extra.get("sip")
                                   and random.random() < 0.35)
                nap = max(5.0, float(s.get("nap_seconds", 60)))
                self.nap_until = now + nap * (random.uniform(0.75, 1.3) if self.sleeping else random.uniform(0.2, 0.4))

        on_rope = (self.phase in ("climb", "slip", "think", "descend")
                   or (self.phase in ("fall", "dizzy", "laugh") and self.fall_next == "climb"))
        if on_rope:
            off = SW / 2                                  # rope through the middle of the sprite…
            if self.frames.extra:                         # …or in front of it, where the paws grip
                off = SW * (ROPE_X if self.dir > 0 else BASE - ROPE_X) / BASE
            rx = int(self.roam_x + (W - SW) / 2 + off - self.rope.WIDTH / 2)
            if (self.rope.x(), self.rope.y(), self.rope.height()) != (rx, g.top(), g.height()):
                self.rope.setGeometry(rx, g.top(), self.rope.WIDTH, g.height())
        self.rope.set_active(on_rope)
        self._place(top_layout=self.phase in ("top", "think"))

    # ================================================================== #
    # wellbeing: breathe together, break reminders, focus sessions
    # ================================================================== #
    AWAY_AFTER = 180          # this long away from the keyboard counts as a real break
    STRETCH_SECS = 12

    def _say(self, text: str, ms: int = 5000):
        if self.pet.isVisible():
            self.pet.say(text, ms)

    def _sit_now(self):
        """Stop whatever the lap was doing so the new pose shows straight away."""
        self.roam_pause_until = 0.0
        self.excited_until = 0.0
        self.napping = False

    # ---- breathing --------------------------------------------------------------------------- #
    def toggle_breathe(self):
        if time.time() < self.breathe_end:
            self.stop_breathe()
        else:
            self.start_breathe()

    def start_breathe(self, minutes: float | None = None):
        s = self.store.settings
        minutes = float(minutes or s.get("breathe_minutes", 2))
        rounds = max(1, round(minutes * 60 / wellbeing.BREATH_CYCLE))       # always end on a full breath out
        now = time.time()
        self.breathe_start, self.breathe_end = now, now + rounds * wellbeing.BREATH_CYCLE
        self.stretch_until = 0.0
        self._sit_now()
        self._say("🌿 Breathe with me. In through the nose, twice… then slowly out.", 4500)
        self._update_caption()
        self._sync_controls()

    def stop_breathe(self, done: bool = False):
        if not self.breathe_end:
            return
        self.breathe_start = self.breathe_end = 0.0
        self._say("🌿 Nicely done. A little lighter now?" if done else "🌿 Okay, we stop here.", 4000)
        self._update_caption()
        self._sync_controls()

    # ---- focus session ----------------------------------------------------------------------- #
    def toggle_focus(self):
        if self.focus_end:
            self.stop_focus()
        else:
            self.start_focus()

    def start_focus(self, minutes: int | None = None, task_id: str | None = None):
        s = self.store.settings
        minutes = max(1, int(minutes or s.get("focus_minutes", 25)))
        task = self.store.task(task_id) if task_id else None
        now = time.time()
        self.focus_start, self.focus_end, self.focus_minutes = now, now + minutes * 60, minutes
        self.focus_task, self.focus_title = (task["id"], task["title"]) if task else (None, "")
        self.focus_held, self.rest_end, self.done_offer = 0, 0.0, None
        self.stretch_until = 0.0
        if s.get("focus_quiet_system", True):
            self.focus_quiet = wellbeing.quiet_on()
        self._sit_now()
        what = f" on “{self._short(self.focus_title, 30)}”" if self.focus_title else ""
        self._say(f"🎯 {minutes} min{what}. I'm working with you!", 4500)
        self._update_caption()
        self._sync_controls()

    def _focus_cleanup(self):
        self.focus_start = self.focus_end = 0.0
        if self.focus_quiet:
            wellbeing.quiet_off()
            self.focus_quiet = False

    def _held_note(self):
        """Tell about the notifications that waited, once the session is over."""
        n, self.focus_held = self.focus_held, 0
        if n and not self.store.settings["dnd"]:
            self._desktop_notify(f"📬 {n} notification{'s' if n > 1 else ''} waited while you focused",
                                 "Open CapyRunner to read them.")
        return n

    def stop_focus(self):
        if not self.focus_end:
            return
        mins = int((time.time() - self.focus_start) // 60)
        self._focus_cleanup()
        self._held_note()
        self.next_stretch = 0.0
        self._say(f"🎯 Stopped after {mins} min. It still counts! 🧡" if mins else "🎯 Focus stopped.", 4000)
        self._update_caption()
        self._sync_controls()

    def _finish_focus(self):
        now = time.time()
        minutes = self.focus_minutes
        self._focus_cleanup()
        held = self._held_note()
        rest = 5 if minutes <= 30 else 10             # longer work needs a longer break
        self.rest_end = now + rest * 60
        self.stretch_until = now + self.STRETCH_SECS
        self.done_offer = self.focus_task if (self.focus_task and self.store.task(self.focus_task)) else None
        msg = f"🎉 {minutes} min done! {rest} min break: stand up, look far away."
        if self.done_offer:
            msg += " Click me if the task is finished ✓"
        elif held:
            msg += f" ({held} notification{'s' if held > 1 else ''} waited.)"
        self._say(msg, 12000)
        self._update_caption()
        self._sync_controls()

    def finish_focus_task(self):
        """Tick the task the last focus session was about."""
        task = self.store.task(self.done_offer) if self.done_offer else None
        self.done_offer = None
        if task and not task.get("done"):
            task["done"] = True
            self.store.save_data()
            self.panel.refresh_tasks()
            self.update_stats()
            self.excited_until = time.time() + 1.5
            self._say(f"✓ “{self._short(task['title'], 30)}” is done! 🎉", 4000)
        self._sync_controls()

    # ---- the one-second tick: timers, time at the keyboard, break reminders -------------------- #
    def _tick_wellbeing(self):
        s, now = self.store.settings, time.time()
        if self.theme is not None and self._theme_now() != self.theme:       # midnight: tomorrow's adventure
            self._load_look()
        if self.breathe_end and now >= self.breathe_end:
            self.stop_breathe(done=True)
        if self.focus_end and now >= self.focus_end:
            self._finish_focus()
        if self.rest_end and now >= self.rest_end:
            self.rest_end, self.done_offer = 0.0, None
            self.work_since, self.next_stretch, self.break_asked = now, 0.0, 0.0
            self._say("☕ Break's over. Ready for the next one? 💪", 5000)

        # at the keyboard, or away? Watching a video without touching anything is still screen time.
        idle = self.idle.seconds()
        on_screen = self.activity.kind in ("watch", "movie", "study")
        if idle >= wellbeing.IDLE_AFTER and not on_screen:
            if not self.away_since:
                self.away_since = now - idle
        elif self.away_since:
            gone, self.away_since = now - self.away_since, 0.0
            if gone >= self.AWAY_AFTER:               # that was a real break
                if self.break_asked and not self.focus_end:
                    self.excited_until = now + 1.5
                    self._say(f"🎉 Welcome back! {max(1, round(gone / 60))} min away. Good break!", 5000)
                self.work_since, self.next_stretch, self.break_asked = now, 0.0, 0.0

        fun = int(s.get("dance_every", 30))           # every so often Jeo turns up with a challenge
        if fun > 0 and not self.dance and s.get("friend_on", True):
            if not self.next_dance:
                self.next_dance = now + fun * 60 * random.uniform(0.9, 1.1)
            elif now >= self.next_dance:
                wclass, wtitle, fullscreen = activity._active_window()
                busy = (fullscreen or self.meeting or wellbeing.in_meeting(wclass, wtitle) or s["dnd"] or self.rest_end
                        or self.activity.kind in ("watch", "movie", "study", "read"))
                if busy or not self.start_dance():
                    self.next_dance = now + 120       # not a good moment: try again in a bit

        ride_every = int(s.get("ride_every", 40))     # and now and then he rides something across the screen
        if ride_every > 0 and s.get("rides_on", True) and not self.ride_win.running:
            if not self.next_ride:
                self.next_ride = now + ride_every * 60 * random.uniform(0.8, 1.2)
            elif now >= self.next_ride:
                self.next_ride = now + ride_every * 60 * random.uniform(0.8, 1.2)
                if self._ride_busy() or not self.start_ride(auto=True):
                    self.next_ride = now + 180

        every = max(5, int(s.get("break_every", 50))) * 60
        due = self.next_stretch or self.work_since + every
        quiet_now = bool(self.focus_end or self.rest_end or self.away_since or s["dnd"]) or now < self.breathe_end
        if s.get("break_remind", True) and self.pet.isVisible() and not quiet_now and now >= due:
            wclass, wtitle, fullscreen = activity._active_window()
            if not (fullscreen or self.meeting or wellbeing.in_meeting(wclass, wtitle)):   # never during a call or a film
                mins = round((now - self.work_since) / 60)
                self.break_asked, self.next_stretch = now, now + every       # asks once, then leaves you alone
                self.stretch_until = now + self.STRETCH_SECS
                self._sit_now()
                self._say(f"🙆 {mins} min without a break. Stand up and stretch with me?", 9000)

        if self.breathe_end or self.focus_end or self.rest_end:
            self._update_caption()
        elif getattr(self, "_had_session", False):
            self._update_caption()                    # clear the timer line once
        self._had_session = bool(self.breathe_end or self.focus_end or self.rest_end)
        if self.controls.isVisible():
            self.controls.sync_wellbeing()

    def _sync_controls(self):
        if self.controls.isVisible():
            self.controls.sync_wellbeing()

    def wellbeing_status(self) -> str:
        now, s = time.time(), self.store.settings
        if now < self.breathe_end:
            return f"🌿 Breathing… {wellbeing.fmt_clock(self.breathe_end - now)} left"
        if self.focus_end:
            what = f" · {self._short(self.focus_title, 30)}" if self.focus_title else ""
            return f"🎯 Focus: {wellbeing.fmt_clock(self.focus_end - now)} left{what}"
        if self.rest_end:
            return f"☕ Break: {wellbeing.fmt_clock(self.rest_end - now)} left"
        mins = int((now - self.work_since) // 60)
        text = f"🖥 At the screen for {mins} min"
        if s.get("break_remind", True) and not s["dnd"]:
            due = self.next_stretch or self.work_since + max(5, int(s.get("break_every", 50))) * 60
            text += f" · break reminder in {max(0, int((due - now) // 60))} min"
        return text

    # ================================================================== #
    # dance showdowns with Jeo (see dance.py)
    # ================================================================== #
    FRIEND_EXTRA_W = 2
    POOF_SECS = 0.65

    def _poof(self):
        """Magician's puff over Primo: whatever he wears next appears out of the smoke."""
        if not self.poof:
            self.poof = poof_frames()
        self.poof_until = time.time() + self.POOF_SECS

    def _poofed(self, pm, until: float):
        """pm with the puff drawn over it, while the puff lasts."""
        left = until - time.time()
        if left <= 0 or not self.poof:
            return pm
        i = min(len(self.poof) - 1, int((1 - left / self.POOF_SECS) * len(self.poof)))
        out = QPixmap(pm)
        p = QPainter(out)
        p.drawPixmap(0, 0, self.poof[i])
        p.end()
        return out

    def _move_frames(self, who: str, style: str, move: str, flipped: bool) -> list:
        """A dance move in a showdown style's outfit, for 'primo' or 'jeo' (drawn the first time, then kept).
        move '' = grooving on the spot."""
        key = (who, style, move)
        if key not in self.styles:
            st = dance.STYLES[style]
            if who == "jeo":
                fr = move_frames(dance.spec(move), style, st["jeo"], jeo=True, bandana=True)
            else:
                band = {"budots": "#2F6FD0", "touch": "#F2C230"}.get(style, False)
                fr = move_frames(dance.spec(move), style, st["primo"], bandana=band)
            mirror = QTransform().scale(-1, 1)
            if len(self.styles) >= 40:                # keep memory flat over days of running
                for old in list(self.styles)[:10]:
                    del self.styles[old]
            self.styles[key] = (fr, [f.transformed(mirror) for f in fr])
        return self.styles[key][1 if flipped else 0]

    def _new_move(self, d: dict, now: float):
        """The next move of the showdown: one nobody has danced yet, shouted out by whoever dances it."""
        st, duet = d["stage"], bool(dance.STYLES[d["style"]].get("duet"))
        solo = st == "solo"
        mv = dance.style_move(d["style"], d["used"], solo=solo)
        d["used"].append(mv)
        d["move"] = mv
        d["switch"] = now + (dance.SOLO_SECS / 4 if solo else dance.TURN_SECS / 2 if st == "turn" else 3.5)
        for who in ("primo", "jeo"):                  # draw it now, not in the middle of a step
            self._move_frames(who, d["style"], mv, False)
        say = dance.MOVES[mv]["say"]
        if solo or (st == "turn" and d["turn"] == "jeo") or (st == "both" and duet and len(d["used"]) % 2):
            self.friend.say(say, 2000)
        else:
            self._say(say, 2000)

    def _size_friend(self):
        """Jeo's window: the pet's size, a touch wider so it can be told apart from the pet's."""
        fr = self.friend
        fr.set_pet_size(self.pet.pet_size, self.pet.width_pct)
        fr.setFixedSize(fr.width() + self.FRIEND_EXTRA_W, fr.height())
        fr.set_font_px(int(self.store.settings.get("bubble_font", 13)))

    @staticmethod
    def _flip_set(fs: FrameSet) -> FrameSet:
        mirror = QTransform().scale(-1, 1)
        flip = lambda fr: [f.transformed(mirror) for f in fr]  # noqa: E731
        return FrameSet(flip(fs.run), fs.sleep, flip(fs.jump), {k: flip(v) for k, v in fs.extra.items()})

    def _show_friend(self, x: float, y: float, pm):
        fr = self.friend
        fr.move(int(x), int(y))
        fr.set_frame(pm)
        fr.show()
        for ms in (300, 1200):
            QTimer.singleShot(ms, self._hypr_passthrough)

    # ================================================================== #
    # rides and coffee breaks
    # ================================================================== #
    def _ride_busy(self) -> bool:
        """Not now: a call, a film, a game or slides in full screen, focus time, do not disturb, work mode…"""
        s = self.store.settings
        wclass, wtitle, fullscreen = activity._active_window()
        return bool(fullscreen or self.meeting or wellbeing.in_meeting(wclass, wtitle) or s["dnd"] or self.rest_end
                    or self.focus_end or self.work or self.dance or self.trip or self.held
                    or self.activity.kind in ("watch", "movie", "study", "read"))

    def start_ride(self, kind: str = "", auto: bool = False) -> bool:
        s = self.store.settings
        if self.ride_win.running:
            self.ride_win.stop()
            return True
        if not self.pet.isVisible() or s.get("character", "capy") != "capy":
            if not auto:
                self._say("Only Primo (the Capy character) can ride 🐾", 3500)
            return False
        if self.dance or self.trip or self.held:
            return False
        allowed = [k for k in (s.get("ride_animals") or list(rides.RIDES)) if k in rides.RIDES] or list(rides.RIDES)
        kind = kind if kind in rides.RIDES else random.choice(allowed)
        th = themes.get(themes.current(s))
        color = s.get("color", "#1F2A5A") if s.get("my_color_always") else (th["jacket"] or s.get("color", "#1F2A5A"))
        hold, wave = rider_frames(color, th["outfit"])
        passengers = friend_rider_frames() if (s.get("ride_friend", True) and s.get("friend_on", True)) else None
        frames = rides.ride_frames(kind, (s.get("ride_colors") or {}).get(kind, ""),
                                   [wave[i] if i in (2, 3) else hold[i] for i in range(len(hold))], passengers)
        pet = self.pet
        screen = self.app.screenAt(pet.frameGeometry().center()) or pet.screen() or self.app.primaryScreen()
        g = self._work_area(screen)
        go_left = pet.frameGeometry().center().x() > g.center().x()      # sets off toward the far side
        self._say(rides.SAY.get(kind, "Wheee!"), 2200)
        self._poof()
        self._ride_kind = kind
        QTimer.singleShot(650, lambda: self._ride_go(kind, frames, g, go_left))
        return True

    def _ride_go(self, kind, frames, g, go_left):
        if self.dance or self.trip or not self.pet.isVisible():
            return
        self.pet.hide()
        self.rope.set_active(False)
        self.ride_win.start(kind, frames, g, self.pet.pet_size, go_left, max(0, int(self.store.settings.get("pet_lift", 0))))

    def _ride_done(self):
        if not self.store.settings.get("show_pet", True):
            return
        self.pet.show()
        self._poof()
        self.excited_until = time.time() + 1.2
        self.roam_y = None                            # back on the ground, a new lap from here
        self._say(random.choice(("What a ride! 🤩", "Again! Again! 🎢", "That was amazing! ✨")), 3000)

    def choose_avatars(self):
        from .avatar_picker import AvatarDialog
        if getattr(self, "_avatar_dlg", None) is not None:
            self._avatar_dlg.raise_()
            self._avatar_dlg.activateWindow()
            return
        dlg = self._avatar_dlg = AvatarDialog(self.store.settings)
        try:
            ok = dlg.exec()
        finally:
            self._avatar_dlg = None
        if ok:
            dlg.result_into(self.store.settings)
            if self.store.settings.get("character") != "capy":
                self.store.settings["character"] = "capy"      # avatars are all capybaras
            self.store.save_settings()
            self.apply_settings()

    def coffee_break(self):
        s, now = self.store.settings, time.time()
        if not self.frames.extra.get("sip"):
            self._say("☕ (Only Primo drinks coffee 🐾)", 3000)
            return
        if not s.get("pet_roam"):
            self._say("☕ Turn on “run around” first, then I can take a break 🐾", 3500)
            return
        if self.phase not in ("bottom_r", "bottom_end", "nap") or self._seated():
            self._say("☕ Right after this! 🐾", 3000)
            return
        self.phase, self.napping, self.coffee = "nap", True, True
        self.nap_until = now + 45
        self._say(random.choice(("☕ Coffee break! Join me?", "☕ Ahh… a warm cup.", "☕ Sip sip… 😌")), 4000)

    def _friend_name(self) -> str:
        return str(self.store.settings.get("friend_name") or "Jeo OngBack").strip()

    def _dance_song_on(self) -> bool:
        a, s = self.activity, self.store.settings
        if a.kind != "listen":
            return False
        if dance.is_dance_song(a.title, a.artist, s.get("dance_extra") or ()):
            return True
        return bool(s.get("dance_mood", True)) and a.mood in dance.MOOD_DANCES

    def _can_dance(self) -> bool:
        return bool(self.store.settings.get("friend_on", True) and self.pet.isVisible()
                    and self.frames.extra.get("d_bob") and not self._pose() and not self.held
                    and not self.trip)

    def toggle_dance(self, style: str = ""):
        """Start a showdown, or send Jeo home. style = one of dance.STYLES ('' = a random one)."""
        if self.dance:
            if self.dance["stage"] != "leave":
                self.dance.update(stage="leave", until=time.time() + 12)
                self.friend.say("Okay, later! 👋", 2500)
        elif not self.start_dance(style=style):
            self._say("Not right now 😅", 2500)

    def start_dance(self, song: bool = False, style: str = "") -> bool:
        if self.dance or not self._can_dance() or self.pet._press is not None:
            return False
        if self.jeo is None:
            self.jeo = friend_frames()
            self.jeo_flip = self._flip_set(self.jeo)
        pet, fr, now = self.pet, self.friend, time.time()
        screen = self.app.screenAt(pet.frameGeometry().center()) or pet.screen() or self.app.primaryScreen()
        g = self._work_area(screen)
        self._size_friend()
        fr.set_top_layout(False)
        x = g.left() - (pet.width() - pet.pet_size) / 2           # he comes in from the left edge
        if style not in dance.STYLES:
            style = dance.pick_style(self.activity.label if song else "", self.last_style,
                                     self.activity.mood if song else "")
        self.last_style = style
        self.dance = {"stage": "gather", "t0": now, "until": 0.0, "song": song, "turn": "jeo", "n": 0,
                      "move": "", "x": float(x), "fdir": 1, "win": "", "switch": 0.0, "t_both": 0.0,
                      "style": style, "dressed": False, "poof": 0.0, "used": []}
        self._move_frames("primo", style, "", False)  # draw both outfits now, so the change itself is instant
        self._move_frames("jeo", style, "", False)
        self.next_dance = now + max(1, int(self.store.settings.get("dance_every", 30))) * 60 * random.uniform(0.9, 1.1)
        self._show_friend(x, pet.y(), self.jeo.run[0])
        self._sit_now()
        if dance.STYLES[style].get("duet"):
            self._say(f"💞 {self._friend_name()} is here… this is our song!", 3500)
        else:
            self._say(f"🕺 {self._friend_name()} is here… dance showdown!", 3500)
        return True

    def _end_dance(self):
        self.dance = None
        self.styles.clear()                           # the drawn moves are big; they are quick to draw again
        self.friend.hide()
        self.friend._clear_bubble()
        self.next_break = time.time() + random.uniform(15, 35)

    def _dance_tick(self):
        """Runs 30 times a second while a showdown is on: moves Jeo, and moves the showdown along."""
        d = self.dance
        if not d:
            return
        pet, fr, now, s = self.pet, self.friend, time.time(), self.store.settings
        if not self._can_dance() or now - d["t0"] > dance.BOTH_MAX + 120:
            self._end_dance()
            return
        roaming = bool(s.get("pet_roam"))
        screen = self.app.screenAt(pet.frameGeometry().center()) or pet.screen() or self.app.primaryScreen()
        g = self._work_area(screen)
        S = pet.pet_size
        left = g.left() - (pet.width() - S) / 2
        gap = S * 1.15
        side = -1 if pet.x() - gap >= left else 1             # Jeo stands beside Primo, where there is room
        tx = pet.x() + side * gap
        ty = (g.bottom() + 1 - pet.height() - max(0, int(self.store.settings.get("pet_lift", 0)))) if roaming else pet.y()
        step = 7.5 * (S / 96)
        st = d["stage"]
        if st == "gather":                                    # Jeo runs in while Primo gets to his spot
            if abs(tx - d["x"]) <= step:
                d["x"], d["fdir"] = tx, -side
                if not roaming or self.phase == "seat":
                    st_ = dance.STYLES[d["style"]]
                    d["stage"], d["until"] = "intro", now + 3.4
                    fr.say(f"{st_['icon']} {st_['label']}! " + ("Watch this first, Primo…" if st_.get("duet")
                                                                else "Ready, Primo?"), 3200)
            else:
                d["fdir"] = 1 if tx > d["x"] else -1
                d["x"] += step * d["fdir"]
            if now - d["t0"] > 30:                            # Primo never made it (sulking, being carried…)
                self._end_dance()
                return
        elif st == "leave":                                   # off he goes, back out on the left
            d["fdir"] = -1
            d["x"] -= step
            if d["x"] <= left or now >= d["until"]:
                self._end_dance()
                return
        else:
            d["x"], d["fdir"] = tx, -side
            if not roaming:
                self.dir = side                               # the two face each other
            if st == "intro" and not d["dressed"] and now >= d["until"] - 1.6:
                d["dressed"], d["poof"] = True, now + self.POOF_SECS       # poof! both in the outfit of the style
                self._poof()
                self._say("✨ Poof! Outfit change!", 1600)
            if now >= d["until"]:
                self._dance_next(d, now)
            elif st in ("turn", "solo", "both") and now >= d["switch"]:
                self._new_move(d, now)
        fr.move(int(d["x"]), int(ty))
        pm, hop = self._friend_frame(d, now)
        fr.set_frame(self._poofed(pm, d["poof"]), hop)

    def _dance_next(self, d: dict, now: float):
        st, duet = d["stage"], bool(dance.STYLES[d["style"]].get("duet"))
        if st == "turn":
            d["n"] += 1
        if st == "intro" and duet:                            # Touch by Touch: Jeo shows off on his own first
            d.update(stage="solo", turn="jeo", until=now + dance.SOLO_SECS)
            self._say("Go, Jeo! 🔥", 2500)
            self._new_move(d, now)
        elif st in ("intro", "turn", "solo"):
            if st == "solo" or d["n"] >= dance.ROUNDS * 2:    # everyone has had their turns: dance together
                d.update(stage="both", until=now + (dance.DUET_SECS if duet else dance.BOTH_SECS), t_both=now)
                self._new_move(d, now)
                if duet:
                    self.friend.say("Now you, Primo… touch by touch! 💞", 2600)
                    self._say("Slow and smooth 😏", 2600)
                else:
                    self._say("Together now! 🎶", 2500)
                    self.friend.say("Let's go! 🔥", 2500)
            else:
                d.update(stage="turn", turn="jeo" if d["n"] % 2 == 0 else "primo", until=now + dance.TURN_SECS)
                self._new_move(d, now)
        elif st == "both":
            if d["song"] and self._dance_song_on() and now - d["t_both"] < dance.BOTH_MAX:
                d["until"] = now + 3.0                        # keep dancing while the song lasts
                return
            win = d["win"] = "duet" if duet else random.choice(("primo", "jeo", "tie"))
            d.update(stage="result", until=now + 4.0, t_res=now, dressed=False, poof=now + self.POOF_SECS)
            self._poof()                              # and poof, back into their own clothes
            name = self._friend_name()
            if win == "duet":
                self._say("What a duet! 💞", 3800)
                self.friend.say("Smooth, bro 😎🤝", 3800)
            elif win == "primo":
                self._say("I win this one! 🏆", 3800)
                self.friend.say("Okay okay, you got me 😅", 3800)
            elif win == "jeo":
                self.friend.say(f"{name} takes it! 🏆", 3800)
                self._say("Rematch soon! 😤", 3800)
            else:
                self._say("It's a tie! 🤝", 3800)
                self.friend.say("Good one, bro! 🤝", 3800)
            if win != "jeo":
                self.excited_until = now + 3.5
        elif st == "result":
            d.update(stage="leave", until=now + 12)
            self.friend.say("Next time! 👋", 2500)

    def _dance_frame(self, fs: FrameSet):
        """Primo's pose during the showdown."""
        d, ex, now = self.dance, fs.extra, time.time()
        st = d["stage"]
        if d["dressed"]:                              # in the outfit of the showdown's style
            dancing = st == "both" or (st == "turn" and d["turn"] == "primo")
            fr = self._move_frames("primo", d["style"], d["move"] if dancing else "", fs is self.flipped)
            fps = dance.STYLES[d["style"]].get("fps", 11) if dancing else 8
            return fr[int(now * fps) % len(fr)]
        fr = ex.get("d_wave" if st == "leave" else "d_bob")
        return fr[int(now * 9) % len(fr)] if fr else None

    def _friend_frame(self, d: dict, now: float):
        """(pixmap, hop) for Jeo."""
        fs = self.jeo_flip if d["fdir"] < 0 else self.jeo
        st = d["stage"]
        if st in ("gather", "leave") and (st == "leave" or abs(self.friend.x() - d["x"]) > 0.5):
            return fs.run[int(now * 14) % len(fs.run)], 0
        if st == "result" and d["win"] in ("jeo", "tie", "duet"):
            i = int((now - d.get("t_res", now)) * 18) % len(fs.jump)
            k = i / max(1, len(fs.jump) - 1)
            hop = int(max(0.0, math.sin((k - 0.18) / 0.82 * math.pi)) * self.pet.pet_size * 0.3) if k > 0.18 else 0
            return fs.jump[i], hop
        if not d["dressed"]:
            fr = fs.extra["d_bob"]
            return fr[int(now * 8) % len(fr)], 0
        dancing = st in ("both", "solo") or (st == "turn" and d["turn"] == "jeo")
        fr = self._move_frames("jeo", d["style"], d["move"] if dancing else "", d["fdir"] < 0)
        fps = (dance.STYLES[d["style"]].get("fps", 11) if st == "both" else 11) if dancing else 8
        return fr[int(now * fps) % len(fr)], 0

    # ================================================================== #
    # space day: once a day Primo invites Jeo along on the rocket
    # ================================================================== #
    def _start_trip(self) -> bool:
        s = self.store.settings
        today = date.today().isoformat()
        if (self.trip or self.dance or not s.get("friend_on", True) or s.get("space_trip_day") == today
                or not self.frames.extra.get("rocket2")):
            return False
        s["space_trip_day"] = today                   # one invitation a day
        self.store.save_settings()
        if self.jeo_space is None:
            self.jeo_space = friend_frames(space=True)
            self.jeo_space_flip = self._flip_set(self.jeo_space)
        pet = self.pet
        screen = self.app.screenAt(pet.frameGeometry().center()) or pet.screen() or self.app.primaryScreen()
        g = self._work_area(screen)
        self._size_friend()
        self.friend.set_top_layout(False)
        x = g.left() - (pet.width() - pet.pet_size) / 2
        self.trip = {"stage": "board", "x": float(x), "y": pet.y(), "until": time.time() + 40, "said": False}
        self._show_friend(x, pet.y(), self.jeo_space.run[0])
        self._say(f"{self._friend_name().split()[0]}! Come to space with me! 🚀", 4000)
        return True

    def _end_trip(self):
        self.trip = None
        self.friend.hide()
        self.friend._clear_bubble()
        self.friend.set_top_layout(False)

    def _trip_tick(self):
        t = self.trip
        if not t:
            return
        pet, fr, now, ph = self.pet, self.friend, time.time(), self.phase
        S = pet.pet_size
        step = 9 * (S / 96)
        st = t["stage"]
        ok = (pet.isVisible() and not self.held and not self.dance and self.jeo_space is not None
              and themes.get(self.theme)["climb"] == "rocket")
        allowed = {"board": ("prelaunch",), "inside": ("prelaunch", "climb", "top"),
                   "out": ("top", "think", "descend", "bottom_end")}
        if not ok or (st in allowed and ph not in allowed[st]):
            self._end_trip()                          # the trip was cut short (grabbed, music came on…)
            return
        right_, left_ = self.jeo_space, self.jeo_space_flip
        if st == "board":                             # running over to the rocket
            if abs(pet.x() - t["x"]) <= step or now >= t["until"]:
                t["stage"] = "inside"
                fr.hide()
                self._say("Seatbelt on! 😎", 2000)
                return
            t["x"] += step
            fr.move(int(t["x"]), pet.y())
            fr.set_frame(right_.run[int(now * 14) % len(right_.run)])
        elif st == "inside":
            if ph == "top":                           # in orbit: out he floats
                t["stage"] = "out"
                self._show_friend(pet.x() + S * 0.9, pet.y(), left_.extra["float"][0])
                fr.say("Whoa, I'm flying! 🤩", 3500)
        elif st == "out":
            if ph in ("top", "think"):                # floating along beside Primo
                fr.set_top_layout(True)
                fr.move(int(pet.x() + S * 0.9), int(pet.y() + S * 0.07 * math.sin(now * 1.7 + 1.2)))
                fr.set_frame(left_.extra["float"][int(now * 8) % 12])
                if ph == "think" and not t["said"]:
                    t["said"] = True
                    QTimer.singleShot(1800, lambda: self.trip and fr.say("The whole world… 🌍", 3000))
            elif ph == "descend":                     # his own parachute, a little above
                fr.set_top_layout(False)
                fr.move(int(pet.x() + S * 0.95), int(max(pet.y() - S * 0.35, 0)))
                fr.set_frame(left_.extra["chute"][int(now * 7) % 12])
            else:                                     # landed
                t.update(stage="bye", until=now + 3.4, x=float(fr.x()), y=pet.y())
                fr.move(fr.x(), pet.y())
                fr.say("Best trip ever! See you at the fiesta 🎉", 3400)
        elif st == "bye":
            fr.set_frame(left_.extra["d_bob"][int(now * 8) % 8])
            if now >= t["until"]:
                t.update(stage="leave", until=now + 6)
        elif st == "leave":                           # home again, off to the left
            t["x"] -= step
            fr.move(int(t["x"]), int(t["y"]))
            fr.set_frame(left_.run[int(now * 14) % len(left_.run)])
            screen = self.app.screenAt(pet.frameGeometry().center()) or pet.screen() or self.app.primaryScreen()
            if t["x"] <= self._work_area(screen).left() - (pet.width() - S) / 2 or now >= t["until"]:
                self._end_trip()

    # ================================================================== #
    # chatting in the speech bubble
    # ================================================================== #
    def _words(self, key: str, **extra) -> str:
        """A phrase from settings ({name}/{greet} filled in). Lists give a random line; '' means stay quiet."""
        v = self.store.settings.get(key, "")
        if isinstance(v, (list, tuple)):
            v = [x for x in v if str(x).strip()]
            v = random.choice(v) if v else ""
        h = datetime.now().hour
        greet = "Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening"
        name = str(self.store.settings.get("pet_name") or "Primo")
        out = str(v).replace("{name}", name).replace("{greet}", greet)
        for k, val in extra.items():
            out = out.replace("{" + k + "}", str(val))
        return out.strip()

    def chat(self, hello: bool = False, clicked: bool = False):
        if not self.pet.isVisible():
            return
        overdue, today, open_ = self.store.task_counts()
        unread = self.store.unread()
        h = datetime.now().hour
        greet = "Good morning" if h < 12 else "Good afternoon" if h < 18 else "Good evening"
        if hello:
            msg = self._words("say_hello") or f"{greet}!"
            if overdue:
                msg += f" — {overdue} task{'s' if overdue > 1 else ''} overdue!"
            elif today:
                msg += f" — {today} task{'s' if today > 1 else ''} today."
        elif overdue:
            msg = f"🏃 {overdue} overdue task{'s' if overdue > 1 else ''}! Double-click me."
        elif unread:
            msg = f"📬 {unread} unread notification{'s' if unread > 1 else ''}."
        elif today:
            msg = f"📋 {today} task{'s' if today > 1 else ''} due today."
        elif clicked:
            msg = self._words("say_click") if random.random() < 0.5 else self._cheer()
            msg = msg or self._words("say_click") or self._cheer()
        else:
            msg = self._cheer()
        if clicked:
            self.roam_pause_until = time.time() + 3
        if msg:
            self.pet.say(msg, 5000)

    # ================================================================== #
    # notifications & reminders
    # ================================================================== #
    def notify(self, title: str, body: str = "", source: str = "app", record: bool = True):
        if record:
            self.store.add_notification(title, body, source)
        if self.focus_end or time.time() < self.breathe_end:      # keep it for later: no jumping, no pop-up
            if self.focus_end:
                self.focus_held += 1
            self.update_stats()
            self.panel.refresh_notifs()
            return
        self.excited_until = time.time() + 4
        self.update_stats()
        self.panel.refresh_notifs()
        if self.pet.isVisible():
            self.pet.say(title if not body else f"{title} — {body}")
        if self.store.settings["dnd"]:
            return
        self._desktop_notify(title, body)

    def _desktop_notify(self, title: str, body: str = ""):
        if self.tray.isVisible() and self.tray.supportsMessages() and not IS_LINUX:
            self.tray.showMessage(title, body or " ", QSystemTrayIcon.Information, 8000)
        elif IS_LINUX and shutil.which("notify-send"):
            try:
                subprocess.Popen(["notify-send", "-a", "CapyRunner", "-i", "capyrunner", title, body],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            except OSError:
                pass
        elif self.tray.isVisible():
            self.tray.showMessage(title, body or " ", QSystemTrayIcon.Information, 8000)

    def check_reminders(self):
        now = datetime.now()
        changed = False
        for t in self.store.tasks:
            if t.get("done") or t.get("reminded") or not t.get("due"):
                continue
            try:
                due = datetime.fromisoformat(t["due"])
            except ValueError:
                continue
            if due <= now:
                t["reminded"] = True
                changed = True
                late = int((now - due).total_seconds() // 60)
                self.notify(f"⏰ {t['title']}", "Due now" if late < 2 else f"Overdue by {late} min", "reminder")
        if changed:
            self.store.save_data()
            self.panel.refresh_tasks()

    # ================================================================== #
    def quick_add(self):
        text, ok = QInputDialog.getText(None, "Quick add task",
                                        "Task (e.g. “Call Jason in 30m”, “Standup @9:30”, “Report tomorrow @14”):")
        if ok and text.strip():
            title, due = quickadd.parse(text)
            self.store.add_task(title, due)
            self.panel.refresh_tasks()
            self.update_stats()

    def _tray_activated(self, reason):
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            if self.panel.isVisible() and self.panel.isActiveWindow():
                self.panel.hide()
            else:
                self.panel.show_and_raise()
        elif reason == QSystemTrayIcon.MiddleClick:
            self.quick_add()

    def _about(self):
        QMessageBox.information(None, "About CapyRunner",
                                f"CapyRunner {__version__}\nDeveloped by {updater.DEVELOPER}\n\n"
                                "A running mascot for your tasks, notes and notifications.\n"
                                "Windows 10/11, Linux (Arch, Ubuntu, Fedora…) and macOS.\n\n"
                                f"Data folder:\n{self.store.folder}")

    # ================================================================== #
    # updates (see updater.py)
    # ================================================================== #
    def check_updates(self, manual: bool = False):
        if manual and self.update_info:
            self._offer_update(self.update_info)
            return
        self._update_manual = manual
        self.updates.check()

    def _update_found(self, info: dict):
        new = bool(info.get("newer"))
        if new:
            self.update_info = info
            self.act_update.setText(f"⬆  Update to {info['version']}…")
        if getattr(self, "_update_manual", False):
            self._update_manual = False
            if new:
                self._offer_update(info)
            else:
                QMessageBox.information(None, "CapyRunner", f"You have the newest version ({__version__}). 🎉")
        elif new:
            self.notify("CapyRunner update", f"Version {info['version']} is ready. Right-click {self._name()} → Update.", "update")
            self._say(f"⬆ New version {info['version']}! Right-click me to update.", 6000)

    def _update_failed(self, why: str):
        if getattr(self, "_update_manual", False):
            self._update_manual = False
            QMessageBox.warning(None, "CapyRunner", f"Could not check for updates.\n\n{why}")

    def _offer_update(self, info: dict):
        how = updater.how_to_update()
        text = f"CapyRunner {info['version']} is out (you have {__version__}).\n\n"
        if how == "installer":
            text += "Update now? CapyRunner closes, updates itself and starts again (about a minute)."
        elif how == "script":
            text += "Open the download page? (Or run install.sh again in the CapyRunner folder.)"
        else:
            text += "Open the download page?"
        if QMessageBox.question(None, "Update CapyRunner", text) != QMessageBox.Yes:
            return
        if how == "installer":
            self._say("⬇ Downloading the update…", 8000)
            self.updates.install(info)
        else:
            updater.open_page(info)

    def _name(self) -> str:
        return str(self.store.settings.get("pet_name") or "Primo")

    def quit(self):
        self.panel.quitting = True
        self.idle.stop()
        self.mic.stop()
        if self.focus_quiet:
            wellbeing.quiet_off()
        self.webhook.stop()
        self.tray.hide()
        self.app.exit(0)


# ====================================================================== #
def _single_instance(name: str, message: bytes = b"show") -> QLocalServer | None:
    """Return a server if we are the first instance; otherwise ping the running one."""
    sock = QLocalSocket()
    sock.connectToServer(name)
    if sock.waitForConnected(300):
        sock.write(message)
        sock.flush()
        sock.waitForBytesWritten(300)
        return None
    QLocalServer.removeServer(name)
    server = QLocalServer()
    server.listen(name)
    return server


def main(argv=None):
    ap = argparse.ArgumentParser(prog="capyrunner", description="Running mascot for tasks & notifications")
    ap.add_argument("--version", action="version", version=__version__)
    ap.add_argument("--reset-position", action="store_true", help="move the floating pet back to the corner")
    ap.add_argument("--notify", nargs="+", metavar=("TITLE", "BODY"), help="send a notification to the running app via webhook")
    ap.add_argument("--settings", action="store_true", help="open the settings window (of the running app, if any)")
    ap.add_argument("--controls", action="store_true", help="open Primo's control panel (of the running app, if any)")
    ap.add_argument("--breathe", action="store_true", help="start / stop the breathing exercise in the running app")
    ap.add_argument("--focus", action="store_true", help="start / stop a focus session in the running app")
    ap.add_argument("--dance", action="store_true", help="start / stop a dance showdown with Jeo in the running app")
    ap.add_argument("--touch", action="store_true", help="start / stop the Touch by Touch dance (Jeo's solo, then the duet)")
    args, qt_args = ap.parse_known_args(argv)

    if args.notify:
        import json
        import urllib.request
        st = Store()
        s = st.settings
        req = urllib.request.Request(f"http://127.0.0.1:{s['webhook_port']}/notify",
                                     data=json.dumps({"title": args.notify[0], "body": " ".join(args.notify[1:]),
                                                      "source": "cli"}).encode(),
                                     headers={"Content-Type": "application/json", "X-Token": s.get("webhook_token", "")})
        try:
            urllib.request.urlopen(req, timeout=3)
            print("sent")
            return 0
        except OSError as e:
            print(f"Could not reach CapyRunner webhook (is it running with webhook enabled?): {e}")
            return 1

    if sys.platform == "win32":                   # its own name and icon on the taskbar and in notifications
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Capytech.CapyRunner")
        except Exception:
            pass
    app = QApplication([sys.argv[0], *qt_args])
    app.setApplicationName("CapyRunner")
    app.setDesktopFileName("capyrunner")
    app.setQuitOnLastWindowClosed(False)

    server = _single_instance(f"capyrunner-{getpass.getuser()}", b"settings" if args.settings else b"controls" if args.controls
                             else b"breathe" if args.breathe else b"focus" if args.focus else b"dance" if args.dance else b"touch" if args.touch else b"show")
    if server is None:
        print("CapyRunner is already running — " + ("told Primo." if (args.breathe or args.focus or args.dance or args.touch) else
                                                    "opened its settings." if args.settings else "opened its window."))
        return 0

    store = Store()
    if args.reset_position:
        store.settings["pet_pos"] = None
        store.save_settings()

    from .characters import builtin_frames
    app.setWindowIcon(QIcon(builtin_frames("capy", "#1F2A5A").run[0]))

    runner = CapyRunner(app, store)

    def on_conn():
        c = server.nextPendingConnection()

        def on_msg():
            msg = bytes(c.readAll().data())
            if msg.startswith(b"settings"):
                QTimer.singleShot(0, runner.open_settings)
            elif msg.startswith(b"controls"):
                QTimer.singleShot(0, runner.show_controls)
            elif msg.startswith(b"breathe"):
                QTimer.singleShot(0, runner.toggle_breathe)
            elif msg.startswith(b"focus"):
                QTimer.singleShot(0, runner.toggle_focus)
            elif msg.startswith(b"dance"):
                QTimer.singleShot(0, runner.toggle_dance)
            elif msg.startswith(b"touch"):
                QTimer.singleShot(0, lambda: runner.toggle_dance("touch"))
            else:
                runner.panel.show_and_raise()
        c.readyRead.connect(on_msg)
    server.newConnection.connect(on_conn)
    if args.settings:
        QTimer.singleShot(800, runner.open_settings)
    if args.controls:
        QTimer.singleShot(800, runner.show_controls)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("Note: no system tray found (on GNOME install the 'AppIndicator' extension). "
              "Using the floating pet instead.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
