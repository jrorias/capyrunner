# CapyRunner 🏃 — Capytech's running mascot for tasks & notifications

![Capy](docs/capy-preview.gif)

Capy lives in your **system tray / top bar** and/or as a **floating pet** that **runs back and forth along the
bottom of your screen**, turns around at the edges, stops now and then to **say hello** or remind you about tasks,
and **jumps with sparkles** when a notification arrives. Its speed reflects how busy you are:

| Capy is… | Meaning |
|---|---|
| 😴 sleeping | nothing pending, no unread notifications |
| 🚶 jogging | open tasks / CPU working |
| 🏃 sprinting | overdue tasks, many unread notifications or high CPU |
| 🎉 jumping with sparkles | a new notification or reminder just arrived |
| 🔴 badge | unread notifications + overdue tasks |

Works on **Windows 10/11**, **Linux** (Arch, Ubuntu, Fedora…; GNOME, KDE, Hyprland, XFCE, Cinnamon…) and **macOS**.

Developed by **Devjr**.

## Download (the easy way, no setup needed)
This repository is private, so you need a GitHub account that has been invited to it. Sign in first.

1. Open the **[latest release](https://github.com/jrorias/capyrunner/releases/latest)**.
2. Under **Assets**, click the file for your computer:
   - **Windows 10 / 11 (recommended):** `CapyRunner-Setup-x64.exe`, the installer
   - **Windows, no install:** `CapyRunner-windows-x64.zip` (portable: extract and run)
   - **Linux:** `CapyRunner-linux-x86_64.tar.gz` (on Arch you can also use `./install.sh`, see below)
   - **macOS (Apple silicon):** `CapyRunner-macos-arm64.zip`, double-click to unzip and drag **CapyRunner** to
     *Applications*. The first time, right-click it → **Open** → **Open** (the app is not notarised by Apple).
3. **Windows:** double-click **CapyRunner-Setup-x64.exe** → **Next** → **Install**. No administrator password is needed.
   You can tick *Start CapyRunner when I sign in* and *Add a shortcut to my desktop*. Afterwards it is in the Start menu,
   and you can remove it in *Settings → Apps* like any other app.
   If Windows shows a blue "Windows protected your PC" box, click **More info** → **Run anyway** (the app is not code-signed).
   Capy appears in the tray next to the clock; drag it out of the `^` overflow to keep it visible.
   (Portable zip: right-click → **Extract All** → open the folder → double-click **CapyRunner.exe**.)
4. **Linux:** extract the file, open the `CapyRunner` folder and run the `CapyRunner` program inside
   (terminal: `tar -xzf CapyRunner-linux-x86_64.tar.gz && ./CapyRunner/CapyRunner`).

**Updates:** once a day CapyRunner looks for a new release. On Windows (installed with the setup) Primo tells you,
and *right-click → Update* downloads it, checks it, installs it silently and starts the new version, about a minute,
with your tasks, notes and settings kept. Elsewhere it opens the download page. Turn it off in Settings → *About*.
(This only reads GitHub's public release page, so the repository has to be public for it to work.)

The Windows build only carries the parts of Qt it uses (no web engine, PDF, QML or software OpenGL), so it is a small
download and stays light while it runs.

The sections below are for installing from the source code instead.

## Primo joins in with what you are doing
| You are… | Primo… |
|---|---|
| 🎧 listening to music | sits on the right side with headphones on, and his mood follows the song: happy, hype (head-banging), chill, sad (a tear) or in love (hearts) |
| 📱 watching a video | gets cosy with a pillow, a blanket, headphones and his phone |
| 🍿 watching a movie (fullscreen, mpv/VLC, Netflix…) | sits down with popcorn |
| 📝 watching a tutorial, podcast or discussion | puts on glasses, sits up straight and takes notes |
| 📖 reading a PDF / e-book | puts on glasses and reads a book (with headphones if music is on) |

- A small line above him shows the mode icon and what is playing. Click him for the full title.
- He guessed wrong? Right-click him → *When something plays* and pick the mode yourself.
  Settings → *Take notes for* lets you list channels or words that always count as a tutorial/podcast.
- Right-click him → control panel: play/pause, next, previous, and a volume slider (system output volume).
- Speech bubbles stay on the screen and shrink to fit the text; the text size is in Settings.
- Turn it all off in Settings → *Joins in*.

- **Windows 10/11:** what is playing comes from the system media controls (the same list as the volume pop-up:
  Spotify, Chrome, Edge, Firefox, the Media Player…), and the window in front from Windows itself.
- **Linux:** music and video need `playerctl` (Spotify, browsers, mpv, VLC…), volume uses `wpctl` or `pactl`, and the
  window in front (reading, video in front) is detected on Hyprland (and X11 for work modes).
- **macOS:** Spotify and Apple Music (only while they are open; macOS asks once if CapyRunner may see them).
The mood and the tutorial/podcast guess come from the words in the title, artist/channel and genre; nothing analyses the sound.

## New in 0.5.0
### 🐉 Rides across the screen
Now and then (every 40 minutes, you choose) Primo rides an animal from one side of the screen to the other:
a **dragon** 🐉, an **eagle** 🦅 or a **parrot** 🦜 fly near the top, a **lion** 🦁, a **tiger** 🐅 or a **wolf** 🐺 run
along the bottom, and a **whale** 🐋 swims past on a strip of sea. The ride ignores the mouse and the keyboard, so you can
keep clicking and typing right through it. There are no rides during calls, films, full-screen apps (games, slides),
focus time or work modes. Right-click Primo → *Ride a…* → **Ride!** for one now. Settings → *Rides & fun* lets you choose
the animals, their colours and how often.

### 🎭 Avatars: Primo, Jeo, Geelee, Koko, Luna, Tito… or your own
Right-click Primo → **🎭 Avatar** to choose who runs on your screen and who comes round for the dance showdowns.
Pick one of the ready-made friends (Primo, Jeo OngBack, Geelee with her bow, Koko with his cap, Luna with a flower,
Tito with a crown), then change the name, fur colour, jacket colour and headwear (bandana, bow, flower, cap,
crown or nothing), with a live preview. The avatar on screen also rides the animals, and the dance friend can ride
along behind.

### 🎵 He dances to the mood of the song
Upbeat songs start a hip-hop, budots or K-pop showdown, happy ones disco, and love songs *Touch by Touch* or a
top-hat tap-off. Sad and chill songs get the quiet listening pose. Works on Windows and macOS now too.

### ☕ Coffee, clothes and colours
- Some naps after a lap become a **coffee break** with a steaming cup. Right-click → **☕ Coffee** for one now.
- Right-click → **👕 Jacket** and **🥤 Cup** to change their colours. Settings → *Look & place → Wardrobe* also lets him
  keep your jacket colour on adventure days.

### ⬆ Updates, macOS, lighter
- Automatic update check (see *Download* above). The About window says **Developed by Devjr**, and so do the Windows
  installer and the program's file details.
- A **macOS** build (Apple silicon), with start-at-login.
- Lighter for running all day: while he sits (calls, work, music) he redraws about half as often, and the dance
  pictures he keeps in memory are capped, so memory stays flat after days of running.

## New in 0.4.0

### 💻 Work modes: Primo at his desk while you work
When you work in **Articulate Storyline**, Primo sits down on an **office chair** with his **laptop** and types along with
you. Now and then he stops for an idea 💡 and smiles when it works.

- It is called **"Storyline time"** to start with, and everything about it can be changed in Settings → **Work modes**:
  - **Name** and **icon** (shown in the small line above him: `💻 Storyline time · Articulate Storyline`)
  - **Apps**: words from the program name or window title (`Articulate Storyline, Storyline 360, Storyline.exe`).
    **Pick…** lists the windows open right now so you can choose one.
  - **On**: while the app is the window in front, or while it is open at all
  - **Days**: Monday to Friday to start with; tick any days, or use *Mon–Fri* / *Every day*
  - **He wears**: his own hoodie, office clothes (blazer, tie, headset), or the outfit of the day's adventure
  - **Chair colour**, **glasses**, and **what he says** when the mode starts (`{mode}`, `{app}`, `{name}`)
  - A live preview shows how it looks
- **+ Add mode** makes more: *Coding* for VS Code, *Design* for Figma, *Rise 360*… **Copy** and **Remove** too.
  Untick a mode in the list to pause it.
- He keeps sitting for 45 seconds after you switch away, so a quick look at your email does not end it.
- A call wins over a work mode, and a work mode wins over music and videos. No dance showdowns while you work.
- Works on Windows 10 / 11 (window in front, from Windows itself), Linux on Hyprland, and Linux X11 with `xdotool`.
  Only the program name and window title are compared; nothing is kept or sent.

### 📍 Where he sits, and how big he is
Settings → **Look & place** (also in the right-click panel and the tray menu):
- **He sits** for calls, work modes, music, videos and reading: *on the right*, *on the left*, *in the middle*,
  or *right where he is*.
- **Screen**: the screen he is on, or always the main screen (he hops over with a puff of smoke).
- **Raise him by**: lift his running line and his seat above the bottom edge (clear of the taskbar or a dock).
- **Height** and **Width** separately: make him taller, slimmer or wider. *As drawn* puts the width back.
- Want him to stay in one place? Turn off *Run around the screen* and drag him there.

### 🎨 App themes
Choose how the windows, menus and Primo's speech bubbles look: **System**, **Light**, **Dark**, **Capytech**
(warm cream and orange), **Ocean night**, **Forest**, **Sakura pink** or **Taco fiesta**. They look the same on
Windows 10, Windows 11 and Linux. Settings → *Look & place*, the right-click panel, or the tray menu → *App theme*.

### 🪟 Windows
- **Calls are detected on Windows too**: a meeting window (Zoom Meeting, Google Meet, Teams meeting, Webex…) or a
  meeting app or browser using the microphone. He puts on his office clothes and headset. (Moving his mouth when you speak
  is still Linux only.)
- Smoother running (precise timers), its own name on Windows notifications, and *Start when I log in* matches what you
  ticked in the installer.

## A different adventure every weekday

Primo's lap around the screen changes with the day, and the five days tell one story: the fiesta lantern needs a real star.

| Day | Adventure | What you see |
| --- | --- | --- |
| Monday | 🏃 Training day | The classic lap: run, climb the rope, tiptoe along the top, slide down, nap. |
| Tuesday | 🏔️ Mountain hike | Red jacket, bobble hat, backpack and walking stick. He climbs a climbing rope, walks the ridge and plants a flag on the summit, where he spots the star. |
| Wednesday | 🚀 Space mission | Space suit and helmet. On the right edge he boards a rocket (countdown, lift-off), floats along the top in zero gravity, catches the star, and comes down the left side under a parachute. |
| Thursday | 🌴 Jungle treasure hunt | Explorer hat and satchel. The rope is a vine; he sneaks past a sleeping jaguar and finds the star that fell. |
| Friday | 🎉 Fiesta Friday | Party hat and garland, carrying the star on a pole. The rope is a string of flags; at the top he hangs the star lantern. Then tacos. |
| Weekend | 🏃 Rest days | The classic lap. |

- The outfit stays on for everything else too (music, videos, reading, breathing, focus).
- Choose another one any time: right-click Primo → *Today's adventure*, or the tray menu. *Follow the weekday* goes back to the plan.
- Settings → *Adventures* sets which adventure belongs to which day, and turns the story lines off.
- At midnight he changes into the next day's outfit by himself.
- The adventures are for Primo; the other characters always do the classic lap. On hiking, space and jungle days the outfit colour replaces the hoodie colour.

## Jeo OngBack and the dance showdowns

Primo has a friend: **Jeo OngBack**, a capybara with a red bandana tied round his head. He runs in from the left,
the two take turns showing a move, then they dance together and one of them wins (or it is a tie). Then Jeo runs home.

| A showdown starts… | |
| --- | --- |
| 🎵 when a dance song is playing | They keep dancing together for as long as the song lasts. |
| ⏰ every 30 minutes | Jeo turns up and challenges Primo (you choose how often, or never). Not during a call, a film, a video, reading, focus or "Do not disturb". |
| 🕺 when you ask | Right-click Primo → *Dance showdown with Jeo*, the tray menu, or `capyrunner --dance` (bind it to a key). The same again stops it. |

- **100 dance moves.** Moonwalk, floss, dab, robot, the worm, backflip, cartwheel, headspin, sprinkler, cha-cha, can-can,
  otso-otso, budots… Every turn is two moves, and no move comes twice in one showdown. Whoever dances shouts its name.
  Each move is one line in `capyrunner/dance.py` (an arm pattern + a leg pattern + a body pattern), so adding your own is easy.
- **💞 Touch by Touch.** When Joy's *Touch by Touch* is playing (or from the menu: *Touch by Touch*, or `capyrunner --touch`)
  there is no contest. Both change into sequin jackets and gold chains, Jeo dances a show-off solo (flips, spins, moonwalk),
  then Primo joins him for the slow duet: hip sways, body rolls, winks and hearts, for as long as the song lasts.
- **Every challenge has a style, and they change clothes for it like magicians**: a puff of smoke and stars, and both
  are in the outfit; another puff at the end and they are back in their own clothes.

  | Style | Outfit | Picked when the song says |
  | --- | --- | --- |
  | 🧢 Hip-hop battle | snapback caps and gold chains | hip hop, rap, trap, phonk… |
  | 🪩 Disco fever | pink shades, purple and gold | disco, funk, retro, 80s… |
  | 😎 Budots showdown | bandanas and dark shades, neon | budots, sayaw, TikTok mashup… |
  | 🎤 K-pop stage | pastel hoodies and headset mics | k-pop and the big group names |
  | 🎩 Top-hat tap-off | top hats and bow ties | swing, jazz, tango, ballroom… |

  With no song (or none of those words) the style is drawn at random, never the same as last time.
- A "dance song" is decided from the title and artist, nothing listens to the sound: dance words (*dance, sayaw, budots,
  zumba, TikTok mashup…*) plus the dance-challenge songs going round in late 2026 (*Hawak Mo ang Beat*, *Motion Party*,
  *Dame Hombro*, *Sey Mami*, *BbY WOW*, *Hideaway*, Tyla's *CHANEL*, *You Spin Me Round*…) and *Pinoy Ako*.
  That list goes out of date: add your own under Settings → *Friend & dance* → *My dance songs*, or edit `capyrunner/dance.py`.
- Song detection uses the same `playerctl` as "Joins in", so it is Linux only for now and needs *Joins in* switched on.
- Settings → *Friend & dance* also changes his name and turns him off. Jeo cannot be clicked or dragged.
- **Space day:** once a day Primo invites Jeo along. Jeo runs over and climbs in (the rocket gets a second window),
  floats beside Primo in orbit in his own space suit, parachutes down next to him and runs home.
- Jeo's window has the same title as the pet's (`CapyRunner`), so compositor rules written for the pet (no border,
  no blur, no dim) cover him as well.

## Primo joins your calls

When you are in a call, Primo sits down at the side, and with a puff of smoke he is in office clothes: blazer, shirt
and tie, a headset with a microphone, a laptop on his lap. He listens and nods. **When you speak, he speaks**:
his mouth moves, one paw explains, sound comes out of the microphone. When the call ends he changes back.

- A call is: a meeting window is open (Google Meet, Zoom, Teams, Webex, Jitsi…; found on Hyprland), or a meeting app
  or a browser is using the microphone (found through `pactl`, on any Linux desktop).
- "You speak" is measured from the loudness of the default microphone, only during a call. Each 50 ms of sound becomes
  one number and is thrown away: nothing is recorded, saved or sent. Your desktop may show its "microphone in use" sign.
- It follows the system microphone. If you mute only inside the meeting app, Primo still moves his mouth when you talk;
  mute the system microphone and he is quiet too.
- No dance challenges, break reminders or story lines while you are in a call.
- Settings → *Behaviour* has both switches (the office look, and listening to the microphone). Linux only for now.

## Primo looks after you (wellbeing)

Right-click Primo (or use the tray menu) to open his control panel. Everything below is there.

| What | How it works |
| --- | --- |
| 🌿 **Breathe with Primo** | Primo fills up and lets go slowly, and you breathe with him: two short breaths in through the nose, one long breath out ("cyclic sighing"). 1 to 5 minutes. Click him to stop. |
| 🙆 **Break reminders** | After 50 minutes at the screen (you choose) Primo stretches and asks you to stand up. He asks once, never during a call or a fullscreen video, and cheers when you come back. Leaving the keyboard for 3 minutes counts as a break. |
| 🎯 **Focus session** | Pick a task and a length (25 or 50 minutes are good). Primo puts his glasses on and works beside you with a countdown. Notifications wait until the end, then he gives you a break (5 min, or 10 after a long session). Click him afterwards to tick the task. |

- Nothing about your time at the keyboard is saved or sent anywhere.
- Break reminders are quiet while "Do not disturb" is on.
- Keyboard shortcuts: bind `capyrunner --breathe` and `capyrunner --focus` to any key; each one starts or stops.
- Linux with Hyprland sees typing and the mouse (through a private `hypridle`); on Windows it uses the system idle time; elsewhere only mouse movement is seen.
- During focus, other apps' pop-ups are held too when the notification daemon is `mako`. Turn this off with "Focus also silences other apps' pop-ups".

## Features
- **Tasks** with due dates, reminders, notes per task, snooze 10 min
- **Quick add** in plain language: `Call Jason in 30m`, `Standup @9:30`, `Report tomorrow @14`
- **Notes** (first line = title, autosaves)
- **Notifications inbox** + desktop pop-ups (Do-Not-Disturb toggle)
- **Customisable runner**: Capy (hoodie colour adjustable), simple capybara, cat, dog, dots — or your own
- **Speed source**: tasks + notifications + CPU (mix), tasks only, or CPU only (classic RunCat)
- **Webhook** so other systems (CapyWatcher, CI, LMS cron, scripts) can make Capy jump
- Start on login, single instance, data stored as plain JSON

## Install on Linux
```bash
unzip capyrunner.zip && cd capyrunner
chmod +x install.sh uninstall.sh
./install.sh
```
The installer:
1. offers to install missing system packages with `sudo apt` (`python3-venv libxcb-cursor0 libegl1 libxkbcommon-x11-0 libnotify-bin`)
2. creates a private virtualenv in `~/.local/share/capyrunner`
3. adds `capyrunner` to `~/.local/bin`, an app-menu entry, and (optionally) autostart
4. launches it

Run later from the app menu or with `capyrunner`. Uninstall: `./uninstall.sh` (add `--purge` to delete your data).

**GNOME note:** stock GNOME hides tray icons. Install *AppIndicator and KStatusNotifierItem Support*
(`sudo apt install gnome-shell-extension-appindicator`, then log out/in) to see Capy in the top bar.
Without it, Capy still runs as the floating pet. Ubuntu ships this extension already.

**Wayland note:** the launcher uses XWayland when available so the pet stays on top and remembers its position.
Set `CAPYRUNNER_WAYLAND=1` to force native Wayland.

## Install on Windows
Install Python 3.9+ from python.org (tick *Add python.exe to PATH*), then double-click `install-windows.bat`.
Drag Capy out of the `^` tray overflow onto the taskbar to keep it visible.
Or use the ready-built `.zip` from the [latest release](https://github.com/jrorias/capyrunner/releases/latest) (see *Download* above), with no Python needed.

## Using it
- **Left-click** tray icon → open Tasks / Notes / Notifications. **Middle-click** → quick add.
- **Right-click the pet** → Primo's control panel: tasks, media and volume, how he joins in, the main switches,
  and a **Close** button (Esc also closes it). `capyrunner --controls` opens it too, handy for a keyboard shortcut.
- **Right-click the tray icon** → menu (character, speed source, DND, settings, quit).
- **Click** the pet → Capy says hi / tells you what's pending. **Double-click** → open the panel.
- The pet **never takes your typing**: you can click, pat and drag it, and the keyboard stays with the window you were
  working in. Scroll over it and it steps aside so the scroll reaches the page underneath (Hyprland).
  Tick *Ghost mode* in the menu if you want clicks to pass straight through it as well.
- **Drag** the pet to another height or screen; it keeps running on that line. Turn running off with
  right-click → *Run around the screen* (then it stays where you drop it).

## Custom characters
Settings → Character → **Custom**, then pick:
- an **animated GIF / WebP**
- a **sprite sheet PNG**: frames side by side, left to right. Square frames are auto-detected, otherwise set *Sprite frames*.
  See `examples/example-sprite-sheet-10-frames.png`.
- a **folder of PNGs**: `run01.png, run02.png…` plus optional `jump01.png…` (played on new notifications)
  and `sleep01.png…` (played when idle). Transparent backgrounds look best.

## Webhook (send notifications from anything)
Enable in Settings (default port 8765, bound to 127.0.0.1 only; optional token).
```bash
curl -X POST http://127.0.0.1:8765/notify \
  -H 'Content-Type: application/json' -H 'X-Token: yourtoken' \
  -d '{"title":"LMS backup done","body":"learn.capytech.co.uk","source":"cron"}'

# or from the CLI
capyrunner --notify "Deploy finished" "Siraj LMS updated"
```

## Data
`~/.config/CapyRunner/` on Linux, `%APPDATA%\CapyRunner\` on Windows, `~/Library/Preferences/CapyRunner/` on macOS. Contains `settings.json` and `data.json` (tasks, notes, notifications).

## Development
```bash
./run-dev.sh            # runs from source with a local .venv
```
Code layout: `capyrunner/characters.py` (drawn animations: Capy is `_capy()`), `app.py` (tray, pet, timers),
`activity.py` (music / video / reading detection), `rides.py` (the animals Primo rides), `updater.py` (update check),
`workmode.py` (work modes: Storyline and your apps), `winwatch.py`
(Windows windows and microphone), `meeting.py` (calls), `uitheme.py` (app themes), `panel.py` (tasks/notes/notifications UI),
`settings_dialog.py`, `webhook.py`, `quickadd.py`, `store.py`. The Windows installer is `packaging/capyrunner.iss` (Inno Setup).

## GitHub builds
`.github/workflows/build.yml` builds standalone Linux (`.tar.gz`), Windows (`.zip` + `CapyRunner-Setup-x64.exe`) and
macOS (`.zip` with `CapyRunner.app`) apps with PyInstaller and Inno Setup on every push to `main`, and test-starts the
Windows and macOS builds. Push a tag to publish a Release:
```bash
git tag v0.5.0 && git push origin v0.5.0
```

## Roadmap ideas
ClickUp tasks/alerts sync · global hotkey for quick add · more Capy moods (celebrate when all tasks done, worried when overdue) ·
team notifications via a small server · Tauri rewrite for a smaller download.
