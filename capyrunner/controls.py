"""Primo's control panel: a small ordinary window (with a Close button) that opens when you right-click the pet.

It replaces the pop-up menu on the pet, which could get stuck open on Wayland compositors: a pop-up
only closes when it sees a click elsewhere, and under XWayland it never sees clicks on other apps.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton,
                               QSlider, QSpinBox, QVBoxLayout, QWidget)

from . import activity, themes, uitheme, wellbeing, workmode

MODES = (("auto", "Decides by himself (auto)"), ("listen", "🎧 Listens with headphones"),
         ("watch", "📱 Watches cosy, on his phone"), ("movie", "🍿 Watches with popcorn"),
         ("study", "📝 Takes notes (tutorial / podcast)"), ("read", "📖 Reads a book"))
SPEEDS = (("mix", "Tasks + notifications + CPU"), ("tasks", "Tasks & notifications only"), ("cpu", "CPU only"))
TOGGLES = (("show_pet", "Show floating pet"), ("pet_roam", "Run around the screen"),
           ("activity_react", "Join in with music, videos and reading"),
           ("activity_caption", "Show the small “now playing” line"),
           ("break_remind", "Remind me to take a break"),
           ("friend_on", "Jeo comes round for dance showdowns"),
           ("meeting_look", "Office look with a headset during calls"),
           ("work_on", "Work modes: at his desk while I use Storyline (and my apps)"),
           ("focus_quiet_system", "Focus also silences other apps' pop-ups"),
           ("pet_ghost", "Ghost mode (pet can't be touched)"), ("dnd", "Do not disturb"))


def _line() -> QFrame:
    f = QFrame()
    f.setFrameShape(QFrame.HLine)
    f.setStyleSheet("color: rgba(128,128,128,90);")
    return f


class ControlPanel(QWidget):
    def __init__(self, runner):
        super().__init__(None, Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.r = runner
        self.setWindowTitle("Primo controls")
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self._loading = False

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 12, 14, 12)
        root.setSpacing(8)

        # ---- header: name, what is going on, close ------------------------------------- #
        head = QHBoxLayout()
        self.title = QLabel()
        self.title.setStyleSheet("font-size: 15px; font-weight: 600;")
        close = QPushButton("✕  Close")
        close.setToolTip("Close this panel (Esc)")
        close.clicked.connect(self.close)
        head.addWidget(self.title, 1)
        head.addWidget(close)
        root.addLayout(head)
        self.now = QLabel()
        self.now.setWordWrap(True)
        self.now.setStyleSheet("color: palette(mid);")
        root.addWidget(self.now)

        # ---- quick actions --------------------------------------------------------------- #
        row = QHBoxLayout()
        self.btn_tasks = QPushButton("Tasks && notes")
        self.btn_add = QPushButton("Quick add task…")
        self.btn_notifs = QPushButton("Notifications")
        self.btn_tasks.clicked.connect(lambda: (self.close(), runner.panel.show_and_raise()))
        self.btn_add.clicked.connect(lambda: (self.close(), runner.quick_add()))
        self.btn_notifs.clicked.connect(lambda: (self.close(), runner.panel.show_notifications()))
        for b in (self.btn_tasks, self.btn_add, self.btn_notifs):
            row.addWidget(b)
        root.addLayout(row)
        root.addWidget(_line())

        # ---- wellbeing: breathe, focus, breaks ------------------------------------------- #
        self.well = QLabel("🖥 At the screen for 0 min · break reminder in 50 min")
        self.well.setWordWrap(True)
        root.addWidget(self.well)
        row = QHBoxLayout()
        self.btn_breathe = QPushButton("🌿  Breathe with Primo")
        self.btn_breathe.setToolTip("Two short breaths in, one long breath out. Primo shows the rhythm.")
        self.btn_breathe.clicked.connect(self._breathe)
        self.breathe_min = QSpinBox(minimum=1, maximum=5, suffix=" min")
        self.breathe_min.valueChanged.connect(lambda v: self._choose("breathe_minutes", v))
        row.addWidget(self.btn_breathe, 1)
        row.addWidget(self.breathe_min)
        root.addLayout(row)
        row = QHBoxLayout()
        self.focus_task = QComboBox()
        self.focus_task.setToolTip("The task this focus session is for")
        self.focus_task.setMinimumWidth(170)
        self.focus_min = QSpinBox(minimum=5, maximum=120, singleStep=5, suffix=" min")
        self.focus_min.valueChanged.connect(lambda v: self._choose("focus_minutes", v))
        self.btn_focus = QPushButton("🎯  Start focus")
        self.btn_focus.setToolTip("Primo works beside you and keeps notifications quiet until the timer ends")
        self.btn_focus.clicked.connect(self._focus)
        row.addWidget(self.focus_task, 1)
        row.addWidget(self.focus_min)
        row.addWidget(self.btn_focus)
        root.addLayout(row)
        self.btn_dance = QPushButton("🕺  Dance showdown with Jeo")
        self.btn_dance.setToolTip("Jeo runs in and the two take turns dancing. It also starts by itself when a dance song plays.")
        self.btn_dance.clicked.connect(lambda: (runner.toggle_dance(), self.close()))
        self.btn_touch = QPushButton("💞  Touch by Touch")
        self.btn_touch.setToolTip("Jeo dances a solo, then Primo joins him for the slow duet. Also starts when the song plays.")
        self.btn_touch.clicked.connect(lambda: (runner.toggle_dance("touch"), self.close()))
        row = QHBoxLayout()
        row.addWidget(self.btn_dance, 1)
        row.addWidget(self.btn_touch, 1)
        root.addLayout(row)
        # ---- fun: rides, coffee, clothes ---------------------------------------- #
        from . import rides
        row = QHBoxLayout()
        self.ride_pick = QComboBox()
        self.ride_pick.addItem("🎲  Surprise me", "")
        for key, (label, _, _) in rides.RIDES.items():
            self.ride_pick.addItem(label, key)
        self.ride_pick.setToolTip("He rides it across the screen. You can keep clicking and typing through it.")
        b_ride = QPushButton("Ride!")
        b_ride.clicked.connect(lambda: (runner.start_ride(self.ride_pick.currentData() or ""), self.close()))
        b_coffee = QPushButton("☕  Coffee")
        b_coffee.setToolTip("A coffee break, right now")
        b_coffee.clicked.connect(lambda: (runner.coffee_break(), self.close()))
        self.b_jacket = QPushButton("👕  Jacket")
        self.b_jacket.setToolTip("Change the colour of his jacket")
        self.b_jacket.clicked.connect(lambda: self._pick_color("color", "Jacket colour", True))
        self.b_cup = QPushButton("🥤  Cup")
        self.b_cup.setToolTip("Change the colour of his coffee cup")
        self.b_cup.clicked.connect(lambda: self._pick_color("cup_color", "Cup colour"))
        row.addWidget(QLabel("Ride a"))
        row.addWidget(self.ride_pick, 1)
        row.addWidget(b_ride)
        root.addLayout(row)
        b_avatar = QPushButton("🎭  Avatar")
        b_avatar.setToolTip("Choose who runs on your screen (Primo, Jeo, Geelee, Koko, Luna, Tito…) and the dance friend")
        b_avatar.clicked.connect(lambda: (self.close(), runner.choose_avatars()))
        row = QHBoxLayout()
        for b in (b_avatar, b_coffee, self.b_jacket, self.b_cup):
            row.addWidget(b, 1)
        root.addLayout(row)
        row = QHBoxLayout()
        self.btn_done = QPushButton("✓  Mark the focus task done")
        self.btn_done.clicked.connect(runner.finish_focus_task)
        self.break_every = QSpinBox(minimum=15, maximum=180, singleStep=5, prefix="Break every ", suffix=" min")
        self.break_every.valueChanged.connect(lambda v: self._choose("break_every", v))
        row.addWidget(self.btn_done, 1)
        row.addWidget(self.break_every)
        root.addLayout(row)
        root.addWidget(_line())

        # ---- media + volume -------------------------------------------------------------- #
        media = QHBoxLayout()
        for text, cmd, tip in (("⏮", "previous", "Previous"), ("⏯", "play-pause", "Play / pause"), ("⏭", "next", "Next")):
            b = QPushButton(text)
            b.setToolTip(tip)
            b.setFixedWidth(44)
            b.clicked.connect(lambda _=False, c=cmd: runner._media(c))
            media.addWidget(b)
        media.addSpacing(8)
        self.mute = QPushButton("🔊")
        self.mute.setToolTip("Mute / unmute")
        self.mute.setFixedWidth(44)
        self.mute.clicked.connect(self._toggle_mute)
        self.vol = QSlider(Qt.Horizontal, minimum=0, maximum=100)
        self.vol.setMinimumWidth(150)
        self.vol.valueChanged.connect(self._vol_changed)
        self.vol_label = QLabel("–")
        self.vol_label.setMinimumWidth(40)
        media.addWidget(self.mute)
        media.addWidget(self.vol, 1)
        media.addWidget(self.vol_label)
        root.addLayout(media)
        root.addWidget(_line())

        # ---- choices --------------------------------------------------------------------- #
        grid = QGridLayout()
        grid.setColumnStretch(1, 1)
        self.mode = QComboBox()
        for key, label in MODES:
            self.mode.addItem(label, key)
        self.mode.currentIndexChanged.connect(lambda: self._choose("activity_mode", self.mode.currentData(), poll=True))
        self.speed = QComboBox()
        for key, label in SPEEDS:
            self.speed.addItem(label, key)
        self.speed.currentIndexChanged.connect(lambda: self._choose("speed_source", self.speed.currentData()))
        self.font = QSpinBox(minimum=10, maximum=18, suffix=" px")
        self.font.valueChanged.connect(lambda v: self._choose("bubble_font", v))
        self.adventure = QComboBox()
        self.adventure.addItem("Follow the weekday (auto)", "auto")
        for key in themes.ORDER:
            self.adventure.addItem(f"{themes.THEMES[key]['icon']}  {themes.THEMES[key]['label']}", key)
        self.adventure.currentIndexChanged.connect(lambda: self._choose("day_theme", self.adventure.currentData()))
        grid.addWidget(QLabel("Today's adventure"), 3, 0)
        grid.addWidget(self.adventure, 3, 1)
        grid.addWidget(QLabel("When something plays"), 0, 0)
        grid.addWidget(self.mode, 0, 1)
        grid.addWidget(QLabel("Speed follows"), 1, 0)
        grid.addWidget(self.speed, 1, 1)
        grid.addWidget(QLabel("Bubble text size"), 2, 0)
        grid.addWidget(self.font, 2, 1, Qt.AlignLeft)
        self.seat = QComboBox()
        for key, label in workmode.SEAT_SIDES:
            self.seat.addItem(label, key)
        self.seat.setToolTip("Where he sits for calls, work modes, music, videos and reading")
        self.seat.currentIndexChanged.connect(lambda: self._choose("seat_side", self.seat.currentData()))
        grid.addWidget(QLabel("He sits"), 4, 0)
        grid.addWidget(self.seat, 4, 1)
        self.ui_theme = QComboBox()
        for key in uitheme.ORDER:
            self.ui_theme.addItem(uitheme.THEMES[key]["label"], key)
        self.ui_theme.currentIndexChanged.connect(lambda: self._choose("ui_theme", self.ui_theme.currentData()))
        grid.addWidget(QLabel("App theme"), 5, 0)
        grid.addWidget(self.ui_theme, 5, 1)
        self.name = QLineEdit(maxLength=24)
        self.name.setPlaceholderText("Primo")
        self.name.setToolTip("His name: used in the panel and wherever his words say {name}. Press Enter to keep it.")
        self.name.editingFinished.connect(lambda: self._choose("pet_name", self.name.text().strip() or "Primo"))
        grid.addWidget(QLabel("Name"), 6, 0)
        grid.addWidget(self.name, 6, 1)
        self.height_ = QSpinBox(minimum=32, maximum=320, singleStep=8, suffix=" px")
        self.height_.setKeyboardTracking(False)
        self.height_.setToolTip("How tall he is")
        self.height_.valueChanged.connect(lambda v: self._choose("pet_size", v))
        grid.addWidget(QLabel("Height"), 7, 0)
        grid.addWidget(self.height_, 7, 1, Qt.AlignLeft)
        wrow = QHBoxLayout()
        self.width_ = QSlider(Qt.Horizontal, minimum=50, maximum=200, singleStep=5, pageStep=10)
        self.width_.setTracking(False)          # changes when you let go of the handle
        self.width_.setToolTip("Slimmer ← → wider (100 % = as drawn)")
        self.width_lbl = QLabel("100 %")
        self.width_lbl.setMinimumWidth(48)
        self.width_.sliderMoved.connect(lambda v: self.width_lbl.setText(f"{v} %"))
        self.width_.valueChanged.connect(lambda v: (self.width_lbl.setText(f"{v} %"), self._choose("pet_width", v)))
        wrow.addWidget(self.width_, 1)
        wrow.addWidget(self.width_lbl)
        grid.addWidget(QLabel("Width"), 8, 0)
        grid.addLayout(wrow, 8, 1)
        root.addLayout(grid)

        self.checks: dict[str, QCheckBox] = {}
        for key, label in TOGGLES:
            c = QCheckBox(label)
            c.toggled.connect(lambda on, k=key: self._choose(k, on))
            self.checks[key] = c
            root.addWidget(c)
        root.addWidget(_line())

        # ---- bottom ---------------------------------------------------------------------- #
        foot = QHBoxLayout()
        b_set = QPushButton("All settings…")
        b_set.clicked.connect(lambda: (self.close(), runner.open_settings()))
        b_quit = QPushButton("Quit Primo")
        b_quit.clicked.connect(runner.quit)
        foot.addWidget(b_set)
        foot.addStretch(1)
        foot.addWidget(b_quit)
        root.addLayout(foot)

        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.close)
        self.setFixedSize(self.sizeHint())           # fixed size: tiling compositors keep it floating

    # ------------------------------------------------------------------ #
    def _pick_color(self, key: str, title: str, jacket: bool = False):
        from PySide6.QtGui import QColor
        from PySide6.QtWidgets import QColorDialog
        st = self.r.store.settings
        c = QColorDialog.getColor(QColor(st.get(key) or "#1F2A5A"), self, title)
        if not c.isValid():
            return
        if jacket:
            st["my_color_always"] = True          # a colour picked here should show today, whatever the adventure
        self.r._set(key, c.name())

    def _choose(self, key: str, value, poll: bool = False):
        if self._loading or self.r.store.settings.get(key) == value:
            return
        self.r._set(key, value)
        if poll:
            self.r._poll_activity()

    def _breathe(self):
        starting = not self.r.breathe_end
        self.r.toggle_breathe()
        if starting:
            self.close()                              # so you can watch him

    def _focus(self):
        if self.r.focus_end:
            self.r.stop_focus()
        else:
            self.r.start_focus(self.focus_min.value(), self.focus_task.currentData())
            self.close()

    def sync_wellbeing(self):
        """The part that changes every second: timers and button labels."""
        r = self.r
        self.well.setText(r.wellbeing_status())
        self.btn_breathe.setText("■  Stop breathing" if r.breathe_end else f"🌿  Breathe with {r.store.settings.get('pet_name') or 'Primo'}")
        self.btn_focus.setText("■  Stop focus" if r.focus_end else "🎯  Start focus")
        for w in (self.focus_task, self.focus_min):
            w.setEnabled(not r.focus_end)
        self.btn_done.setEnabled(bool(r.done_offer))

    def _vol_changed(self, v: int):
        if self._loading:
            return
        activity.set_volume(v)
        self.vol_label.setText(f"{v}%")

    def _toggle_mute(self):
        activity.toggle_mute()
        self.sync_volume()

    def sync_volume(self):
        cur = activity.get_volume()
        self._loading = True
        ok = cur is not None
        for w in (self.vol, self.mute):
            w.setEnabled(ok)
        if ok:
            self.vol.setValue(cur[0])
            self.vol_label.setText(f"{cur[0]}%")
            self.mute.setText("🔇" if cur[1] else "🔊")
        else:
            self.vol_label.setText("n/a")
        self._loading = False

    def sync(self):
        """Load the current settings and state into the widgets."""
        s, r = self.r.store.settings, self.r
        self._loading = True
        self.title.setText(str(s.get("pet_name") or "Primo"))
        self.setWindowTitle(f"{s.get('pet_name') or 'Primo'} controls")
        act = r.activity
        if r.work:
            self.now.setText(f"💻 {r.work.name} · {r.work.app}")
        elif act:
            self.now.setText(f"{r.ACT_ICON.get(act.kind, '')} {act.label or act.kind.capitalize()}")
        else:
            self.now.setText("Nothing playing right now.")
        unread = r.store.unread()
        self.btn_notifs.setText(f"Notifications ({unread})" if unread else "Notifications")
        self.mode.setCurrentIndex(max(0, self.mode.findData(s.get("activity_mode", "auto"))))
        self.speed.setCurrentIndex(max(0, self.speed.findData(s.get("speed_source", "mix"))))
        self.adventure.setCurrentIndex(max(0, self.adventure.findData(s.get("day_theme", "auto"))))
        self.seat.setCurrentIndex(max(0, self.seat.findData(s.get("seat_side", "right"))))
        self.name.setText(str(s.get("pet_name") or "Primo"))
        self.height_.setValue(int(s.get("pet_size", 96)))
        self.width_.setValue(int(s.get("pet_width", 100)))
        self.width_lbl.setText(f"{self.width_.value()} %")
        self.ui_theme.setCurrentIndex(max(0, self.ui_theme.findData(s.get("ui_theme", "system"))))
        self.font.setValue(int(s.get("bubble_font", 13)))
        self.breathe_min.setValue(int(s.get("breathe_minutes", 2)))
        self.focus_min.setValue(int(s.get("focus_minutes", 25)))
        self.break_every.setValue(int(s.get("break_every", 50)))
        keep = r.focus_task or self.focus_task.currentData()
        self.focus_task.clear()
        self.focus_task.addItem("No particular task", None)
        for t in r.store.tasks:
            if not t.get("done"):
                title = str(t.get("title", ""))
                self.focus_task.addItem(title if len(title) <= 40 else title[:39] + "…", t["id"])
        if keep:
            self.focus_task.setCurrentIndex(max(0, self.focus_task.findData(keep)))
        self.sync_wellbeing()
        for key, c in self.checks.items():
            c.setChecked(bool(s.get(key, key != "pet_ghost" and key != "dnd")))
        self._loading = False
        self.sync_volume()

    def open_near(self, pos: QPoint):
        """Show next to where the pet was clicked, fully on that screen."""
        self.sync()
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        x = min(max(pos.x() - self.width() - 12, g.left() + 8), g.right() - self.width() - 8)
        y = min(max(pos.y() - self.height() - 12, g.top() + 8), g.bottom() - self.height() - 8)
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
