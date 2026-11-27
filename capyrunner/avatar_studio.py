"""Avatar Studio: dress Primo and Jeo in 3D, part by part, and give each of them a voice.

Left: the avatar in 3D. Drag to turn him round, scroll to zoom, pick what he does (stand, run, wave, talk…).
Right: tabs for the ready-made looks, the body, the clothes, the extras and the voice.
"""
from __future__ import annotations

import math
import random
import time

from PySide6.QtCore import QPointF, QSize, Qt, QTimer
from PySide6.QtGui import QColor, QIcon, QPainter, QRadialGradient
from PySide6.QtWidgets import (QButtonGroup, QCheckBox, QColorDialog, QComboBox, QDialog, QFormLayout, QFrame,
                               QGridLayout, QHBoxLayout, QLabel, QLineEdit, QPushButton, QScrollArea, QSlider,
                               QTabWidget, QToolButton, QVBoxLayout, QWidget)

from . import avatars, model3d, voice

def _preset_info(key: str) -> tuple[str, str]:
    if key in model3d.PRESET_INFO:
        return model3d.PRESET_INFO[key]
    p = avatars.PRESETS.get(key, {})
    return p.get("name", key).split()[0], p.get("about", "")


STYLE_LOOK = {"cartoon": "primo", "real": "wild", "hero": "lapulapu"}     # what each style card shows

QSS = """
QDialog#studio { background: palette(window); }
QFrame#card { background: palette(base); border: 1px solid rgba(127,127,127,50); border-radius: 14px; }
QLabel#h { font-size: 13px; font-weight: 700; }
QLabel#muted { color: rgba(127,127,127,230); font-size: 12px; }
QToolButton#look { background: palette(base); border: 1px solid rgba(127,127,127,50); border-radius: 12px;
                   padding: 4px; font-weight: 600; }
QToolButton#look:hover { border: 1px solid palette(highlight); }
QToolButton#look:checked { border: 2px solid palette(highlight); background: rgba(127,127,127,30); }
QPushButton#chip { background: rgba(127,127,127,30); border: none; border-radius: 13px; padding: 4px 9px; }
QPushButton#chip:hover { background: rgba(127,127,127,60); }
QPushButton#chip:checked { background: palette(highlight); color: palette(highlighted-text); }
QPushButton#primary { background: palette(highlight); color: palette(highlighted-text); border: none;
                      border-radius: 10px; padding: 7px 16px; font-weight: 600; }
QPushButton#soft { background: rgba(127,127,127,30); border: none; border-radius: 10px; padding: 6px 12px; }
QPushButton#soft:hover { background: rgba(127,127,127,60); }
QTabWidget::pane { border: none; }
QTabBar::tab { background: transparent; border: none; padding: 6px 10px; margin-right: 2px; border-radius: 12px; }
QTabBar::tab:selected { background: palette(highlight); color: palette(highlighted-text); }
QTabBar::tab:hover:!selected { background: rgba(127,127,127,45); }
"""


current_look = model3d.current_look


