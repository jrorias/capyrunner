"""Primo's control panel: a small ordinary window (with a Close button) that opens when you right-click the pet.

It replaces the pop-up menu on the pet, which could get stuck open on Wayland compositors: a pop-up
only closes when it sees a click elsewhere, and under XWayland it never sees clicks on other apps.

Layout: a header (his picture, name and what is going on), four tabs (Home, Wellbeing, Fun, Settings) and a
footer. Home has big tiles for the things you do most; everything else is grouped in cards. The window keeps
one size that fits the screen, and a tab scrolls when it holds more than fits.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRectF, QSize, Qt, Signal
from PySide6.QtGui import QColor, QGuiApplication, QKeySequence, QPainter, QShortcut
from PySide6.QtWidgets import (QAbstractButton, QButtonGroup, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel,
                               QLineEdit, QPushButton, QScrollArea, QSizePolicy, QSlider, QSpinBox, QStackedWidget,
                               QVBoxLayout, QWidget)

from . import activity, themes, uitheme, workmode

MODES = (("auto", "Decides by himself (auto)"), ("listen", "🎧 Listens with headphones"),
         ("watch", "📱 Watches cosy, on his phone"), ("movie", "🍿 Watches with popcorn"),
         ("study", "📝 Takes notes (tutorial / podcast)"), ("read", "📖 Reads a book"))
SPEEDS = (("mix", "Tasks + notifications + CPU"), ("tasks", "Tasks & notifications only"), ("cpu", "CPU only"))
TOGGLES = {
    "show_pet": ("Show the floating pet", "Off = only the tray icon"),
    "pet_roam": ("Run around the screen", "Laps along the edges, naps in between"),
    "pet_ghost": ("Ghost mode", "Clicks go straight through him"),
    "activity_react": ("Join in with what I do", "Music, videos and reading"),
    "activity_caption": ("“Now playing” line", "A small line above him"),
    "meeting_look": ("Office look in calls", "Blazer, headset, he talks when you do"),
    "work_on": ("Work modes", "At his desk while you work in your apps"),
    "break_remind": ("Break reminders", "He asks you to stand up and stretch"),
    "focus_quiet_system": ("Focus silences other apps", "Holds other pop-ups during focus"),
    "friend_on": ("Dance friend comes round", "Dance showdowns when a dance song plays"),
    "voice_on": ("Speak out loud", "Reads his speech bubbles in his own voice"),
    "dnd": ("Do not disturb", "No pop-ups and no talking"),
}
TOGGLE_DEFAULT_OFF = {"pet_ghost", "dnd", "voice_on"}

QSS = """
#panel { background: palette(window); }
#panel QLabel { background: transparent; }
QFrame#card { background: palette(base); border: 1px solid rgba(127,127,127,50); border-radius: 14px; }
QLabel#title { font-size: 17px; font-weight: 700; }
QLabel#muted { color: rgba(127,127,127,230); font-size: 12px; }
QLabel#h { font-size: 13px; font-weight: 700; }
QLabel#avatar { background: rgba(127,127,127,35); border-radius: 26px; }
QPushButton#nav { border: none; border-radius: 15px; padding: 6px 4px; background: transparent; font-weight: 600; }
QPushButton#nav:hover { background: rgba(127,127,127,40); }
QPushButton#nav:checked { background: palette(highlight); color: palette(highlighted-text); }
QFrame#navbar { background: rgba(127,127,127,28); border-radius: 18px; }
QPushButton#tile { background: palette(base); border: 1px solid rgba(127,127,127,50); border-radius: 14px; }
QPushButton#tile:hover { border: 1px solid palette(highlight); background: rgba(127,127,127,22); }
QPushButton#tile:pressed { background: rgba(127,127,127,55); }
QPushButton#primary { background: palette(highlight); color: palette(highlighted-text); border: none;
                      border-radius: 10px; padding: 7px 14px; font-weight: 600; }
