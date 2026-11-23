"""The avatar picker: choose who runs on your screen and who comes round to dance, and dress them up."""
from __future__ import annotations

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon
from PySide6.QtWidgets import (QButtonGroup, QColorDialog, QComboBox, QDialog, QDialogButtonBox, QFormLayout,
                               QGridLayout, QGroupBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QTabWidget,
                               QToolButton, QVBoxLayout, QWidget, QCheckBox)

from . import avatars
from .characters import avatar_preview


class _Side(QWidget):
    """One avatar (the one on screen, or the friend): gallery of ready-made avatars + editors + live preview."""

    def __init__(self, av: dict, intro: str, parent=None):
        super().__init__(parent)
        self._loading = True
        self.av = dict(av)
        self.frames: list = []
        self.i = 0
        v = QVBoxLayout(self)
        lab = QLabel(intro)
        lab.setWordWrap(True)
        v.addWidget(lab)

        gallery = QGridLayout()
        self.group = QButtonGroup(self)
        self.group.setExclusive(True)
        for i, (key, p) in enumerate(avatars.PRESETS.items()):
            b = QToolButton()
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setIcon(QIcon(avatar_preview(avatars.preset(key), n=1)[0]))
            b.setIconSize(QSize(72, 72))
            b.setText(p["name"].split()[0])
            b.setToolTip(p["about"])
            b.setMinimumWidth(92)
            b.clicked.connect(lambda _=False, k=key: self._choose(k))
            self.group.addButton(b)
            b.setProperty("key", key)
            b.setChecked(key == self.av.get("preset"))
            gallery.addWidget(b, i // 3, i % 3)
        v.addLayout(gallery)

        row = QHBoxLayout()
        form = QFormLayout()
        self.name = QLineEdit(self.av["name"])
        self.name.textChanged.connect(lambda t: self._set("name", t.strip()))
        form.addRow("Name", self.name)
        self.fur_btn = QPushButton()
        self.fur_btn.clicked.connect(lambda: self._pick("fur", "Fur colour"))
        form.addRow("Fur", self.fur_btn)
        self.hoodie_btn = QPushButton()
        self.hoodie_btn.clicked.connect(lambda: self._pick("hoodie", "Jacket colour"))
        form.addRow("Jacket", self.hoodie_btn)
        self.acc = QComboBox()
        for k, label in avatars.HEADWEAR.items():
            self.acc.addItem(label, k)
        self.acc.currentIndexChanged.connect(lambda _: self._set("acc", self.acc.currentData()))
        form.addRow("Headwear", self.acc)
        self.acc_btn = QPushButton()
        self.acc_btn.clicked.connect(lambda: self._pick("acc_color", "Headwear colour"))
        form.addRow("Headwear colour", self.acc_btn)
        row.addLayout(form, 1)
        self.preview = QLabel()
        self.preview.setFixedSize(150, 150)
        self.preview.setAlignment(Qt.AlignCenter)
        self.preview.setStyleSheet("background: palette(base); border-radius: 12px;")
        row.addWidget(self.preview)
        v.addLayout(row)
        v.addStretch(1)
        self._fill()
        self.timer = QTimer(self, interval=90, timeout=self._tick)
        self.timer.start()

    def _choose(self, key: str):
        self.av = avatars.preset(key)
        self._fill()

    def _set(self, field: str, value):
        if self._loading or self.av.get(field) == value:
            return
        self.av[field] = value
        if field != "name":
            self.av["preset"] = "custom"               # changed by hand: no longer one of the ready-made ones
            for b in self.group.buttons():
                b.setChecked(False)
            self._redraw()

    def _pick(self, field: str, title: str):
        c = QColorDialog.getColor(QColor(self.av[field]), self, title)
        if c.isValid():
            self._set(field, c.name())
            self._paint()

    def _fill(self):
        self._loading = True
        self.name.setText(self.av["name"])
        self.acc.setCurrentIndex(max(0, self.acc.findData(self.av.get("acc", ""))))
        for b in self.group.buttons():
            b.setChecked(b.property("key") == self.av.get("preset"))
        self._loading = False
        self._paint()
        self._redraw()

    def _paint(self):
        for btn, field in ((self.fur_btn, "fur"), (self.hoodie_btn, "hoodie"), (self.acc_btn, "acc_color")):
            c = self.av[field]
            btn.setText(c)
            btn.setStyleSheet(f"background:{c}; color:{'#000' if QColor(c).lightness() > 128 else '#fff'};")
        self.acc_btn.setEnabled(bool(self.av.get("acc")))

    def _redraw(self):
        self.frames = [f.scaled(140, 140, Qt.KeepAspectRatio, Qt.SmoothTransformation) for f in avatar_preview(self.av)]
        self.i = 0

    def _tick(self):
        if self.frames:
            self.i = (self.i + 1) % len(self.frames)
            self.preview.setPixmap(self.frames[self.i])


class AvatarDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Choose avatars")
        self.setMinimumWidth(560)
        v = QVBoxLayout(self)
        tabs = QTabWidget()
        self.me = _Side(avatars.get(settings, "main"),
                        "Who runs on your screen. Pick one, then change the name, colours and headwear as you like. "
                        "This avatar also rides the dragon, the whale and the others.")
        self.friend = _Side(avatars.get(settings, "friend"),
                            "Who comes round for the dance showdowns (and rides along behind, if you like).")
        tabs.addTab(self.me, "🎭  On my screen")
        tabs.addTab(self.friend, "🕺  Dance friend")
        v.addWidget(tabs)
        self.ride_friend = QCheckBox("The friend rides along on the animals too",
                                     checked=bool(settings.get("ride_friend", True)))
        v.addWidget(self.ride_friend)
        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

    def result_into(self, settings: dict) -> None:
        avatars.put(settings, "main", self.me.av)
        avatars.put(settings, "friend", self.friend.av)
        settings["ride_friend"] = self.ride_friend.isChecked()
