"""Settings dialog with live preview of the runner."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog,
                               QDialogButtonBox, QFileDialog, QFormLayout,
                               QGroupBox, QHBoxLayout, QLabel, QLineEdit,
                               QPlainTextEdit, QPushButton, QSpinBox, QTabWidget,
                               QVBoxLayout, QWidget)

from .characters import BUILTIN, load_frames


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Mascot settings")
        self.setMinimumWidth(460)
        self.s = dict(settings)
        v = QVBoxLayout(self)
        tabs = QTabWidget()
        v.addWidget(tabs)

        # ---- character -------------------------------------------------- #
        g = QWidget()
        f = QFormLayout(g)
        self.pet_name = QLineEdit(str(self.s.get("pet_name", "Primo")), maxLength=24)
        self.pet_name.setToolTip("Used wherever the words contain {name}")
        f.addRow("Name", self.pet_name)
        self.character = QComboBox()
        for k, label in BUILTIN.items():
            self.character.addItem(label, k)
        self.character.addItem("Custom (GIF / sprite sheet / folder)…", "custom")
        self.character.setCurrentIndex(max(0, self.character.findData(self.s["character"])))
        f.addRow("Character", self.character)

        self.color_btn = QPushButton()
        self.color_btn.clicked.connect(self._pick_color)
        f.addRow("Jacket colour", self.color_btn)
        self.rope_btn = QPushButton()
        self.rope_btn.clicked.connect(self._pick_rope)
        f.addRow("Rope colour", self.rope_btn)

        crow = QHBoxLayout()
        self.custom_path = QLineEdit(self.s.get("custom_path", ""))
        b1 = QPushButton("Image…")
        b1.setToolTip("Animated GIF/WebP, or a sprite sheet PNG (frames side by side)")
        b2 = QPushButton("Folder…")
        b2.setToolTip("Folder of PNG frames: run*.png, plus optional jump*.png and sleep*.png")
        b1.clicked.connect(self._browse_file)
        b2.clicked.connect(self._browse_dir)
        crow.addWidget(self.custom_path, 1)
        crow.addWidget(b1)
        crow.addWidget(b2)
        f.addRow("Custom file", crow)
        self.sprite_frames = QSpinBox(minimum=0, maximum=64, value=int(self.s.get("sprite_frames", 0)))
        self.sprite_frames.setSpecialValueText("auto")
        self.sprite_frames.setToolTip("Only for sprite sheets: number of frames side by side. 'auto' assumes square frames.")
        f.addRow("Sprite frames", self.sprite_frames)

        self.preview = QLabel(alignment=Qt.AlignCenter)
        self.preview.setFixedHeight(110)
        self.preview.setStyleSheet("background:#2b2b2b; border-radius:8px;")
        f.addRow(self.preview)
        self.err = QLabel(styleSheet="color:#E53935;", wordWrap=True)
        f.addRow(self.err)
        tabs.addTab(g, "Character")

        # ---- words ------------------------------------------------------ #
        gw = QWidget()
        fw = QFormLayout(gw)
        hint = QLabel("{name} = the name above, {greet} = Good morning / afternoon / evening.\n"
                      "Lists: one line each, a random one is picked. Leave a box empty to stay quiet.")
        hint.setWordWrap(True)
        fw.addRow(hint)
        self.say_hello = QLineEdit(str(self.s.get("say_hello", "")))
        fw.addRow("Hello at start", self.say_hello)
        self.say_click = QPlainTextEdit("\n".join(self.s.get("say_click", [])))
        self.say_click.setFixedHeight(80)
        fw.addRow("When clicked", self.say_click)
        self.say_cheers = QPlainTextEdit("\n".join(self.s.get("say_cheers", [])))
        self.say_cheers.setFixedHeight(120)
        fw.addRow("Cheers", self.say_cheers)
        self.say_top = QLineEdit(str(self.s.get("say_top", "")))
        fw.addRow("Sneaking on top", self.say_top)
        self.say_fall = QLineEdit(str(self.s.get("say_fall", "")))
        fw.addRow("Clicked off the rope", self.say_fall)
        self.say_laugh = QLineEdit(str(self.s.get("say_laugh", "")))
        fw.addRow("Laughing after", self.say_laugh)
        self.say_grab = QLineEdit(str(self.s.get("say_grab", "")))
        fw.addRow("When grabbed", self.say_grab)
        self.say_tampo = QLineEdit(str(self.s.get("say_tampo", "")))
        fw.addRow("Sulking (tampo)", self.say_tampo)
        self.say_forgive = QLineEdit(str(self.s.get("say_forgive", "")))
        fw.addRow("Clicked while sulking", self.say_forgive)
        tabs.addTab(gw, "Words")

        # ---- behaviour -------------------------------------------------- #
        g2 = QWidget()
        f2 = QFormLayout(g2)
        self.speed = QComboBox()
        for label, k in [("Tasks + notifications + CPU (mix)", "mix"),
                         ("Tasks + notifications only", "tasks"), ("CPU usage only (classic RunCat)", "cpu")]:
            self.speed.addItem(label, k)
        self.speed.setCurrentIndex(max(0, self.speed.findData(self.s["speed_source"])))
        f2.addRow("Speed follows", self.speed)
        self.show_tray = QCheckBox("Show in system tray / top bar", checked=self.s["show_tray"])
        self.show_pet = QCheckBox("Show floating pet on desktop", checked=self.s["show_pet"])
        self.pet_ghost = QCheckBox("Ghost mode: clicks go straight through the pet (it can't be touched)",
                                   checked=self.s.get("pet_ghost", False))
        self.pet_ghost.setToolTip("Off: you can click, drag and pat the pet, and it still never takes your typing or scrolling.\n"
                                  "On: the pet ignores the mouse completely. Use the tray icon menu instead.")
        self.pet_roam = QCheckBox("Pet does laps around the screen (run, climb, sneak, nap)", checked=self.s.get("pet_roam", True))
        self.lap_falls = QCheckBox("Sometimes slips and falls while climbing", checked=self.s.get("lap_falls", True))
        self.lap_click_fall = QCheckBox("Clicking it on the rope knocks it off", checked=self.s.get("lap_click_fall", True))
        self.lap_sneak = QCheckBox("Tiptoes and looks around on the top edge", checked=self.s.get("lap_sneak", True))
        self.nap_seconds = QSpinBox(minimum=5, maximum=3600, singleStep=5, value=int(self.s.get("nap_seconds", 60)), suffix=" s")
        self.nap_seconds.setToolTip("Roughly how long it sleeps after each lap (shorter when you have open tasks).")
        self.greetings = QCheckBox("Say hello && cheers on its own (not only when clicked)", checked=self.s.get("greetings", True))
        self.pet_size = QSpinBox(minimum=32, maximum=320, singleStep=8, value=int(self.s["pet_size"]), suffix=" px")
        self.max_fps = QSpinBox(minimum=4, maximum=30, value=int(self.s["max_fps"]), suffix=" fps")
        self.max_fps.setToolTip("Top animation speed. Lower uses less CPU (esp. tray on Linux).")
        self.dnd = QCheckBox("Do not disturb (no pop-ups, still counts)", checked=self.s["dnd"])
        self.autostart = QCheckBox("Start when I log in", checked=self.s["autostart"])
        for w in (self.show_tray, self.show_pet):
            f2.addRow(w)
        f2.addRow(self.pet_ghost)
        f2.addRow(self.pet_roam)
        f2.addRow(self.lap_falls)
        f2.addRow(self.lap_click_fall)
        f2.addRow(self.lap_sneak)
        self.grab_tampo = QCheckBox("Gets angry when grabbed, then sulks (tampo)", checked=self.s.get("grab_tampo", True))
        f2.addRow(self.grab_tampo)
        f2.addRow("Nap after a lap", self.nap_seconds)
        f2.addRow(self.greetings)
        f2.addRow("Pet size", self.pet_size)
        f2.addRow("Max speed", self.max_fps)
        f2.addRow(self.dnd)
        f2.addRow(self.autostart)
        tabs.addTab(g2, "Behaviour")

        # ---- webhook ---------------------------------------------------- #
        g3 = QWidget()
        f3 = QFormLayout(g3)
        f3.addRow(QLabel("Let other apps send notifications to the mascot."))
        self.wh_on = QCheckBox("Enable local webhook on 127.0.0.1", checked=self.s["webhook_enabled"])
        self.wh_port = QSpinBox(minimum=1024, maximum=65535, value=int(self.s["webhook_port"]))
        self.wh_token = QLineEdit(self.s.get("webhook_token", ""), placeholderText="optional secret (X-Token header)")
        f3.addRow(self.wh_on)
        f3.addRow("Port", self.wh_port)
        f3.addRow("Token", self.wh_token)
        tabs.addTab(g3, "Webhook")

        bb = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        bb.accepted.connect(self.accept)
        bb.rejected.connect(self.reject)
        v.addWidget(bb)

        # live preview
        self._frames = []
        self._i = 0
        self._anim = QTimer(self, interval=80, timeout=self._tick)
        self.character.currentIndexChanged.connect(self._reload)
        self.custom_path.editingFinished.connect(self._reload)
        self.sprite_frames.valueChanged.connect(self._reload)
        self._update_color_btn()
        self._reload()
        self._anim.start()

    # ------------------------------------------------------------------ #
    def _update_color_btn(self):
        c = self.s["color"]
        self.color_btn.setText(c)
        self.color_btn.setStyleSheet(f"background:{c}; color:{'#000' if QColor(c).lightness() > 128 else '#fff'};")
        r = self.s.get("rope_color", "#C79A5B")
        self.rope_btn.setText(r)
        self.rope_btn.setStyleSheet(f"background:{r}; color:{'#000' if QColor(r).lightness() > 128 else '#fff'};")

    def _pick_rope(self):
        c = QColorDialog.getColor(QColor(self.s.get("rope_color", "#C79A5B")), self, "Rope colour")
        if c.isValid():
            self.s["rope_color"] = c.name()
            self._update_color_btn()

    def _pick_color(self):
        c = QColorDialog.getColor(QColor(self.s["color"]), self, "Runner colour")
        if c.isValid():
            self.s["color"] = c.name()
            self._update_color_btn()
            self._reload()

    def _browse_file(self):
        p, _ = QFileDialog.getOpenFileName(self, "Choose runner image", "",
                                           "Images (*.gif *.webp *.png *.jpg)")
        if p:
            self.custom_path.setText(p)
            self.character.setCurrentIndex(self.character.findData("custom"))
            self._reload()

    def _browse_dir(self):
        p = QFileDialog.getExistingDirectory(self, "Choose folder of PNG frames")
        if p:
            self.custom_path.setText(p)
            self.character.setCurrentIndex(self.character.findData("custom"))
            self._reload()

    def _collect(self) -> dict:
        s = self.s
        s["character"] = self.character.currentData()
        s["pet_name"] = self.pet_name.text().strip() or "Primo"
        lines = lambda w: [ln.strip() for ln in w.toPlainText().splitlines() if ln.strip()]
        s["say_hello"] = self.say_hello.text().strip()
        s["say_click"] = lines(self.say_click)
        s["say_cheers"] = lines(self.say_cheers)
        s["say_top"] = self.say_top.text().strip()
        s["say_fall"] = self.say_fall.text().strip()
        s["say_laugh"] = self.say_laugh.text().strip()
        s["say_grab"] = self.say_grab.text().strip()
        s["say_tampo"] = self.say_tampo.text().strip()
        s["say_forgive"] = self.say_forgive.text().strip()
        s["grab_tampo"] = self.grab_tampo.isChecked()
        s["lap_falls"] = self.lap_falls.isChecked()
        s["lap_click_fall"] = self.lap_click_fall.isChecked()
        s["lap_sneak"] = self.lap_sneak.isChecked()
        s["nap_seconds"] = self.nap_seconds.value()
        s["custom_path"] = self.custom_path.text().strip()
        s["sprite_frames"] = self.sprite_frames.value()
        s["speed_source"] = self.speed.currentData()
        s["show_tray"] = self.show_tray.isChecked()
        s["show_pet"] = self.show_pet.isChecked()
        s["pet_size"] = self.pet_size.value()
        s["pet_ghost"] = self.pet_ghost.isChecked()
        s["pet_roam"] = self.pet_roam.isChecked()
        s["greetings"] = self.greetings.isChecked()
        s["max_fps"] = self.max_fps.value()
        s["dnd"] = self.dnd.isChecked()
        s["autostart"] = self.autostart.isChecked()
        s["webhook_enabled"] = self.wh_on.isChecked()
        s["webhook_port"] = self.wh_port.value()
        s["webhook_token"] = self.wh_token.text().strip()
        return s

    def _reload(self):
        fs, err = load_frames(self._collect())
        self.err.setText(err or "")
        self._frames = fs.run + fs.jump * 2 + fs.run   # preview runs, jumps, runs
        self._i = 0

    def _tick(self):
        if self._frames:
            self._i = (self._i + 1) % len(self._frames)
            self.preview.setPixmap(self._frames[self._i].scaled(96, 96, Qt.KeepAspectRatio, Qt.SmoothTransformation))

    def result_settings(self) -> dict:
        return self._collect()