QPushButton#primary:hover { padding-top: 6px; padding-bottom: 8px; }
QPushButton#primary:disabled { background: rgba(127,127,127,70); }
QPushButton#soft { background: rgba(127,127,127,30); border: none; border-radius: 10px; padding: 7px 12px; }
QPushButton#soft:hover { background: rgba(127,127,127,60); }
QPushButton#round { background: rgba(127,127,127,30); border: none; border-radius: 16px; font-size: 14px; }
QPushButton#round:hover { background: rgba(127,127,127,70); }
QScrollArea, QScrollArea > QWidget > QWidget { background: transparent; border: none; }
"""


# --------------------------------------------------------------------------- #
# small building blocks
# --------------------------------------------------------------------------- #
class Switch(QAbstractButton):
    """An on/off switch (a pill with a knob), nicer to hit than a tiny checkbox."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setCheckable(True)
        self.setCursor(Qt.PointingHandCursor)
        self.setFixedSize(42, 24)

    def sizeHint(self):
        return QSize(42, 24)

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        on = self.isChecked()
        pal = self.palette()
        track = pal.highlight().color() if on else QColor(127, 127, 127, 110)
        if not self.isEnabled():
            track.setAlpha(80)
        p.setPen(Qt.NoPen)
        p.setBrush(track)
        p.drawRoundedRect(QRectF(0, 0, 42, 24), 12, 12)
        p.setBrush(QColor("#FFFFFF"))
        x = 21 if on else 3
        p.drawEllipse(QRectF(x, 3, 18, 18))


class SwitchRow(QWidget):
    """Title, a short explanation underneath, and a switch on the right. Click anywhere on it to flip it."""
    toggled = Signal(bool)

    def __init__(self, title: str, hint: str = ""):
        super().__init__()
        self.setCursor(Qt.PointingHandCursor)
        h = QHBoxLayout(self)
        h.setContentsMargins(2, 4, 2, 4)
        v = QVBoxLayout()
        v.setSpacing(0)
        t = QLabel(title)
        v.addWidget(t)
        if hint:
            m = QLabel(hint)
            m.setObjectName("muted")
            m.setWordWrap(True)
            v.addWidget(m)
        h.addLayout(v, 1)
        self.switch = Switch()
        self.switch.toggled.connect(self.toggled.emit)
        h.addWidget(self.switch, 0, Qt.AlignVCenter)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self.rect().contains(e.position().toPoint()):
            self.switch.toggle()

    def setChecked(self, on: bool):
        self.switch.setChecked(on)

    def isChecked(self) -> bool:
        return self.switch.isChecked()


class Tile(QPushButton):
    """A big square button: an emoji on top, a short label underneath."""

    def __init__(self, icon: str, label: str, tip: str = ""):
        super().__init__()
        self.setObjectName("tile")
        self.setCursor(Qt.PointingHandCursor)
        self.setToolTip(tip)
        self.setMinimumHeight(76)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        v = QVBoxLayout(self)
        v.setContentsMargins(4, 8, 4, 8)
        v.setSpacing(2)
        self.icon = QLabel(icon)
        self.icon.setAlignment(Qt.AlignCenter)
        self.icon.setStyleSheet("font-size: 24px;")
        self.label = QLabel(label)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setWordWrap(True)
        self.label.setStyleSheet("font-size: 12px; font-weight: 600;")
        for w in (self.icon, self.label):
            w.setAttribute(Qt.WA_TransparentForMouseEvents)
            v.addWidget(w)

    def set(self, icon: str | None = None, label: str | None = None):
        if icon is not None:
            self.icon.setText(icon)
        if label is not None:
            self.label.setText(label)


def card(title: str = "", hint: str = "") -> tuple[QFrame, QVBoxLayout]:
    f = QFrame()
    f.setObjectName("card")
    v = QVBoxLayout(f)
    v.setContentsMargins(14, 12, 14, 12)
    v.setSpacing(8)
    if title:
        h = QLabel(title)
        h.setObjectName("h")
        v.addWidget(h)
    if hint:
        m = QLabel(hint)
        m.setObjectName("muted")
        m.setWordWrap(True)
        v.addWidget(m)
    return f, v


def button(text: str, kind: str = "soft", tip: str = "") -> QPushButton:
    b = QPushButton(text)
    b.setObjectName(kind)
    b.setCursor(Qt.PointingHandCursor)
    if tip:
        b.setToolTip(tip)
    return b


def labelled(text: str, w: QWidget) -> QHBoxLayout:
    h = QHBoxLayout()
    lab = QLabel(text)
    lab.setMinimumWidth(110)
    h.addWidget(lab)
    h.addWidget(w, 1)
    return h


