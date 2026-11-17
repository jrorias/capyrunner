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
from datetime import datetime

import psutil
from PySide6.QtCore import QTimer
from PySide6.QtGui import QAction, QActionGroup, QIcon, QTransform
from PySide6.QtNetwork import QLocalServer, QLocalSocket
from PySide6.QtWidgets import (QApplication, QInputDialog, QMenu,
                               QMessageBox, QSystemTrayIcon)

from . import __version__, autostart, quickadd
from .characters import BASE, BUILTIN, ROPE_X, FrameSet, load_frames, with_badge
from .panel import Panel
from .pet import PetWindow, RopeWindow
from .settings_dialog import SettingsDialog
from .store import Store
from .webhook import WebhookBridge, WebhookServer

IS_LINUX = sys.platform.startswith("linux")


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
        self.pet.context_menu.connect(lambda pos: self.menu.popup(pos))
        self.pet.moved.connect(self._pet_moved)
        self.pet.clicked.connect(self._pet_clicked)
        self.pet.grabbed.connect(self._pet_grabbed)

        self.rope = RopeWindow()

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

        psutil.cpu_percent(None)  # prime
        self.apply_settings(first=True)
        self.update_stats()
        self.check_reminders()
        self.stats_timer.start()
        self.remind_timer.start()
        self.roam_timer.start()
        self.anim.start(100)
        if store.settings.get("greetings", True):
            QTimer.singleShot(1200, lambda: self.chat(hello=True))

    # ================================================================== #
    # menu
    # ================================================================== #
    def _build_menu(self) -> QMenu:
        m = QMenu()
        m.addAction("Open tasks && notes", self.panel.show_and_raise)
        m.addAction("Quick add task…", self.quick_add)
        self.act_notifs = m.addAction("Notifications", self.panel.show_notifications)
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

        self.act_pet = QAction("Show floating pet", m, checkable=True)
        self.act_pet.toggled.connect(lambda on: self._set("show_pet", on))
        m.addAction(self.act_pet)
        self.act_pass = QAction("Click-through pet (never blocks typing or scrolling)", m, checkable=True)
        self.act_pass.toggled.connect(lambda on: self._set("pet_passthrough", on))
        m.addAction(self.act_pass)
        self.act_roam = QAction("Run around the screen", m, checkable=True)
        self.act_roam.toggled.connect(lambda on: self._set("pet_roam", on))
        m.addAction(self.act_roam)
        self.act_dnd = QAction("Do not disturb", m, checkable=True)
        self.act_dnd.toggled.connect(lambda on: self._set("dnd", on))
        m.addAction(self.act_dnd)
        m.addAction("Settings…", self.open_settings)
        m.addSeparator()
        m.addAction("Send test notification", lambda: self.notify("Hello from CapyRunner 👋", "Notifications are working.", "test"))
        m.addAction("About", self._about)
        m.addAction("Quit", self.quit)
        return m

    def _sync_menu(self):
        s = self.store.settings
        for a in self.speed_group.actions():
            a.setChecked(a.data() == s["speed_source"])
        for a in self.char_group.actions():
            a.setChecked(a.data() == s["character"])
        for act, key in ((self.act_pet, "show_pet"), (self.act_pass, "pet_passthrough"),
                         (self.act_roam, "pet_roam"), (self.act_dnd, "dnd")):
            act.blockSignals(True)
            act.setChecked(bool(s.get(key, True)))
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
        self.frames, err = load_frames(s)
        mirror = QTransform().scale(-1, 1)
        flip = lambda fr: [f.transformed(mirror) for f in fr]  # noqa: E731
        self.flipped = FrameSet(flip(self.frames.run), self.frames.sleep, flip(self.frames.jump),
                                {k: flip(v) for k, v in self.frames.extra.items()})
        self.roam_y = None
        self.rope.set_color(s.get("rope_color", "#C79A5B"))
        self._badge_cache.clear()
        self.frame_i = 0
        if err and not first:
            QMessageBox.warning(None, "CapyRunner", f"Custom character problem:\n{err}\n\nUsing Primo for now.")

        tray_ok = QSystemTrayIcon.isSystemTrayAvailable()
        self.tray.setVisible(bool(s["show_tray"]) and tray_ok)
        show_pet = bool(s["show_pet"]) or not self.tray.isVisible()   # never be invisible
        self.pet.set_pet_size(int(s["pet_size"]))
        self.pet.set_passthrough(bool(s.get("pet_passthrough", True)))
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

        if not first or s["autostart"]:
            err = autostart.set_enabled(bool(s["autostart"]))
            if err and not first:
                QMessageBox.warning(None, "CapyRunner", err)
        self._sync_menu()
        self.panel.refresh_notifs()

    def open_settings(self):
        if getattr(self, "_settings_dlg", None) is not None:      # already open: just bring it forward
            self._settings_dlg.raise_()
            self._settings_dlg.activateWindow()
            return
        dlg = self._settings_dlg = SettingsDialog(self.store.settings)
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
            self.pet.set_frame(with_badge(pm, badge, right=fs is self.flipped and not asleep), hop,
                               self.spin if roaming else 0.0)

        if excited and self.frames.jump:
            interval = 55
        elif asleep:
            interval = 900
        elif special is not None or (roaming and self.phase == "fall"):
            interval = 45
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

    def _hypr_passthrough(self):
        """Hyprland gives focus to whatever is under the mouse, so a pet running under the cursor would
        swallow typing and scrolling. no_focus makes Hyprland skip the window for keyboard and mouse."""
        if not (IS_LINUX and os.environ.get("HYPRLAND_INSTANCE_SIGNATURE")):
            return
        on = bool(self.store.settings.get("pet_passthrough", True))
        pet_size = [self.pet.width(), self.pet.height()]
        try:
            out = subprocess.run(["hyprctl", "clients", "-j"], capture_output=True, text=True, timeout=1).stdout
            cmds = []
            for c in json.loads(out):
                if c.get("pid") != os.getpid() or c.get("title") != "CapyRunner":
                    continue
                size = c.get("size") or [0, 0]
                if size[0] <= 2 * RopeWindow.WIDTH:
                    want = True                       # the rope is decoration only
                elif size == pet_size:
                    want = on
                else:
                    continue                          # the tasks panel must stay usable
                cmds.append(f"dispatch setprop address:{c['address']} no_focus {int(want)}")
            if cmds:
                subprocess.run(["hyprctl", "--batch", " ; ".join(cmds)], capture_output=True, timeout=1)
        except Exception:
            pass

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

    CLIMB_RATE = 4.5      # rad/s; one full hand-over-hand cycle = 2*pi / CLIMB_RATE seconds

    def _special_frame(self, fs: FrameSet):
        """Rope poses (only characters that have them, i.e. Primo)."""
        ex, ph, now = fs.extra, self.phase, time.time()
        if not ex:
            return None

        def pick(name: str, fps: float):
            fr = ex.get(name)
            return fr[int(now * fps) % len(fr)] if fr else None

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
        if s.get("pet_roam") and self.phase == "tampo":   # a pat makes it all better
            msg = self._words("say_forgive")
            if msg:
                self.pet.say(msg, 3000)
            self.excited_until = time.time() + 1.3
            self.phase = self.fall_next if self.fall_next != "tampo" else "bottom_r"
            return
        if s.get("pet_roam") and s.get("lap_click_fall", True) and self.phase == "climb":
            msg = self._words("say_fall")                 # poked while climbing: lose the grip
            if msg:
                self.pet.say(msg, 2200)
            self.laugh_after = True
            self.phase, self.phase_until = "slip", time.time() + 0.5
            return
        self.chat(clicked=True)

    def _start_fall(self, then: str):
        self.phase, self.fall_next, self.fall_v = "fall", then, 0.0

    def _roam(self):
        s = self.store.settings
        pet = self.pet
        if not (s.get("pet_roam") and pet.isVisible()):
            self.napping, self.spin = False, 0.0
            self.rope.set_active(False)
            return
        now = time.time()
        if pet._press is not None:
            return

        screen = self.app.screenAt(pet.frameGeometry().center()) or pet.screen() or self.app.primaryScreen()
        g = self._work_area(screen)
        W, H, S = pet.width(), pet.height(), pet.pet_size
        left = g.left() - (W - S) / 2                 # sprite touching the left edge
        right = g.right() + 1 - W + (W - S) / 2       # sprite touching the right edge
        bottom = g.bottom() + 1 - H                   # sprite standing on the bottom edge
        top = g.top() - pet.BUBBLE_H                  # sprite touching the top edge

        if self.roam_y is None:                       # first run / after a drag / settings change
            self.roam_x = min(max(float(pet.x()), left), right)
            self.roam_y = float(pet.y() - (pet.BUBBLE_H if pet.top_layout else 0))
            self.spin, self.napping = 0.0, False
            if self.held:                             # just put down after being carried
                self.held, self.tampo_after = False, True
            self.fall_next = "bottom_r"
            if self.roam_y < bottom - 2:
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

        if ph == "nap":
            if now >= self.nap_until or excited:
                self.napping, self.phase, self.dir = False, "bottom_r", 1
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
                n = random.choices([0, 1, 2], [0.2, 0.4, 0.4])[0] if s.get("lap_falls", True) else 0
                self.falls = sorted((top + (bottom - top) * random.uniform(0.15, 0.75) for _ in range(n)),
                                    reverse=True)
        elif ph == "climb":                           # hand over hand up the rope on the right edge
            self.dir, self.roam_x = 1, right
            pull = math.sin(now * self.CLIMB_RATE) ** 2               # body rises as an arm pulls
            self.roam_y -= speed * 0.75 * (0.2 + 1.6 * pull)
            if self.falls and self.roam_y <= self.falls[0]:
                self.falls.pop(0)                     # oops — lose the grip
                self.phase, self.phase_until = "slip", now + 0.5
            elif self.roam_y <= top:
                self.roam_y, self.phase, self.dir = top, "top", -1
                self.top_moving, self.top_checks, self.seg_until = True, 0, now      # start with a look around
        elif ph == "slip":
            if now >= self.phase_until:
                self._start_fall("climb")
        elif ph == "fall":
            self.fall_v += 0.9
            self.roam_y += self.fall_v
            self.spin = (self.spin + 13) % 360
            if self.roam_y >= bottom:                 # thud: sit there seeing stars
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
            has_sneak = bool(self.frames.extra.get("sneak")) and bool(s.get("lap_sneak", True))
            if has_sneak and now >= self.seg_until:
                self.top_moving = not self.top_moving
                self.seg_start = now
                if self.top_moving:
                    self.seg_until = now + random.uniform(2.5, 4.5)
                else:
                    self.seg_until = now + random.uniform(1.6, 2.6)
                    self.top_checks += 1
                    if self.top_checks % 3 == 1:      # politely excusing himself, Filipino style
                        msg = self._words("say_top")
                        if msg:
                            self.pet.say(msg, 2800)
            if not has_sneak:
                self.roam_x -= speed
            elif self.top_moving:
                self.roam_x -= 1.6 * (S / 96) * (1.6 if excited else 1)
            if self.roam_x <= left:
                self.roam_x, self.phase = left, "think"
                self.phase_until = now + random.uniform(3.0, 4.5)
        elif ph == "think":                           # look down the rope and think about it first
            self.dir, self.roam_x, self.roam_y = -1, left, top
            if now >= self.phase_until:
                self.phase, self.desc_moving, self.desc_slip, self.seg_until = "descend", False, False, now + 1.0
        elif ph == "descend":                         # nervously down the rope: inch, freeze, inch…
            self.dir, self.roam_x = -1, left
            if now >= self.seg_until:
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
        elif ph == "bottom_end":                      # jog to a nice spot, then sleep
            self.dir, self.roam_y = 1, bottom
            self.roam_x += speed
            if self.roam_x >= self.nap_x:
                self.phase, self.napping = "nap", True
                nap = max(5.0, float(s.get("nap_seconds", 60)))
                self.nap_until = now + nap * (random.uniform(0.75, 1.3) if self.sleeping else random.uniform(0.2, 0.4))

        on_rope = (self.phase in ("climb", "slip", "think", "descend")
                   or (self.phase in ("fall", "dizzy", "laugh") and self.fall_next == "climb"))
        if on_rope:
            off = S / 2                                   # rope through the middle of the sprite…
            if self.frames.extra:                         # …or in front of it, where the paws grip
                off = S * (ROPE_X if self.dir > 0 else BASE - ROPE_X) / BASE
            rx = int(self.roam_x + (W - S) / 2 + off - self.rope.WIDTH / 2)
            if (self.rope.x(), self.rope.y(), self.rope.height()) != (rx, g.top(), g.height()):
                self.rope.setGeometry(rx, g.top(), self.rope.WIDTH, g.height())
        self.rope.set_active(on_rope)
        self._place(top_layout=self.phase in ("top", "think"))

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
            msg = self._words("say_click") if random.random() < 0.5 else self._words("say_cheers")
            msg = msg or self._words("say_click") or self._words("say_cheers")
        else:
            msg = self._words("say_cheers")
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
        self.excited_until = time.time() + 4
        self.update_stats()
        self.panel.refresh_notifs()
        if self.pet.isVisible():
            self.pet.say(title if not body else f"{title} — {body}")
        if self.store.settings["dnd"]:
            return
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
                                f"CapyRunner {__version__}\nA running mascot for your tasks, notes and notifications.\n\n"
                                f"Data folder:\n{self.store.folder}")

    def quit(self):
        self.panel.quitting = True
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

    app = QApplication([sys.argv[0], *qt_args])
    app.setApplicationName("CapyRunner")
    app.setDesktopFileName("capyrunner")
    app.setQuitOnLastWindowClosed(False)

    server = _single_instance(f"capyrunner-{getpass.getuser()}", b"settings" if args.settings else b"show")
    if server is None:
        print("CapyRunner is already running — opened its " + ("settings." if args.settings else "window."))
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
            else:
                runner.panel.show_and_raise()
        c.readyRead.connect(on_msg)
    server.newConnection.connect(on_conn)
    if args.settings:
        QTimer.singleShot(800, runner.open_settings)

    if not QSystemTrayIcon.isSystemTrayAvailable():
        print("Note: no system tray found (on GNOME install the 'AppIndicator' extension). "
              "Using the floating pet instead.")
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
