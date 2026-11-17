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

Works on **Linux** (GNOME, KDE, XFCE, Cinnamon…) and **Windows 10/11**.

## Download (the easy way, no setup needed)
This repository is private, so you need a GitHub account that has been invited to it. Sign in first.

1. Open the **[latest release](https://github.com/jrorias/capyrunner/releases/latest)**.
2. Under **Assets**, click the file for your computer:
   - **Windows:** `CapyRunner-windows-x64.zip`
   - **Linux:** `CapyRunner-linux-x86_64.tar.gz`
3. **Windows:** right-click the downloaded zip → **Extract All** → open the extracted folder → double-click **CapyRunner.exe**.
   If Windows shows a blue "Windows protected your PC" box, click **More info** → **Run anyway** (the app is not code-signed).
   Capy appears in the tray next to the clock; drag it out of the `^` overflow to keep it visible.
4. **Linux:** extract the file, open the `CapyRunner` folder and run the `CapyRunner` program inside
   (terminal: `tar -xzf CapyRunner-linux-x86_64.tar.gz && ./CapyRunner/CapyRunner`).

To update later, download the newest release the same way and replace the old folder. Your tasks and notes are kept.

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

Linux only for now: music and video need `playerctl` (works with Spotify, browsers, mpv, VLC…), volume uses
`wpctl` or `pactl`, and the focused window (reading, video in front) is detected on Hyprland.
The mood and the tutorial/podcast guess come from the words in the title, artist/channel and genre; nothing analyses the sound.

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
`~/.config/CapyRunner/` on Linux, `%APPDATA%\CapyRunner\` on Windows. Contains `settings.json` and `data.json` (tasks, notes, notifications).

## Development
```bash
./run-dev.sh            # runs from source with a local .venv
```
Code layout: `capyrunner/characters.py` (drawn animations: Capy is `_capy()`), `app.py` (tray, pet, timers),
`activity.py` (music / video / reading detection), `panel.py` (tasks/notes/notifications UI), `settings_dialog.py`, `webhook.py`, `quickadd.py`, `store.py`.

## GitHub builds
`.github/workflows/build.yml` builds standalone Linux (`.tar.gz`) and Windows (`.zip`) apps with PyInstaller on every
push to `main`. Push a tag to publish a Release:
```bash
git tag v0.2.0 && git push origin v0.2.0
```

## Roadmap ideas
ClickUp tasks/alerts sync · global hotkey for quick add · more Capy moods (celebrate when all tasks done, worried when overdue) ·
team notifications via a small server · Tauri rewrite for a smaller download.