def page() -> tuple[QScrollArea, QVBoxLayout]:
    """A tab that scrolls when its cards are taller than the window."""
    inner = QWidget()
    v = QVBoxLayout(inner)
    v.setContentsMargins(0, 0, 6, 0)
    v.setSpacing(10)
    sa = QScrollArea()
    sa.setWidgetResizable(True)
    sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
    sa.setFrameShape(QFrame.NoFrame)
    sa.setWidget(inner)
    return sa, v


# --------------------------------------------------------------------------- #
# the panel
# --------------------------------------------------------------------------- #
class ControlPanel(QWidget):
    WIDTH, HEIGHT = 420, 640

    def __init__(self, runner):
        super().__init__(None, Qt.Dialog | Qt.WindowStaysOnTopHint)
        self.r = runner
        self.setObjectName("panel")
        self.setStyleSheet(QSS)
        self.setWindowTitle("Primo controls")
        self.setAttribute(Qt.WA_QuitOnClose, False)
        self._loading = False
        self.switches: dict[str, SwitchRow] = {}

        root = QVBoxLayout(self)
        root.setContentsMargins(14, 14, 14, 12)
        root.setSpacing(10)

        # ---- header: picture, name, what is going on, close ---------------------------- #
        head = QHBoxLayout()
        head.setSpacing(12)
        self.avatar = QLabel()
        self.avatar.setObjectName("avatar")
        self.avatar.setFixedSize(52, 52)
        self.avatar.setAlignment(Qt.AlignCenter)
        head.addWidget(self.avatar)
        tv = QVBoxLayout()
        tv.setSpacing(1)
        self.title = QLabel()
        self.title.setObjectName("title")
        self.now = QLabel()
        self.now.setObjectName("muted")
        self.now.setWordWrap(True)
        self.now.setMaximumHeight(34)
        tv.addWidget(self.title)
        tv.addWidget(self.now)
        head.addLayout(tv, 1)
        close = button("✕", "round", "Close (Esc)")
        close.setFixedSize(32, 32)
        close.clicked.connect(self.close)
        head.addWidget(close, 0, Qt.AlignTop)
        root.addLayout(head)

        # ---- tabs ------------------------------------------------------------------------ #
        bar = QFrame()
        bar.setObjectName("navbar")
        nav = QHBoxLayout(bar)
        nav.setContentsMargins(4, 4, 4, 4)
        nav.setSpacing(2)
        self.stack = QStackedWidget()
        self.nav = QButtonGroup(self)
        for i, (label, build) in enumerate((("🏠 Home", self._home), ("🌿 Wellbeing", self._wellbeing),
                                            ("🎉 Fun", self._fun), ("⚙ Settings", self._settings))):
            b = QPushButton(label)
            b.setObjectName("nav")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            self.nav.addButton(b, i)
            nav.addWidget(b, 1)
            self.stack.addWidget(build())
        self.nav.idClicked.connect(self.stack.setCurrentIndex)
        self.nav.button(0).setChecked(True)
        root.addWidget(bar)
        root.addWidget(self.stack, 1)

        # ---- footer ---------------------------------------------------------------------- #
        foot = QHBoxLayout()
        b_set = button("⚙  All settings…")
        b_set.clicked.connect(lambda: (self.close(), runner.open_settings()))
        b_quit = button("⏻  Quit")
        b_quit.setToolTip("Close CapyRunner")
        b_quit.clicked.connect(runner.quit)
        foot.addWidget(b_set)
        foot.addStretch(1)
        foot.addWidget(b_quit)
        root.addLayout(foot)

        QShortcut(QKeySequence(Qt.Key_Escape), self, activated=self.close)
        for i in range(4):                       # Alt+1…4 jumps to a tab
            QShortcut(QKeySequence(f"Alt+{i + 1}"), self, activated=lambda i=i: self._go(i))
        self.setFixedSize(self.WIDTH, self.HEIGHT)      # fixed size: tiling compositors keep it floating

    def _go(self, i: int):
        self.nav.button(i).setChecked(True)
        self.stack.setCurrentIndex(i)

    # ---- Home: the things you do most ------------------------------------------------------ #
    def _home(self):
        r = self.r
        sa, v = page()
        self.well = QLabel()
        self.well.setObjectName("muted")
        self.well.setWordWrap(True)
        v.addWidget(self.well)

        grid = QGridLayout()
        grid.setSpacing(8)
        self.t_tasks = Tile("📋", "Tasks & notes", "Your tasks, notes and reminders")
        self.t_tasks.clicked.connect(lambda: (self.close(), r.panel.show_and_raise()))
        self.t_add = Tile("➕", "Add a task", "Quick add a task")
        self.t_add.clicked.connect(lambda: (self.close(), r.quick_add()))
        self.t_notifs = Tile("🔔", "Notifications")
        self.t_notifs.clicked.connect(lambda: (self.close(), r.panel.show_notifications()))
        self.t_breathe = Tile("🌿", "Breathe", "Two short breaths in, one long breath out. He shows the rhythm.")
        self.t_breathe.clicked.connect(self._breathe)
        self.t_focus = Tile("🎯", "Focus", "He works beside you and holds notifications until the timer ends")
        self.t_focus.clicked.connect(self._focus)
        self.t_dance = Tile("🕺", "Dance", "A dance showdown with his friend")
        self.t_dance.clicked.connect(lambda: (r.toggle_dance(), self.close()))
        t_ride = Tile("🐉", "Ride", "He rides an animal across the screen (pick one in Fun)")
        t_ride.clicked.connect(lambda: (r.start_ride(self.ride_pick.currentData() or ""), self.close()))
        t_coffee = Tile("☕", "Coffee break", "A coffee break, right now")
        t_coffee.clicked.connect(lambda: (r.coffee_break(), self.close()))
        t_studio = Tile("🧸", "Avatar Studio", "Dress him up in 3D and give him a voice")
        t_studio.clicked.connect(lambda: (self.close(), r.open_studio()))
        for i, t in enumerate((self.t_tasks, self.t_add, self.t_notifs, self.t_breathe, self.t_focus, self.t_dance,
                               t_ride, t_coffee, t_studio)):
            grid.addWidget(t, i // 3, i % 3)
        v.addLayout(grid)

        # what is playing, and the volume
        c, cv = card("🎵  Now playing")
        self.playing = QLabel()
        self.playing.setObjectName("muted")
        self.playing.setWordWrap(True)
        cv.addWidget(self.playing)
        media = QHBoxLayout()
        for text, cmd, tip in (("⏮", "previous", "Previous"), ("⏯", "play-pause", "Play / pause"),
                               ("⏭", "next", "Next")):
            b = button(text, "round", tip)
            b.setFixedSize(36, 32)
            b.clicked.connect(lambda _=False, c=cmd: r._media(c))
            media.addWidget(b)
        media.addSpacing(6)
        self.mute = button("🔊", "round", "Mute / unmute")
        self.mute.setFixedSize(36, 32)
        self.mute.clicked.connect(self._toggle_mute)
        self.vol = QSlider(Qt.Horizontal, minimum=0, maximum=100)
        self.vol.valueChanged.connect(self._vol_changed)
        self.vol_label = QLabel("–")
        self.vol_label.setMinimumWidth(38)
        media.addWidget(self.mute)
        media.addWidget(self.vol, 1)
        media.addWidget(self.vol_label)
        cv.addLayout(media)
        v.addWidget(c)

        quick = QHBoxLayout()
        self.q_dnd = SwitchRow("Do not disturb")
        self.q_dnd.toggled.connect(lambda on: self._choose("dnd", on))
        self.q_voice = SwitchRow("Speak out loud")
        self.q_voice.toggled.connect(lambda on: self._choose("voice_on", on))
        for w in (self.q_dnd, self.q_voice):
            c, cv = card()
            cv.setContentsMargins(10, 4, 8, 4)
            cv.addWidget(w)
            quick.addWidget(c, 1)
        v.addLayout(quick)
        v.addStretch(1)
        return sa

    # ---- Wellbeing ------------------------------------------------------------------------- #
    def _wellbeing(self):
        sa, v = page()
        c, cv = card("🌿  Breathe", "Two short breaths in through the nose, one long breath out. Breathe along with him.")
        row = QHBoxLayout()
        self.btn_breathe = button("Start breathing", "primary")
        self.btn_breathe.clicked.connect(self._breathe)
        self.breathe_min = QSpinBox(minimum=1, maximum=5, suffix=" min")
        self.breathe_min.valueChanged.connect(lambda val: self._choose("breathe_minutes", val))
        row.addWidget(self.btn_breathe, 1)
        row.addWidget(self.breathe_min)
        cv.addLayout(row)
        v.addWidget(c)

        c, cv = card("🎯  Focus session", "He puts his glasses on and works beside you. Notifications wait until the end.")
        self.focus_task = QComboBox()
        self.focus_task.setToolTip("The task this focus session is for")
        cv.addLayout(labelled("Working on", self.focus_task))
        row = QHBoxLayout()
        self.focus_min = QSpinBox(minimum=5, maximum=120, singleStep=5, suffix=" min")
        self.focus_min.valueChanged.connect(lambda val: self._choose("focus_minutes", val))
        self.btn_focus = button("Start focus", "primary")
        self.btn_focus.clicked.connect(self._focus)
        row.addWidget(self.focus_min)
        row.addWidget(self.btn_focus, 1)
        cv.addLayout(row)
        self.btn_done = button("✓  Mark the focus task done")
        self.btn_done.clicked.connect(self.r.finish_focus_task)
        cv.addWidget(self.btn_done)
        v.addWidget(c)

        c, cv = card("🙆  Breaks")
        self.well2 = QLabel()
        self.well2.setObjectName("muted")
        self.well2.setWordWrap(True)
        cv.addWidget(self.well2)
        self._switch(cv, "break_remind")
        self.break_every = QSpinBox(minimum=15, maximum=180, singleStep=5, suffix=" min")
        self.break_every.valueChanged.connect(lambda val: self._choose("break_every", val))
        cv.addLayout(labelled("Remind me every", self.break_every))
        v.addWidget(c)
        v.addStretch(1)
        return sa

    # ---- Fun ----------------------------------------------------------------------------- #
    def _fun(self):
        from . import rides
        r = self.r
        sa, v = page()
        c, cv = card("🧸  Look", "Dress him up part by part in 3D, or pick another friend.")
        studio = button("Open the Avatar Studio · 3D and voices", "primary")
        studio.clicked.connect(lambda: (self.close(), r.open_studio()))
        cv.addWidget(studio)
        row = QHBoxLayout()
        b_avatar = button("🎭  Avatars", tip="Who runs on your screen, and who comes round to dance")
        b_avatar.clicked.connect(lambda: (self.close(), r.choose_avatars()))
        self.b_jacket = button("👕  Jacket", tip="The colour of his jacket")
        self.b_jacket.clicked.connect(lambda: self._pick_color("color", "Jacket colour", True))
        self.b_cup = button("🥤  Cup", tip="The colour of his coffee cup")
        self.b_cup.clicked.connect(lambda: self._pick_color("cup_color", "Cup colour"))
        for b in (b_avatar, self.b_jacket, self.b_cup):
            row.addWidget(b, 1)
        cv.addLayout(row)
        v.addWidget(c)

        c, cv = card("🕺  Dance")
        row = QHBoxLayout()
        self.btn_dance = button("Dance showdown", "primary",
                                "His friend runs in and they take turns. It also starts by itself when a dance song plays.")
        self.btn_dance.clicked.connect(lambda: (r.toggle_dance(), self.close()))
        self.btn_touch = button("💞  Touch by Touch", tip="A solo, then the slow duet")
        self.btn_touch.clicked.connect(lambda: (r.toggle_dance("touch"), self.close()))
        row.addWidget(self.btn_dance, 1)
        row.addWidget(self.btn_touch, 1)
        cv.addLayout(row)
        self._switch(cv, "friend_on")
        v.addWidget(c)

        c, cv = card("🐉  Rides", "He crosses the screen on an animal. You can keep clicking and typing through it.")
        row = QHBoxLayout()
        self.ride_pick = QComboBox()
        self.ride_pick.addItem("🎲  Surprise me", "")
        for key, (label, _, _) in rides.RIDES.items():
            self.ride_pick.addItem(label, key)
        b_ride = button("Ride!", "primary")
        b_ride.clicked.connect(lambda: (r.start_ride(self.ride_pick.currentData() or ""), self.close()))
        row.addWidget(self.ride_pick, 1)
        row.addWidget(b_ride)
        cv.addLayout(row)
        v.addWidget(c)

        c, cv = card("📅  Today's adventure")
        self.adventure = QComboBox()
        self.adventure.addItem("Follow the weekday (auto)", "auto")
        for key in themes.ORDER:
            self.adventure.addItem(f"{themes.THEMES[key]['icon']}  {themes.THEMES[key]['label']}", key)
        self.adventure.currentIndexChanged.connect(lambda: self._choose("day_theme", self.adventure.currentData()))
        cv.addWidget(self.adventure)
        v.addWidget(c)
        v.addStretch(1)
        return sa

    # ---- Settings ------------------------------------------------------------------------- #
    def _settings(self):
        sa, v = page()
        c, cv = card("🐾  Pet")
        self.name = QLineEdit(maxLength=24)
        self.name.setPlaceholderText("Primo")
        self.name.setToolTip("His name. Press Enter to keep it.")
        self.name.editingFinished.connect(lambda: self._choose("pet_name", self.name.text().strip() or "Primo"))
        cv.addLayout(labelled("Name", self.name))
        self.height_ = QSpinBox(minimum=32, maximum=320, singleStep=8, suffix=" px")
        self.height_.setKeyboardTracking(False)
        self.height_.valueChanged.connect(lambda val: self._choose("pet_size", val))
        cv.addLayout(labelled("Size", self.height_))
        wrow = QHBoxLayout()
        self.width_ = QSlider(Qt.Horizontal, minimum=50, maximum=200, singleStep=5, pageStep=10)
        self.width_.setTracking(False)            # changes when you let go of the handle
        self.width_.setToolTip("Slimmer ← → wider (100 % = as drawn)")
        self.width_lbl = QLabel("100 %")
        self.width_lbl.setMinimumWidth(44)
        self.width_.sliderMoved.connect(lambda val: self.width_lbl.setText(f"{val} %"))
        self.width_.valueChanged.connect(lambda val: (self.width_lbl.setText(f"{val} %"), self._choose("pet_width", val)))
        wrow.addWidget(self.width_, 1)
        wrow.addWidget(self.width_lbl)
        w = QWidget()
        w.setLayout(wrow)
        wrow.setContentsMargins(0, 0, 0, 0)
        cv.addLayout(labelled("Width", w))
        self.seat = QComboBox()
        for key, label in workmode.SEAT_SIDES:
            self.seat.addItem(label, key)
        self.seat.setToolTip("Where he sits for calls, work modes, music, videos and reading")
        self.seat.currentIndexChanged.connect(lambda: self._choose("seat_side", self.seat.currentData()))
        cv.addLayout(labelled("He sits", self.seat))
        for key in ("show_pet", "pet_roam", "pet_ghost"):
            self._switch(cv, key)
        v.addWidget(c)

        c, cv = card("🎧  Joining in")
        self.mode = QComboBox()
        for key, label in MODES:
            self.mode.addItem(label, key)
        self.mode.currentIndexChanged.connect(lambda: self._choose("activity_mode", self.mode.currentData(), poll=True))
        cv.addLayout(labelled("When something plays", self.mode))
        for key in ("activity_react", "activity_caption", "meeting_look", "work_on"):
            self._switch(cv, key)
        v.addWidget(c)

        c, cv = card("💬  Talking and notifications")
        self.font = QSpinBox(minimum=10, maximum=18, suffix=" px")
        self.font.valueChanged.connect(lambda val: self._choose("bubble_font", val))
        cv.addLayout(labelled("Bubble text", self.font))
        for key in ("voice_on", "dnd", "focus_quiet_system"):
            self._switch(cv, key)
        v.addWidget(c)

        c, cv = card("🎨  Look and speed")
        self.ui_theme = QComboBox()
        for key in uitheme.ORDER:
            self.ui_theme.addItem(uitheme.THEMES[key]["label"], key)
        self.ui_theme.currentIndexChanged.connect(lambda: self._choose("ui_theme", self.ui_theme.currentData()))
        cv.addLayout(labelled("App theme", self.ui_theme))
        self.speed = QComboBox()
        for key, label in SPEEDS:
            self.speed.addItem(label, key)
        self.speed.currentIndexChanged.connect(lambda: self._choose("speed_source", self.speed.currentData()))
        cv.addLayout(labelled("Speed follows", self.speed))
        v.addWidget(c)
        v.addStretch(1)
        return sa

    def _switch(self, layout, key: str):
        title, hint = TOGGLES[key]
        row = SwitchRow(title, hint)
        row.toggled.connect(lambda on, k=key: self._choose(k, on))
        self.switches.setdefault(key, [])
        self.switches[key].append(row)
        layout.addWidget(row)

    # ------------------------------------------------------------------ #
    def _pick_color(self, key: str, title: str, jacket: bool = False):
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
        for row in self.switches.get(key, []):     # the same switch can be on two tabs
            if row.isChecked() != bool(value):
                row.switch.blockSignals(True)
                row.setChecked(bool(value))
                row.switch.blockSignals(False)
                row.switch.update()
        for row, k in ((self.q_dnd, "dnd"), (self.q_voice, "voice_on")):
            if k == key and row.isChecked() != bool(value):
                row.switch.blockSignals(True)
                row.setChecked(bool(value))
                row.switch.blockSignals(False)
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
        status = r.wellbeing_status()
        self.well.setText(status)
        self.well2.setText(status)
        self.btn_breathe.setText("■  Stop breathing" if r.breathe_end else "Start breathing")
        self.t_breathe.set("■" if r.breathe_end else "🌿", "Stop" if r.breathe_end else "Breathe")
        self.btn_focus.setText("■  Stop focus" if r.focus_end else "Start focus")
        self.t_focus.set("■" if r.focus_end else "🎯", "Stop focus" if r.focus_end else "Focus")
        self.t_dance.set(None, "Stop dance" if r.dance else "Dance")
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

    def _sync_avatar(self):
        fs = getattr(self.r, "frames", None)
        if fs and fs.run:
            pm = fs.run[0].scaled(46, 46, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.avatar.setPixmap(pm)
        else:
            self.avatar.setText("🐾")

    def sync(self):
        """Load the current settings and state into the widgets."""
        s, r = self.r.store.settings, self.r
        self._loading = True
        name = str(s.get("pet_name") or "Primo")
        self.title.setText(name)
        self.setWindowTitle(f"{name} controls")
        self._sync_avatar()
        act = r.activity
        if r.work:
            now = f"💻 {r.work.name} · {r.work.app}"
        elif act:
            now = f"{r.ACT_ICON.get(act.kind, '')} {act.label or act.kind.capitalize()}"
        else:
            now = ""
        self.now.setText(self.now.fontMetrics().elidedText(now or "Here with you 🐾", Qt.ElideRight, 300))
        self.now.setToolTip(now)
        self.playing.setText(now if act else "Nothing playing right now.")
        unread = r.store.unread()
        self.t_notifs.set("🔔", f"Notifications ({unread})" if unread else "Notifications")
        self.mode.setCurrentIndex(max(0, self.mode.findData(s.get("activity_mode", "auto"))))
        self.speed.setCurrentIndex(max(0, self.speed.findData(s.get("speed_source", "mix"))))
        self.adventure.setCurrentIndex(max(0, self.adventure.findData(s.get("day_theme", "auto"))))
        self.seat.setCurrentIndex(max(0, self.seat.findData(s.get("seat_side", "right"))))
        self.name.setText(name)
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
        for key, rows in self.switches.items():
            for row in rows:
                row.setChecked(bool(s.get(key, key not in TOGGLE_DEFAULT_OFF)))
        self.q_dnd.setChecked(bool(s.get("dnd", False)))
        self.q_voice.setChecked(bool(s.get("voice_on", False)))
        self._loading = False
        self.sync_volume()

    def open_near(self, pos: QPoint):
        """Show next to where the pet was clicked, fully on that screen (smaller on a small screen)."""
        self.sync()
        screen = QGuiApplication.screenAt(pos) or QGuiApplication.primaryScreen()
        g = screen.availableGeometry()
        self.setFixedSize(min(self.WIDTH, g.width() - 16), min(self.HEIGHT, g.height() - 16))
        x = min(max(pos.x() - self.width() - 12, g.left() + 8), g.right() - self.width() - 8)
        y = min(max(pos.y() - self.height() - 12, g.top() + 8), g.bottom() - self.height() - 8)
        self.move(x, y)
        self.show()
        self.raise_()
        self.activateWindow()
