"""Settings dialog with live preview of the runner."""
from __future__ import annotations

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (QCheckBox, QColorDialog, QComboBox, QDialog,
                               QDialogButtonBox, QFileDialog, QFormLayout, QGridLayout,
                               QGroupBox, QHBoxLayout, QInputDialog, QLabel, QLineEdit,
                               QListWidget, QListWidgetItem, QPlainTextEdit, QPushButton,
                               QScrollArea, QSlider, QSpinBox, QTabWidget,
                               QVBoxLayout, QWidget)

from . import themes, uitheme, workmode
from .characters import BUILTIN, desk_frames, load_frames


class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None, app=None):
        super().__init__(parent)
        self.parent_app = app                 # the running app: "Ride now" and "Check now" buttons
        self.setWindowTitle("Mascot settings")
        self.setMinimumWidth(700)
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
        self.activity_react = QCheckBox("Joins in: headphones for music, popcorn for videos, a book when I read",
                                        checked=self.s.get("activity_react", True))
        self.activity_react.setToolTip("Linux: needs playerctl for music/video. Reading is detected on Hyprland.\n"
                                       "The mood (happy, hype, chill, sad, love) is guessed from the song title and artist.")
        f2.addRow(self.activity_react)
        self.activity_caption = QCheckBox("Show a small line above him: mode icon + what is playing",
                                          checked=self.s.get("activity_caption", True))
        f2.addRow(self.activity_caption)
        self.meeting_look = QCheckBox("In a call (Meet, Zoom, Teams…): office clothes and a headset",
                                      checked=self.s.get("meeting_look", True))
        self.meeting_look.setToolTip("A call is a meeting window being open (Hyprland), or a meeting app or browser using the microphone.")
        f2.addRow(self.meeting_look)
        self.meeting_mic = QCheckBox("…and he talks when the microphone hears me", checked=self.s.get("meeting_mic", True))
        self.meeting_mic.setToolTip("Only during a call. Only the loudness of the microphone is measured; nothing is recorded,\n"
                                    "saved or sent. It follows the system microphone, not the mute button inside the meeting app.")
        f2.addRow(self.meeting_mic)
        self.study_words = QLineEdit(", ".join(self.s.get("study_words") or []))
        self.study_words.setPlaceholderText("e.g. NetworkChuck, Fireship, devlog")
        self.study_words.setToolTip("Words or channel names, separated by commas. A video whose title or channel contains one\n"
                                    "makes him put on glasses and take notes, like a tutorial or podcast.")
        f2.addRow("Take notes for", self.study_words)
        self.bubble_font = QSpinBox(minimum=10, maximum=18, value=int(self.s.get("bubble_font", 13)), suffix=" px")
        f2.addRow("Speech bubble text size", self.bubble_font)
        f2.addRow(self.lap_falls)
        f2.addRow(self.lap_click_fall)
        f2.addRow(self.lap_sneak)
        self.grab_tampo = QCheckBox("Gets angry when grabbed, then sulks (tampo)", checked=self.s.get("grab_tampo", True))
        f2.addRow(self.grab_tampo)
        f2.addRow("Nap after a lap", self.nap_seconds)
        f2.addRow(self.greetings)
        f2.addRow("Max speed", self.max_fps)
        f2.addRow(self.dnd)
        f2.addRow(self.autostart)
        tabs.addTab(_scroll(g2), "Behaviour")

        # ---- look & place ------------------------------------------------ #
        g6 = QWidget()
        f6 = QFormLayout(g6)
        self.ui_theme = QComboBox()
        for k in uitheme.ORDER:
            self.ui_theme.addItem(uitheme.THEMES[k]["label"], k)
        self.ui_theme.setCurrentIndex(max(0, self.ui_theme.findData(self.s.get("ui_theme", "system"))))
        self.ui_theme.setToolTip("Colours of the windows, menus and speech bubbles. Looks the same on Windows 10, 11 and Linux.")
        f6.addRow("App theme", self.ui_theme)
        self.theme_swatch = QLabel()
        self.theme_swatch.setFixedHeight(34)
        f6.addRow("", self.theme_swatch)
        self.ui_theme.currentIndexChanged.connect(self._show_swatch)

        size_box = QGroupBox("Size")
        fs = QFormLayout(size_box)
        self.pet_size.setToolTip("How tall he is on the screen.")
        fs.addRow("Height", self.pet_size)
        wrow = QHBoxLayout()
        self.pet_width = QSlider(Qt.Horizontal, minimum=50, maximum=200, value=int(self.s.get("pet_width", 100)))
        self.pet_width.setSingleStep(5)
        self.pet_width.setPageStep(10)
        self.width_lbl = QLabel()
        self.width_lbl.setMinimumWidth(60)
        b_reset = QPushButton("As drawn")
        b_reset.clicked.connect(lambda: self.pet_width.setValue(100))
        wrow.addWidget(self.pet_width, 1)
        wrow.addWidget(self.width_lbl)
        wrow.addWidget(b_reset)
        fs.addRow("Width", wrow)
        self.pet_width.valueChanged.connect(self._show_width)
        self.pet_size.valueChanged.connect(self._show_width)
        f6.addRow(size_box)

        place_box = QGroupBox("Place")
        fp = QFormLayout(place_box)
        self.pet_lift = QSpinBox(minimum=0, maximum=600, singleStep=10, value=int(self.s.get("pet_lift", 0)), suffix=" px")
        self.pet_lift.setSpecialValueText("on the bottom edge")
        self.pet_lift.setToolTip("Raise his running line and his seat above the bottom of the screen\n"
                                 "(for example to stay clear of the taskbar or a dock).")
        fp.addRow("Raise him by", self.pet_lift)
        self.seat_side = QComboBox()
        for k, label in workmode.SEAT_SIDES:
            self.seat_side.addItem(label, k)
        self.seat_side.setCurrentIndex(max(0, self.seat_side.findData(self.s.get("seat_side", "right"))))
        self.seat_side.setToolTip("Where he sits down to join in: calls, work modes (Storyline), music, videos, reading, focus.")
        fp.addRow("He sits", self.seat_side)
        self.seat_screen = QComboBox()
        self.seat_screen.addItem("On the screen he is on", "same")
        self.seat_screen.addItem("Always on the main screen", "main")
        self.seat_screen.setCurrentIndex(max(0, self.seat_screen.findData(self.s.get("seat_screen", "same"))))
        fp.addRow("Screen", self.seat_screen)
        hint6 = QLabel("Tip: turn off “Pet does laps around the screen” (Behaviour) and drag him anywhere: he stays there.")
        hint6.setWordWrap(True)
        hint6.setStyleSheet("color: palette(mid);")
        fp.addRow(hint6)
        f6.addRow(place_box)

        wear_box = QGroupBox("Wardrobe")
        fw = QFormLayout(wear_box)
        self.my_color_always = QCheckBox("Wear my jacket colour on adventure days too",
                                         checked=self.s.get("my_color_always", False))
        self.my_color_always.setToolTip("The jacket colour is on the Character tab. Normally the hike, space, jungle and "
                                        "fiesta days bring their own colours; tick this to keep yours.")
        fw.addRow(self.my_color_always)
        self.cup_color = self.s.get("cup_color", "#E8762B")
        self.cup_btn = QPushButton()
        self.cup_btn.clicked.connect(lambda: self._pick_into("cup_color", self.cup_btn, "Cup colour"))
        self._paint_btn(self.cup_btn, self.cup_color)
        fw.addRow("Coffee cup", self.cup_btn)
        self.coffee_breaks = QCheckBox("Coffee breaks: some naps become a sip from his cup ☕",
                                       checked=self.s.get("coffee_breaks", True))
        fw.addRow(self.coffee_breaks)
        f6.addRow(wear_box)
        tabs.insertTab(1, g6, "Look && place")

        # ---- rides ------------------------------------------------------- #
        from . import rides
        g8 = QWidget()
        f8 = QFormLayout(g8)
        intro8 = QLabel("Now and then Primo rides an animal across the screen. The ride never takes the mouse or the "
                        "keyboard: you can keep clicking and typing right through it. No rides during calls, films, "
                        "full-screen apps, focus time or work modes.")
        intro8.setWordWrap(True)
        f8.addRow(intro8)
        self.rides_on = QCheckBox("Rides on", checked=self.s.get("rides_on", True))
        f8.addRow(self.rides_on)
        self.ride_every = QSpinBox(minimum=0, maximum=600, singleStep=5, value=int(self.s.get("ride_every", 40)),
                                   suffix=" min")
        self.ride_every.setSpecialValueText("only when I ask")
        f8.addRow("A ride every", self.ride_every)
        picked = set(self.s.get("ride_animals") or rides.RIDES)
        self.ride_colors = dict(self.s.get("ride_colors") or {})
        self.ride_checks = {}
        grid = QGridLayout()
        for i, (key, (label, how, default)) in enumerate(rides.RIDES.items()):
            cb = QCheckBox(f"{label}  ({ {'fly': 'flies', 'run': 'runs', 'swim': 'swims'}[how] })", checked=key in picked)
            btn = QPushButton()
            btn.setFixedWidth(90)
            btn.clicked.connect(lambda _=False, k=key, b=btn: self._pick_ride_color(k, b))
            self._paint_btn(btn, self.ride_colors.get(key, default))
            go = QPushButton("Ride now")
            go.clicked.connect(lambda _=False, k=key: self.parent_app and self.parent_app.start_ride(k))
            grid.addWidget(cb, i, 0)
            grid.addWidget(btn, i, 1)
            grid.addWidget(go, i, 2)
            self.ride_checks[key] = cb
        f8.addRow(grid)
        self.dance_mood = QCheckBox("Dance to upbeat and love songs too (the style follows the mood of the song)",
                                    checked=self.s.get("dance_mood", True))
        f8.addRow(self.dance_mood)
        tabs.addTab(_scroll(g8), "Rides && fun")

        # ---- about / updates ---------------------------------------------- #
        from . import __version__, updater
        g9 = QWidget()
        f9 = QFormLayout(g9)
        title9 = QLabel(f"<h2>CapyRunner {__version__}</h2><p>Developed by <b>{updater.DEVELOPER}</b></p>"
                        "<p>Primo, the Capytech mascot, for Windows 10/11, Linux (Arch, Ubuntu, Fedora…) and macOS.</p>")
        title9.setWordWrap(True)
        f9.addRow(title9)
        self.update_check = QCheckBox("Check for a new version once a day", checked=self.s.get("update_check", True))
        self.update_check.setToolTip("Only GitHub's public release page is read. Nothing about you is sent.")
        f9.addRow(self.update_check)
        b_upd = QPushButton("Check now")
        b_upd.clicked.connect(lambda: self.parent_app and self.parent_app.check_updates(manual=True))
        f9.addRow(b_upd)
        tabs.addTab(g9, "About")

        # ---- work modes --------------------------------------------------- #
        g7 = QWidget()
        v7 = QVBoxLayout(g7)
        intro = QLabel("While you work in one of these apps, Primo sits on his office chair and types on his laptop.\n"
                       "Change the name, the apps, the days and his look, or add your own modes.")
        intro.setWordWrap(True)
        v7.addWidget(intro)
        self.work_on = QCheckBox("Work modes on", checked=self.s.get("work_on", True))
        v7.addWidget(self.work_on)
        row = QHBoxLayout()
        self.mode_list = QListWidget()
        self.mode_list.setMaximumWidth(190)
        row.addWidget(self.mode_list)
        ed = QWidget()
        fe = QFormLayout(ed)
        fe.setContentsMargins(0, 0, 0, 0)
        self.m_name = QLineEdit(maxLength=32)
        fe.addRow("Name", self.m_name)
        self.m_icon = QLineEdit(maxLength=4)
        self.m_icon.setMaximumWidth(60)
        fe.addRow("Icon", self.m_icon)
        arow = QHBoxLayout()
        self.m_apps = QLineEdit()
        self.m_apps.setPlaceholderText("e.g. Articulate Storyline, Storyline.exe")
        self.m_apps.setToolTip("Words from the program name or the window title, separated by commas.")
        b_pick = QPushButton("Pick…")
        b_pick.setToolTip("Choose from the windows open right now")
        b_pick.clicked.connect(self._pick_window)
        arow.addWidget(self.m_apps, 1)
        arow.addWidget(b_pick)
        fe.addRow("Apps", arow)
        self.m_when = QComboBox()
        self.m_when.addItem("While the app is in front", "front")
        self.m_when.addItem("While the app is open", "open")
        fe.addRow("On", self.m_when)
        drow = QHBoxLayout()
        drow.setSpacing(2)
        self.m_days = []
        for d in workmode.DAY_SHORT:
            cb = QCheckBox(d)
            self.m_days.append(cb)
            drow.addWidget(cb)
        fe.addRow("Days", drow)
        qrow = QHBoxLayout()
        for label, days in (("Mon–Fri", range(5)), ("Every day", range(7)), ("None", ())):
            b = QPushButton(label)
            b.clicked.connect(lambda _=False, d=tuple(days): [cb.setChecked(i in d) for i, cb in enumerate(self.m_days)])
            qrow.addWidget(b)
        qrow.addStretch(1)
        fe.addRow("", qrow)
        self.m_look = QComboBox()
        for k, label in workmode.LOOKS.items():
            self.m_look.addItem(label, k)
        fe.addRow("He wears", self.m_look)
        self.m_chair = QPushButton()
        self.m_chair.clicked.connect(self._pick_chair)
        fe.addRow("Chair colour", self.m_chair)
        self.m_glasses = QCheckBox("Glasses on while he works")
        fe.addRow(self.m_glasses)
        self.m_say = QLineEdit()
        self.m_say.setToolTip("Said when the mode starts. {mode} = the name, {app} = the app, {name} = Primo's name.")
        fe.addRow("He says", self.m_say)
        self.desk_preview = QLabel(alignment=Qt.AlignCenter)
        self.desk_preview.setFixedHeight(110)
        self.desk_preview.setStyleSheet("background:#2b2b2b; border-radius:8px;")
        fe.addRow(self.desk_preview)
        row.addWidget(ed, 1)
        v7.addLayout(row, 1)
        brow = QHBoxLayout()
        b_add = QPushButton("+ Add mode")
        b_add.clicked.connect(self._add_mode)
        b_dup = QPushButton("Copy")
        b_dup.clicked.connect(self._copy_mode)
        b_del = QPushButton("Remove")
        b_del.clicked.connect(self._remove_mode)
        for b in (b_add, b_dup, b_del):
            brow.addWidget(b)
        brow.addStretch(1)
        v7.addLayout(brow)
        self.modes = [dict(m) for m in workmode.modes(self.s)]
        self._cur = -1
        self._fill_modes()
        self.mode_list.currentRowChanged.connect(self._mode_selected)
        self.mode_list.itemChanged.connect(self._mode_toggled)
        for w in (self.m_look,):
            w.currentIndexChanged.connect(self._reload_desk)
        self.m_glasses.toggled.connect(self._reload_desk)
        self.m_name.textEdited.connect(self._rename_item)
        if self.modes:
            self.mode_list.setCurrentRow(0)
        else:
            self._mode_selected(-1)
        tabs.insertTab(2, g7, "Work modes")

        # ---- weekday adventures ------------------------------------------ #
        g4 = QWidget()
        f4 = QFormLayout(g4)
        tip = QLabel("Each day Primo's lap is a different trip, and together they tell one story.\n"
                     "Pick the adventure for every day, or wear one all the time.")
        tip.setWordWrap(True)
        f4.addRow(tip)

        def theme_combo(current: str, auto: bool = False) -> QComboBox:
            c = QComboBox()
            if auto:
                c.addItem("Follow the week plan below (auto)", "auto")
            for key in themes.ORDER:
                c.addItem(f"{themes.THEMES[key]['icon']}  {themes.THEMES[key]['label']}", key)
            c.setCurrentIndex(max(0, c.findData(current)))
            return c

        self.day_theme = theme_combo(self.s.get("day_theme", "auto"), auto=True)
        f4.addRow("Right now", self.day_theme)
        week = list(self.s.get("week_themes") or themes.DEFAULT_WEEK)
        week += themes.DEFAULT_WEEK[len(week):]
        self.week_themes = []
        for i, day in enumerate(themes.DAYS):
            c = theme_combo(week[i])
            self.week_themes.append(c)
            f4.addRow(day, c)
        self.adventure_talk = QCheckBox("Tells the story of the day in the speech bubble",
                                        checked=self.s.get("adventure_talk", True))
        f4.addRow(self.adventure_talk)
        tabs.addTab(g4, "Adventures")

        # ---- friend & dance ---------------------------------------------- #
        g5 = QWidget()
        f5 = QFormLayout(g5)
        self.friend_on = QCheckBox("Primo's friend turns up for dance showdowns", checked=self.s.get("friend_on", True))
        f5.addRow(self.friend_on)
        self.friend_name = QLineEdit(str(self.s.get("friend_name", "Jeo OngBack")), maxLength=24)
        f5.addRow("Friend's name", self.friend_name)
        self.dance_songs = QCheckBox("Start a showdown when a dance song is playing", checked=self.s.get("dance_songs", True))
        self.dance_songs.setToolTip("Decided from the song title and artist: dance words (dance, sayaw, budots…)\n"
                                    "and the dance-challenge songs going round right now. Needs “Joins in” to be on.")
        f5.addRow(self.dance_songs)
        self.dance_every = QSpinBox(minimum=0, maximum=600, singleStep=5, value=int(self.s.get("dance_every", 30)),
                                    suffix=" min", specialValueText="never")
        f5.addRow("Jeo challenges Primo every", self.dance_every)
        self.dance_extra = QLineEdit(", ".join(self.s.get("dance_extra") or []))
        self.dance_extra.setPlaceholderText("e.g. Macarena, Cha Cha Slide, my zumba playlist")
        self.dance_extra.setToolTip("Words from a title or artist, separated by commas. A song that contains one is a dance song.")
        f5.addRow("My dance songs", self.dance_extra)
        tabs.addTab(g5, "Friend && dance")

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
        self.day_theme.currentIndexChanged.connect(self._reload)
        self.day_theme.currentIndexChanged.connect(self._reload_desk)
        for c in self.week_themes:
            c.currentIndexChanged.connect(self._reload)
        self._update_color_btn()
        self._reload()
        self._show_swatch()
        self._show_width()
        self._anim.start()

    # ------------------------------------------------------------------ #
    @staticmethod
    def _paint_btn(btn, c: str):
        btn.setText(c)
        btn.setStyleSheet(f"background:{c}; color:{'#000' if QColor(c).lightness() > 128 else '#fff'};")

    def _pick_into(self, attr: str, btn, title: str):
        c = QColorDialog.getColor(QColor(getattr(self, attr)), self, title)
        if c.isValid():
            setattr(self, attr, c.name())
            self._paint_btn(btn, c.name())

    def _pick_ride_color(self, key: str, btn):
        from . import rides
        c = QColorDialog.getColor(QColor(self.ride_colors.get(key, rides.RIDES[key][2])), self, "Animal colour")
        if c.isValid():
            self.ride_colors[key] = c.name()
            self._paint_btn(btn, c.name())

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
        s["pet_width"] = self.pet_width.value()
        s["pet_lift"] = self.pet_lift.value()
        s["seat_side"] = self.seat_side.currentData()
        s["seat_screen"] = self.seat_screen.currentData()
        s["ui_theme"] = self.ui_theme.currentData()
        s["work_on"] = self.work_on.isChecked()
        self._store_mode()
        s["work_modes"] = [dict(m) for m in self.modes]
        s["pet_ghost"] = self.pet_ghost.isChecked()
        s["pet_roam"] = self.pet_roam.isChecked()
        s["activity_react"] = self.activity_react.isChecked()
        s["activity_caption"] = self.activity_caption.isChecked()
        s["meeting_look"] = self.meeting_look.isChecked()
        s["meeting_mic"] = self.meeting_mic.isChecked()
        s["study_words"] = [w.strip() for w in self.study_words.text().split(",") if w.strip()]
        s["bubble_font"] = self.bubble_font.value()
        s["greetings"] = self.greetings.isChecked()
        s["max_fps"] = self.max_fps.value()
        s["dnd"] = self.dnd.isChecked()
        s["autostart"] = self.autostart.isChecked()
        s["friend_on"] = self.friend_on.isChecked()
        s["friend_name"] = self.friend_name.text().strip() or "Jeo OngBack"
        s["dance_songs"] = self.dance_songs.isChecked()
        s["dance_every"] = self.dance_every.value()
        s["dance_extra"] = [w.strip() for w in self.dance_extra.text().split(",") if w.strip()]
        s["day_theme"] = self.day_theme.currentData()
        s["week_themes"] = [c.currentData() for c in self.week_themes]
        s["adventure_talk"] = self.adventure_talk.isChecked()
        s["my_color_always"] = self.my_color_always.isChecked()
        s["cup_color"] = self.cup_color
        s["coffee_breaks"] = self.coffee_breaks.isChecked()
        s["rides_on"] = self.rides_on.isChecked()
        s["ride_every"] = self.ride_every.value()
        s["ride_animals"] = [k for k, cb in self.ride_checks.items() if cb.isChecked()]
        s["ride_colors"] = self.ride_colors
        s["dance_mood"] = self.dance_mood.isChecked()
        s["update_check"] = self.update_check.isChecked()
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
        self._i += 1
        w = max(24, round(96 * self.pet_width.value() / 100)) if hasattr(self, "pet_width") else 96
        if self._frames:
            pm = self._frames[self._i % len(self._frames)]
            self.preview.setPixmap(pm.scaled(w, 96, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))
        if getattr(self, "_desk", None):
            pm = self._desk[(self._i // 3) % len(self._desk)]
            self.desk_preview.setPixmap(pm.scaled(w, 96, Qt.IgnoreAspectRatio, Qt.SmoothTransformation))

    # ---- look & place ---------------------------------------------------- #
    def _show_width(self):
        self.width_lbl.setText(f"{self.pet_width.value()} %")

    def _show_swatch(self):
        t = uitheme.get(self.ui_theme.currentData())
        if "window" not in t:
            self.theme_swatch.setText("Uses your desktop's own colours.")
            self.theme_swatch.setStyleSheet("")
            return
        self.theme_swatch.setText("  Primo says hi! 👋  ")
        self.theme_swatch.setStyleSheet(
            f"background:{t['window']}; color:{t['text']}; border:2px solid {t['accent']}; border-radius:8px;"
            f"padding:4px; font-weight:600;")

    # ---- work modes ------------------------------------------------------ #
    def _fill_modes(self):
        self.mode_list.blockSignals(True)
        self.mode_list.clear()
        for m in self.modes:
            it = QListWidgetItem(f"{m.get('icon') or '💻'}  {m.get('name') or 'Work'}")
            it.setFlags(it.flags() | Qt.ItemIsUserCheckable)
            it.setCheckState(Qt.Checked if m.get("on", True) else Qt.Unchecked)
            it.setToolTip("Tick to switch this mode on")
            self.mode_list.addItem(it)
        self.mode_list.blockSignals(False)

    def _store_mode(self):
        i = self._cur
        if not (0 <= i < len(self.modes)):
            return
        m = self.modes[i]
        m["name"] = self.m_name.text().strip() or "Work"
        m["icon"] = self.m_icon.text().strip() or "💻"
        m["apps"] = [w.strip() for w in self.m_apps.text().split(",") if w.strip()]
        m["when"] = self.m_when.currentData()
        m["days"] = [d for d, cb in enumerate(self.m_days) if cb.isChecked()]
        m["look"] = self.m_look.currentData()
        m["glasses"] = self.m_glasses.isChecked()
        m["say"] = self.m_say.text().strip()
        it = self.mode_list.item(i)
        if it is not None:
            m["on"] = it.checkState() == Qt.Checked

    def _mode_selected(self, row: int):
        self._store_mode()
        self._cur = row
        has = 0 <= row < len(self.modes)
        for w in (self.m_name, self.m_icon, self.m_apps, self.m_when, self.m_look, self.m_chair, self.m_glasses, self.m_say,
                  *self.m_days):
            w.setEnabled(has)
        if not has:
            self._desk = []
            self.desk_preview.clear()
            return
        m = self.modes[row]
        self.m_name.setText(m.get("name", ""))
        self.m_icon.setText(m.get("icon", "💻"))
        self.m_apps.setText(", ".join(m.get("apps") or []))
        self.m_when.setCurrentIndex(max(0, self.m_when.findData(m.get("when", "front"))))
        for d, cb in enumerate(self.m_days):
            cb.setChecked(d in (m.get("days") or []))
        self.m_look.blockSignals(True)
        self.m_look.setCurrentIndex(max(0, self.m_look.findData(m.get("look", "hoodie"))))
        self.m_look.blockSignals(False)
        self.m_glasses.blockSignals(True)
        self.m_glasses.setChecked(bool(m.get("glasses", True)))
        self.m_glasses.blockSignals(False)
        self.m_say.setText(m.get("say", ""))
        self._chair_btn()
        self._reload_desk()

    def _mode_toggled(self, it: QListWidgetItem):
        i = self.mode_list.row(it)
        if 0 <= i < len(self.modes):
            self.modes[i]["on"] = it.checkState() == Qt.Checked

    def _rename_item(self, text: str):
        it = self.mode_list.item(self._cur)
        if it is not None:
            self.mode_list.blockSignals(True)
            it.setText(f"{self.m_icon.text().strip() or '💻'}  {text.strip() or 'Work'}")
            self.mode_list.blockSignals(False)

    def _add_mode(self):
        self._store_mode()
        name, ok = QInputDialog.getText(self, "New work mode", "Name (for example: Coding, Design, Rise 360):")
        if not ok:
            return
        self.modes.append(workmode.new_mode(name.strip() or "New work mode"))
        self._cur = -1
        self._fill_modes()
        self.mode_list.setCurrentRow(len(self.modes) - 1)
        self.m_apps.setFocus()

    def _copy_mode(self):
        self._store_mode()
        if 0 <= self._cur < len(self.modes):
            m = dict(self.modes[self._cur])
            m["name"] = f"{m.get('name', 'Work')} (copy)"
            m["apps"] = list(m.get("apps") or [])
            m["days"] = list(m.get("days") or [])
            self.modes.append(m)
            self._cur = -1
            self._fill_modes()
            self.mode_list.setCurrentRow(len(self.modes) - 1)

    def _remove_mode(self):
        i = self._cur
        if 0 <= i < len(self.modes):
            del self.modes[i]
            self._cur = -1
            self._fill_modes()
            self.mode_list.setCurrentRow(min(i, len(self.modes) - 1))
            if not self.modes:
                self._mode_selected(-1)

    def _pick_window(self):
        names = []
        try:
            for prog, title in workmode._open_windows():
                for n in (title.strip(), prog.strip()):
                    if n and n not in names and len(n) < 90:
                        names.append(n)
        except Exception:
            pass
        if not names:
            self.m_apps.setFocus()
            self.m_apps.setPlaceholderText("No windows found here: type the app name, e.g. Storyline")
            return
        name, ok = QInputDialog.getItem(self, "Pick an app", "Windows open right now\n"
                                        "(tip: shorten it afterwards to the part that never changes, like “Storyline”):",
                                        names, 0, True)
        if ok and name.strip():
            words = [w.strip() for w in self.m_apps.text().split(",") if w.strip()]
            words.append(name.strip())
            self.m_apps.setText(", ".join(words))

    def _chair_btn(self):
        if 0 <= self._cur < len(self.modes):
            c = self.modes[self._cur].get("chair") or "#3B4A63"
            self.m_chair.setText(c)
            self.m_chair.setStyleSheet(f"background:{c}; color:{'#000' if QColor(c).lightness() > 128 else '#fff'};")

    def _pick_chair(self):
        if not (0 <= self._cur < len(self.modes)):
            return
        c = QColorDialog.getColor(QColor(self.modes[self._cur].get("chair") or "#3B4A63"), self, "Chair colour")
        if c.isValid():
            self.modes[self._cur]["chair"] = c.name()
            self._chair_btn()
            self._reload_desk()

    def _reload_desk(self):
        if not (0 <= self._cur < len(self.modes)):
            return
        m = self.modes[self._cur]
        look = self.m_look.currentData()
        outfit = ""
        if look == "adventure" and hasattr(self, "week_themes"):
            outfit = themes.get(themes.current({"day_theme": self.day_theme.currentData(),
                                                "week_themes": [c.currentData() for c in self.week_themes]}))["outfit"]
        self._desk = desk_frames(self.s.get("color", "#1F2A5A"), look, outfit, m.get("chair") or "#3B4A63",
                                 self.m_glasses.isChecked())

    def result_settings(self) -> dict:
        return self._collect()


def _scroll(w: QWidget) -> QScrollArea:
    """A tab with many rows: let it scroll on small laptop screens instead of growing off the screen."""
    sa = QScrollArea()
    sa.setWidget(w)
    sa.setWidgetResizable(True)
    sa.setFrameShape(QScrollArea.NoFrame)
    return sa