class Model3DView(QWidget):
    """The live 3D preview: drag to turn, scroll to zoom."""
    MODES = {"idle": "Stand", "run": "Run", "wave": "Wave", "talk": "Talk", "jump": "Jump", "sleep": "Nap"}

    def __init__(self, look: dict, parent=None):
        super().__init__(parent)
        self.look = dict(look)
        self.mode = "idle"
        self.yaw, self.pitch, self.zoom = -0.8, 0.14, 1.0
        self.spin = False
        self.talking_until = 0.0
        self.mood = None              # try a mood in the preview without changing the look
        self._drag = None
        self._t0 = time.time()
        self._pm = None
        self._dirty = True
        self.setMinimumSize(280, 300)
        self.setCursor(Qt.OpenHandCursor)
        self.setToolTip("Drag to turn · scroll to zoom")
        self.timer = QTimer(self, interval=150, timeout=self._tick)
        self.timer.start()

    def set_look(self, look: dict):
        self.look = dict(look)
        self._dirty = True
        self.update()

    def set_mode(self, mode: str):
        self.mode = mode
        self._dirty = True

    def _tick(self):
        if not self.isVisible():
            return
        if self.spin and self._drag is None:
            self.yaw += 0.12
        if self.spin or self.mode != "idle" or time.time() < self.talking_until or self._dirty:
            self._dirty = True
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        r = self.rect()
        g = QRadialGradient(QPointF(r.center().x(), r.height() * 0.62), r.width() * 0.75)
        g.setColorAt(0, QColor("#4A5568"))
        g.setColorAt(1, QColor("#1F2430"))
        p.fillRect(r, g)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(0, 0, 0, 70))
        size = min(r.width(), r.height()) - 10
        cx, base = r.center().x(), r.top() + 5 + size * 0.96
        p.drawEllipse(QPointF(cx, base + 2), size * 0.2 * self.zoom, size * 0.045 * self.zoom)  # floor shadow
        if self._dirty or self._pm is None:
            t = (time.time() - self._t0) * 5.0
            mode, k, mouth = self.mode, 0.0, None
            if time.time() < self.talking_until:
                mode, mouth = ("run" if self.mode == "run" else "talk"), random.choice((0.15, 0.5, 0.8, 1.0))
                k = mouth
            elif mode == "jump":
                k = (t / 6) % 1.0
            elif mode == "talk":
                k = abs(math.sin(t * 1.7))
            self._pm = model3d.render(self.look, mode, t, k, size, yaw=self.yaw, pitch=self.pitch, zoom=self.zoom,
                                      supersample=2, mouth=mouth, mood=self.mood)
            self._dirty = False
        p.drawPixmap(int(cx - self._pm.width() / 2), r.top() + 5, self._pm)
        p.setPen(QColor(255, 255, 255, 120))
        p.drawText(r.adjusted(8, 0, -8, -6), Qt.AlignBottom | Qt.AlignLeft, "↻ drag to turn · scroll to zoom")

    def mousePressEvent(self, e):
        self._drag = (e.position(), self.yaw, self.pitch)
        self.setCursor(Qt.ClosedHandCursor)

    def mouseMoveEvent(self, e):
        if self._drag is None:
            return
        start, yaw, pitch = self._drag
        d = e.position() - start
        self.yaw = yaw + d.x() * 0.012
        self.pitch = max(-0.6, min(0.9, pitch + d.y() * 0.008))
        self._dirty = True
        self.update()

    def mouseReleaseEvent(self, _):
        self._drag = None
        self.setCursor(Qt.OpenHandCursor)

    def wheelEvent(self, e):
        self.zoom = max(0.6, min(1.8, self.zoom * (1.1 if e.angleDelta().y() > 0 else 1 / 1.1)))
        self._dirty = True
        self.update()


def _swatch(btn: QPushButton, color: str):
    btn.setText(color.upper())
    fg = "#000000" if QColor(color).lightnessF() > 0.55 else "#FFFFFF"
    btn.setStyleSheet(f"QPushButton {{ background: {color}; color: {fg}; border: 1px solid #555; "
                      f"border-radius: 4px; padding: 3px 8px; }}")


