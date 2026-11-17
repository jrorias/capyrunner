"""Primo's control panel: a small ordinary window (with a Close button) that opens when you right-click the pet.

It replaces the pop-up menu on the pet, which could get stuck open on Wayland compositors: a pop-up
only closes when it sees a click elsewhere, and under XWayland it never sees clicks on other apps.
"""
from __future__ import annotations

from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QGuiApplication, QKeySequence, QShortcut
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFrame, QGridLayout, QHBoxLayout, QLabel, QPushButton,
                               QSlider, QSpinBox, QVBoxLayout, QWidget)

from . import activity

MODES = (("auto", "Decides by himself (auto)"), ("listen", "🎧 Listens with headphones"),
         ("watch", "📱 Watches cosy, on his phone"), ("movie", "🍿 Watches with popcorn"),
         ("study", "📝 Takes notes (tutorial / podcast)"), ("read", "📖 Reads a book"))
SPEEDS = (("mix", "Tasks + notifications + CPU"), ("tasks", "Tasks & notifications only"), ("cpu", "CPU only"))
TOGGLES = (("show_pet", "Show floating pet"), ("pet_roam", "Run around the screen"),
           ("activity_react", "Join in with music, videos and reading"),
           ("activity_caption", "Show the small “now playing” line"),
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
        grid.addWidget(QLabel("When something plays"), 0, 0)
        grid.addWidget(self.mode, 0, 1)
        grid.addWidget(QLabel("Speed follows"), 1, 0)
        grid.addWidget(self.speed, 1, 1)
        grid.addWidget(QLabel("Bubble text size"), 2, 0)
        grid.addWidget(self.font, 2, 1, Qt.AlignLeft)
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
    def _choose(self, key: str, value, poll: bool = False):
        if self._loading or self.r.store.settings.get(key) == value:
            return
        self.r._set(key, value)
        if poll:
            self.r._poll_activity()

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
        act = r.activity
        if act:
            self.now.setText(f"{r.ACT_ICON.get(act.kind, '')} {act.label or act.kind.capitalize()}")
        else:
            self.now.setText("Nothing playing right now.")
        unread = r.store.unread()
        self.btn_notifs.setText(f"Notifications ({unread})" if unread else "Notifications")
        self.mode.setCurrentIndex(max(0, self.mode.findData(s.get("activity_mode", "auto"))))
        self.speed.setCurrentIndex(max(0, self.speed.findData(s.get("speed_source", "mix"))))
        self.font.setValue(int(s.get("bubble_font", 13)))
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