class _Side(QWidget):
    """One character: preview on the left, part editors on the right."""

    def __init__(self, who: str, settings: dict, engine: voice.Voice | None, parent=None):
        super().__init__(parent)
        self.who = who
        self.engine = engine
        self.look = current_look(settings, who)
        self.vcfg = voice.settings_for(settings, who)
        key = "pet_name" if who == "main" else "friend_name"
        self.name_key = key
        self.name0 = str(settings.get(key) or ("Primo" if who == "main" else "Jeo OngBack"))
        self._widgets: dict = {}

        row = QHBoxLayout(self)
        left = QVBoxLayout()
        self.view = Model3DView(self.look)
        left.addWidget(self.view, 1)
        ctl = QHBoxLayout()
        self.mode = QComboBox()
        for k, label in Model3DView.MODES.items():
            self.mode.addItem(label, k)
        self.mode.currentIndexChanged.connect(lambda: self.view.set_mode(self.mode.currentData()))
        spin = QCheckBox("Turntable")
        spin.toggled.connect(lambda on: setattr(self.view, "spin", on))
        front = QPushButton("Front")
        front.clicked.connect(lambda: self._turn(-1.35))
        side = QPushButton("Side")
        side.clicked.connect(lambda: self._turn(-0.8))
        for w in (front, side):
            w.setObjectName("soft")
        for w in (self.mode, spin, front, side):
            ctl.addWidget(w)
        left.addLayout(ctl)
        # moods: click one to see (and keep) it
        moods = QGridLayout()
        moods.setSpacing(4)
        self.mood_group = QButtonGroup(self)
        for i, (key, label) in enumerate(model3d.MOODS.items()):
            b = QPushButton(label)
            b.setObjectName("chip")
            b.setCheckable(True)
            b.setCursor(Qt.PointingHandCursor)
            b.setToolTip("His mood: face, ears and a little effect")
            b.clicked.connect(lambda _=False, k=key: self._set("mood", k))
            b.setProperty("mood", key)
            self.mood_group.addButton(b)
            moods.addWidget(b, i // 3, i % 3)
        left.addLayout(moods)
        row.addLayout(left, 5)

        tabs = QTabWidget()
        self.tabs = tabs
        tabs.addTab(self._looks_tab(), "✨ Looks")
        tabs.addTab(self._body_tab(), "🐾 Body")
        tabs.addTab(self._clothes_tab(), "👕 Clothes")
        tabs.addTab(self._extras_tab(), "🎩 Extras")
        tabs.addTab(self._voice_tab(), "🎙 Voice")
        row.addWidget(tabs, 6)
        self._load_widgets()

    def _turn(self, yaw):
        self.view.yaw = yaw
        self.view._dirty = True
        self.view.update()

    # ---- tabs --------------------------------------------------------------- #
    def _looks_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        v.setSpacing(10)
        form = QFormLayout()
        self.name = QLineEdit(self.name0)
        form.addRow("Name", self.name)
        v.addLayout(form)
        h = QLabel("Style")
        h.setObjectName("h")
        v.addWidget(h)
        styles = QHBoxLayout()
        self.style_group = QButtonGroup(self)
        for key, label in model3d.BODIES.items():
            b = QToolButton()
            b.setObjectName("look")
            b.setCheckable(True)
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            b.setIcon(QIcon(model3d.render(model3d.complete(model3d.PRESETS[STYLE_LOOK[key]]), "idle", 0, 0, 84)))
            b.setIconSize(QSize(76, 76))
            b.setText(label.split(" (")[0])
            b.setToolTip(label)
            b.setProperty("body", key)
            b.setMinimumWidth(96)
            b.clicked.connect(lambda _=False, k=key: self._style(k))
            self.style_group.addButton(b)
            styles.addWidget(b, 1)
        v.addLayout(styles)
        h = QLabel("Ready-made characters")
        h.setObjectName("h")
        v.addWidget(h)
        grid = QGridLayout()
        grid.setSpacing(6)
        for i, key in enumerate(model3d.PRESETS):
            b = QToolButton()
            b.setObjectName("look")
            b.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
            look = model3d.complete(model3d.PRESETS[key])
            b.setIcon(QIcon(model3d.render(look, "idle", 0.0, 0.0, 64)))
            b.setIconSize(QSize(56, 56))
            name, about = _preset_info(key)
            b.setText(name)
            b.setToolTip(about)
            b.setMinimumWidth(78)
            b.clicked.connect(lambda _=False, k=key: self._preset(k))
            grid.addWidget(b, i // 4, i % 4)
        v.addLayout(grid)
        rnd = QPushButton("🎲  Surprise me")
        rnd.setObjectName("soft")
        rnd.clicked.connect(self._random)
        v.addWidget(rnd)
        v.addStretch(1)
        sa = QScrollArea()
        sa.setWidgetResizable(True)
        sa.setFrameShape(QFrame.NoFrame)
        sa.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        sa.setWidget(w)
        return sa

    def _style(self, body: str):
        """Change the body style, keeping the colours and extras that still make sense."""
        if body == self.look.get("body"):
            return
        keep = {k: self.look[k] for k in ("hat", "hat_color", "glasses", "glasses_color", "mood")}
        base = {"cartoon": "primo", "real": "wild", "hero": "lapulapu"}[body]
        self.look = model3d.complete(model3d.PRESETS[base])
        if body != "hero":
            self.look.update(keep)
        self._load_widgets()

    def _body_tab(self):
        w = QWidget()
        f = QFormLayout(w)
        f.addRow("Mood", self._combo("mood", model3d.MOODS))
        f.addRow("Fur", self._color("fur"))
        f.addRow("Snout", self._color("muzzle"))
        f.addRow("Eyes", self._combo("eyes", model3d.EYES))
        f.addRow("Eye colour", self._color("eye_color"))
        f.addRow("", self._check("blush", "Rosy cheeks"))
        f.addRow("Head size", self._slider("head", 0.8, 1.3))
        f.addRow("Chubby", self._slider("chubby", 0.8, 1.3))
        f.addRow("Ears", self._slider("ears", 0.6, 1.6))
        f.addRow("Legs", self._slider("height", 0.8, 1.3))
        return w

    def _clothes_tab(self):
        w = QWidget()
        f = QFormLayout(w)
        self.clothes_note = QLabel()
        self.clothes_note.setObjectName("muted")
        self.clothes_note.setWordWrap(True)
        f.addRow(self.clothes_note)
        f.addRow("Costume", self._combo("costume", model3d.COSTUMES))
        f.addRow("Costume colour", self._color("costume_color"))
        f.addRow("Weapon", self._combo("weapon", model3d.WEAPONS))
        f.addRow("Top", self._combo("top", model3d.TOPS))
        f.addRow("Top colour", self._color("top_color"))
        f.addRow("Strings", self._color("top_trim"))
        f.addRow("Bottoms", self._combo("bottom", model3d.BOTTOMS))
        f.addRow("Bottoms colour", self._color("bottom_color"))
        f.addRow("Shoes", self._combo("shoes", model3d.SHOES))
        f.addRow("Shoes colour", self._color("shoes_color"))
        return w

    def _extras_tab(self):
        w = QWidget()
        f = QFormLayout(w)
        f.addRow("Hat", self._combo("hat", model3d.HATS))
        f.addRow("Hat colour", self._color("hat_color"))
        f.addRow("Glasses", self._combo("glasses", model3d.GLASSES))
        f.addRow("Frame colour", self._color("glasses_color"))
        f.addRow("Neck", self._combo("neck", model3d.NECK))
        f.addRow("Neck colour", self._color("neck_color"))
        f.addRow("On the back", self._combo("extra", model3d.EXTRAS))
        f.addRow("Back colour", self._color("extra_color"))
        return w

    def _voice_tab(self):
        w = QWidget()
        v = QVBoxLayout(w)
        f = QFormLayout()
        self.voice_box = QComboBox()
        self._fill_voices()
        self.voice_box.currentIndexChanged.connect(self._voice_changed)
        f.addRow("Voice", self.voice_box)
        self.pitch = QSlider(Qt.Horizontal, minimum=80, maximum=150)
        self.pitch.setValue(int(round(float(self.vcfg["pitch"]) * 100)))
        self.pitch_lab = QLabel()
        self.pitch.valueChanged.connect(self._voice_sliders)
        ph = QHBoxLayout()
        ph.addWidget(self.pitch, 1)
        ph.addWidget(self.pitch_lab)
        f.addRow("Pitch", ph)
        self.speed = QSlider(Qt.Horizontal, minimum=70, maximum=150)
        self.speed.setValue(int(round(float(self.vcfg["speed"]) * 100)))
        self.speed_lab = QLabel()
        self.speed.valueChanged.connect(self._voice_sliders)
        sh = QHBoxLayout()
        sh.addWidget(self.speed, 1)
        sh.addWidget(self.speed_lab)
        f.addRow("Speed", sh)
        v.addLayout(f)
        btns = QHBoxLayout()
        self.dl_btn = QPushButton("⬇  Download this voice")
        self.dl_btn.clicked.connect(self._download)
        self.test_btn = QPushButton("▶  Test voice")
        self.test_btn.clicked.connect(self._test)
        btns.addWidget(self.dl_btn)
        btns.addWidget(self.test_btn)
        v.addLayout(btns)
        self.voice_note = QLabel()
        self.voice_note.setWordWrap(True)
        v.addWidget(self.voice_note)
        hint = QLabel("Natural voices run on this computer: nothing is sent anywhere. Each one is a ~60 MB download, "
                      "once. Higher pitch makes a cuter, younger voice.")
        hint.setWordWrap(True)
        hint.setStyleSheet("color: gray;")
        v.addWidget(hint)
        v.addStretch(1)
        self._voice_sliders()
        self._voice_changed()
        if self.engine is not None:
            self.engine.downloaded.connect(lambda *_: (self._fill_voices(), self._voice_changed()))
        return w

    # ---- voice ------------------------------------------------------------------ #
    def _fill_voices(self):
        cur = self.voice_box.currentData() or self.vcfg["voice"]
        self.voice_box.blockSignals(True)
        self.voice_box.clear()
        for k, label in voice.VOICES.items():
            self.voice_box.addItem(("✓ " if voice.has_voice(k) else "⬇ ") + label, k)
        self.voice_box.addItem("🖥 The computer's own voice (more robotic)", voice.SYSTEM)
        i = self.voice_box.findData(cur)
        self.voice_box.setCurrentIndex(max(0, i))
        self.voice_box.blockSignals(False)

    def _voice_sliders(self):
        self.pitch_lab.setText(f"{self.pitch.value() / 100:.2f}×")
        self.speed_lab.setText(f"{self.speed.value() / 100:.2f}×")

    def _voice_changed(self):
        k = self.voice_box.currentData()
        have = voice.has_voice(k)
        self.dl_btn.setVisible(not have)
        if not voice.piper_ok() and k != voice.SYSTEM:
            self.voice_note.setText("The natural voice engine is not installed yet (button at the bottom). "
                                    "Until then the computer's own voice is used.")
        elif not have:
            self.voice_note.setText("Download this voice to hear it.")
        else:
            self.voice_note.setText("")

    def _download(self):
        if self.engine is not None:
            self.dl_btn.setEnabled(False)
            self.engine.download(self.voice_box.currentData())
            self.engine.downloaded.connect(lambda *_: self.dl_btn.setEnabled(True))

    def voice_cfg(self) -> dict:
        return {"voice": self.voice_box.currentData(), "pitch": self.pitch.value() / 100,
                "speed": self.speed.value() / 100}

    def _test(self):
        if self.engine is None:
            return
        self.engine.test(self.who, self.voice_cfg(), self.name.text().strip() or self.name0)
        self._watch_talk()

    def _watch_talk(self):
        """Move the preview's mouth while the test line plays."""
        self._talk_wait = time.time() + 6.0          # the first line takes a moment to load the voice
        QTimer.singleShot(150, self._poll_talk)

    def _poll_talk(self):
        talking = self.engine.speaking_who == self.who
        if talking:
            self.view.talking_until = time.time() + 0.3
            self._talk_wait = 0.0
        if talking or time.time() < self._talk_wait:
            QTimer.singleShot(150, self._poll_talk)

    # ---- part editors --------------------------------------------------------------- #
    def _set(self, key, value):
        self.look[key] = value
        if key == "mood":
            w = self._widgets.get("mood")
            if w:
                w[1].blockSignals(True)
                w[1].setCurrentIndex(max(0, w[1].findData(value)))
                w[1].blockSignals(False)
            self._sync_style()
        self.view.set_look(self.look)

    def _color(self, key):
        b = QPushButton()
        b.clicked.connect(lambda: self._pick(key, b))
        self._widgets[key] = ("color", b)
        return b

    def _pick(self, key, b):
        c = QColorDialog.getColor(QColor(self.look[key]), self, "Pick a colour")
        if c.isValid():
            self._set(key, c.name())
            _swatch(b, c.name())

    def _combo(self, key, options: dict):
        c = QComboBox()
        for k, label in options.items():
            c.addItem(label, k)
        c.currentIndexChanged.connect(lambda: self._set(key, c.currentData()))
        self._widgets[key] = ("combo", c)
        return c

    def _check(self, key, label):
        c = QCheckBox(label)
        c.toggled.connect(lambda on: self._set(key, on))
        self._widgets[key] = ("check", c)
        return c

    def _slider(self, key, lo, hi):
        s = QSlider(Qt.Horizontal, minimum=int(lo * 100), maximum=int(hi * 100))
        s.valueChanged.connect(lambda v: self._set(key, v / 100))
        self._widgets[key] = ("slider", s)
        return s

    def _load_widgets(self):
        for key, (kind, w) in self._widgets.items():
            w.blockSignals(True)
            val = self.look[key]
            if kind == "color":
                _swatch(w, val)
            elif kind == "combo":
                w.setCurrentIndex(max(0, w.findData(val)))
            elif kind == "check":
                w.setChecked(bool(val))
            elif kind == "slider":
                w.setValue(int(round(float(val) * 100)))
            w.blockSignals(False)
        self._sync_style()
        self.view.set_look(self.look)

    def _row_visible(self, key: str, on: bool):
        w = self._widgets.get(key, (None, None))[1]
        form = w.parentWidget().layout() if w is not None and w.parentWidget() else None
        if isinstance(form, QFormLayout):
            form.setRowVisible(w, on)

    def _sync_style(self):
        body = self.look.get("body", "cartoon")
        for b in self.style_group.buttons():
            b.setChecked(b.property("body") == body)
        for b in self.mood_group.buttons():
            b.setChecked(b.property("mood") == self.look.get("mood"))
        cartoon = body == "cartoon"
        # show only the parts this style has (QFormLayout hides the label with the field)
        for key in ("top", "top_color", "top_trim", "bottom", "bottom_color", "shoes", "shoes_color", "neck",
                    "neck_color", "extra", "extra_color", "head", "chubby", "ears", "height", "eyes", "eye_color"):
            self._row_visible(key, cartoon)
        for key in ("costume", "costume_color"):
            self._row_visible(key, not cartoon)
        self._row_visible("weapon", body == "hero")
        self.clothes_note.setText(
            "Cartoon style: dress him in tops, bottoms and shoes." if cartoon else
            "Real capybaras wear a costume instead: Lapu-Lapu, samurai or shogun armour, or a woven wrap "
            "(weapons need the standing style).")

    def _preset(self, key):
        self.look = model3d.complete(model3d.PRESETS[key])
        self._load_widgets()

    def _random(self):
        rc = lambda: QColor.fromHsv(random.randrange(360), random.randint(90, 230), random.randint(90, 240)).name()  # noqa: E731
        body = self.look.get("body", "cartoon")
        self.look["mood"] = random.choice(list(model3d.MOODS))
        if body != "cartoon":                     # real capybaras: a costume, a hat, a mood
            fur = random.choice(("#9A5A2F", "#8C5530", "#A8683A", "#7A4A2A", "#6B4A33"))
            self.look.update({"fur": fur, "muzzle": QColor(fur).darker(118).name(),
                              "hat": random.choice(("", "", "flower", "tophat", "crown", "party", "beanie")),
                              "hat_color": rc(), "glasses": random.choice(("", "", "round", "shades"))})
            if body == "hero":
                self.look.update({"costume": random.choice(("lapulapu", "samurai", "shogun", "wrap")),
                                  "costume_color": rc(), "weapon": random.choice(("", "kampilan", "katana"))})
            self._load_widgets()
            return
        fur = random.choice(("#C98A50", "#E3B273", "#D9A27A", "#7A4E2D", "#A39A93", "#E0B060", "#B5764A"))
        self.look.update({
            "fur": fur, "muzzle": QColor(fur).darker(112).name(),
            "top": random.choice(list(model3d.TOPS)), "top_color": rc(),
            "bottom": random.choice(list(model3d.BOTTOMS)), "bottom_color": rc(),
            "shoes": random.choice(list(model3d.SHOES)), "shoes_color": rc(),
            "hat": random.choice(list(model3d.HATS)), "hat_color": rc(),
            "glasses": random.choice(("", "", "round", "shades", "star")), "neck": random.choice(list(model3d.NECK)),
            "neck_color": rc(), "extra": random.choice(("", "", "backpack", "cape", "wings")), "extra_color": rc(),
            "eyes": random.choice(list(model3d.EYES)),
        })
        self._load_widgets()


class AvatarStudio(QDialog):
    def __init__(self, settings: dict, engine: voice.Voice | None = None, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Avatar Studio · 3D")
        self.setObjectName("studio")
        self.setStyleSheet(QSS)
        self.resize(980, 680)
        self.engine = engine
        v = QVBoxLayout(self)
        self.tabs = QTabWidget()
        self.sides = {}
        for who in ("main", "friend"):
            side = _Side(who, settings, engine)
            self.sides[who] = side
            self.tabs.addTab(side, side.name0.split()[0] + ("  (on screen)" if who == "main" else "  (dance friend)"))
        v.addWidget(self.tabs, 1)

        opts = QHBoxLayout()
        self.use3d = QCheckBox("Show my avatars in 3D on the screen")
        self.use3d.setChecked(bool(settings.get("avatar_3d", True)))
        self.speak = QCheckBox("Speak the speech bubbles out loud")
        self.speak.setChecked(bool(settings.get("voice_on", False)))
        self.vol = QSlider(Qt.Horizontal, minimum=10, maximum=100)
        self.vol.setValue(int(float(settings.get("voice_volume", 0.9)) * 100))
        self.vol.setMaximumWidth(140)
        opts.addWidget(self.use3d)
        opts.addWidget(self.speak)
        opts.addWidget(QLabel("Volume"))
        opts.addWidget(self.vol)
        opts.addStretch(1)
        v.addLayout(opts)

        eng = QHBoxLayout()
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.install_btn = QPushButton("Install natural voices engine")
        self.install_btn.setObjectName("soft")
        self.install_btn.clicked.connect(self._install)
        eng.addWidget(self.status, 1)
        eng.addWidget(self.install_btn)
        v.addLayout(eng)
        self._engine_status()
        if engine is not None:
            engine.status.connect(self.status.setText)
            engine.installed.connect(lambda ok: (self._engine_status(), [s._voice_changed() for s in self.sides.values()]))

        foot = QHBoxLayout()
        foot.addStretch(1)
        cancel = QPushButton("Cancel")
        cancel.setObjectName("soft")
        cancel.clicked.connect(self.reject)
        save = QPushButton("✓  Save and show")
        save.setObjectName("primary")
        save.setDefault(True)
        save.clicked.connect(self.accept)
        foot.addWidget(cancel)
        foot.addWidget(save)
        v.addLayout(foot)

    def _engine_status(self):
        ok = voice.piper_ok()
        self.install_btn.setVisible(not ok and voice.can_install_piper() and self.engine is not None)
        if ok:
            self.status.setText("🎙 Natural voices are ready. Pick a voice for each character in the Voice tab.")
        elif voice.can_install_piper():
            self.status.setText("🎙 For natural voices, install the voice engine (Piper, runs on this computer).")
        else:
            self.status.setText("🎙 This build uses the computer's own voice.")

    def _install(self):
        self.install_btn.setEnabled(False)
        self.engine.install_engine()

    def done(self, r):
        for s in self.sides.values():
            s.view.timer.stop()
        if self.engine is not None:
            self.engine.stop()
        super().done(r)

    def result_into(self, settings: dict) -> None:
        for who, side in self.sides.items():
            settings[f"look3d_{who}"] = dict(side.look)
            settings[f"voice_{who}"] = side.voice_cfg()
            name = side.name.text().strip()
            if name:
                settings[side.name_key] = name
        settings["avatar_3d"] = self.use3d.isChecked()
        settings["voice_on"] = self.speak.isChecked()
        settings["voice_volume"] = self.vol.value() / 100
