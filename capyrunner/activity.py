"""What is the user doing right now? Listening to music, watching a video, or reading.

- Linux: media from MPRIS (via `playerctl`), the focused window from Hyprland (`hyprctl`).
- Windows 10/11: media from the system media controls (the same list as the volume pop-up: Spotify, browsers,
  the Media Player…) through WinRT, else from the Spotify window title; the window in front through Win32.
- macOS: Spotify and Apple Music through AppleScript (only when they are running), the front app via lsappinfo.
Everything is best effort: when something is missing the answer is simply "nothing".
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass

MUSIC_PLAYERS = ("spotify", "spotifyd", "ncspot", "spotube", "rhythmbox", "mpd", "mopidy", "strawberry", "clementine",
                 "elisa", "amberol", "lollypop", "cmus", "audacious", "tidal", "deezer", "cider", "musikcube",
                 "quodlibet", "gnome-music", "shortwave", "tauon", "feishin", "supersonic", "psst", "youtube-music",
                 "media player", "apple music", "itunes", "amazon music", "musicbee", "foobar2000", "winamp", "aimp")
VIDEO_PLAYERS = ("mpv", "vlc", "celluloid", "totem", "haruna", "kodi", "smplayer", "showtime", "clapper", "jellyfin",
                 "plex", "stremio", "freetube")
BROWSERS = ("chromium", "chrome", "firefox", "brave", "edge", "vivaldi", "opera", "zen", "librewolf", "floorp",
            "epiphany", "helium", "thorium")
AUDIO_EXT = (".mp3", ".flac", ".ogg", ".opus", ".m4a", ".wav", ".aac", ".wma")
MUSIC_SITES = ("music.youtube", "youtube music", "spotify", "soundcloud", "bandcamp", "deezer", "tidal",
               "music.apple", "apple music", "pandora", "last.fm", "mixcloud", "audiomack", "radio")
MUSIC_WORDS = ("lyrics", "lyric video", "official audio", "(audio)", "[audio]", "playlist", "lofi", "lo-fi", " mix",
               "radio", "instrumental", "karaoke", "album", "soundtrack", " ost", "songs", "music")
READER_APPS = ("zathura", "evince", "okular", "calibre", "ebook-viewer", "foliate", "papers", "xreader", "atril",
               "mupdf", "sioyek", "koreader", "bookworm", "komikku", "mcomix", "thorium-reader", "readest")
READ_WORDS = (".pdf", ".epub", ".mobi", ".cbz", "kindle", "play books", "wattpad", "webtoon", "pdf viewer",
              "document viewer", "docviewer")

# Videos you learn from (tutorial, podcast, discussion): Primo takes notes instead of lounging.
STUDY_WORDS = ("tutorial", "how to", "how-to", "course", "lesson", "lecture", "podcast", "explained", "explain",
               "guide", "learn", "interview", "discussion", "discuss", "talk", "crash course", "walkthrough",
               "tips", "webinar", "conference", "keynote", "masterclass", "workshop", "training",
               "review", "analysis", "deep dive", "documentary", "debate", "q&a", "sermon", "preaching",
               "bible study", "ted talk", "tedx", "beginner", "step by step", "introduction to", "intro to", "what is", "why ")
STUDY_STRONG = ("podcast", "interview", "lecture", "audiobook", "sermon", "episode")   # even in a music app
MOVIE_WORDS = ("netflix", "prime video", "disney+", "hbo", "crunchyroll", "viu", "iwanttfc", "full movie",
               "trailer", "plex", "jellyfin", "anime")
KINDS = ("listen", "watch", "movie", "study", "read")

# Mood is guessed from the words in the title / artist / album / genre. It does not listen to the audio.
MOODS = {
    "sad": ("sad", "cry", "tears", "lonely", "alone", "broken", "heartbreak", "goodbye", "miss you", "hurt", "sorry",
            "blues", "pain", "without you", "let go", "paalam", "sakit", "luha", "melanchol"),
    "love": ("love", "heart", "kiss", "baby", "forever", "darling", "valentine", "romance", "romantic", "mahal",
             "ikaw", "pag-ibig", "crush", "wedding"),
    "hype": ("rock", "metal", "remix", "edm", "dance", "party", "bass", "hype", "workout", "trap", "phonk", "drum",
             "punk", "dubstep", "techno", "house", "hardstyle", "rave", "gym", "hip hop", "hip-hop", "rap", "k-pop",
             "kpop", "budots"),
    "chill": ("lofi", "lo-fi", "chill", "relax", "sleep", "calm", "piano", "acoustic", "jazz", "ambient", "study",
              "rain", "meditation", "focus", "classical", "worship", "praise", "hymn", "instrumental", "bossa"),
}
MOOD_ORDER = ("happy", "hype", "chill", "sad", "love")     # index = the k passed to the "listen" pose


@dataclass(frozen=True)
class Activity:
    kind: str = ""            # "" | listen | watch (cosy, on the phone) | movie (popcorn) | study (notes) | read
    title: str = ""
    artist: str = ""
    mood: str = "happy"
    music: bool = False       # music is on in the background (reading with headphones)

    def __bool__(self) -> bool:
        return bool(self.kind)

    @property
    def label(self) -> str:
        if not self.title:
            return ""
        return f"{self.title} — {self.artist}" if self.artist else self.title


def guess_mood(*texts: str) -> str:
    text = " " + " ".join(t for t in texts if t).lower() + " "
    best, score = "happy", 0
    for mood in ("sad", "love", "hype", "chill"):
        n = sum(1 for w in MOODS[mood] if w in text)
        if n > score:
            best, score = mood, n
    return best


def _run(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=1).stdout
    except Exception:
        return ""


def _active_window() -> tuple[str, str, bool]:
    """(class / program, title, fullscreen) of the focused window, lower-cased."""
    if sys.platform == "win32":
        from . import winwatch
        prog, title = winwatch.foreground()
        return prog, title, winwatch.fullscreen()
    if sys.platform == "darwin":
        return _mac_front(), "", False
    if not os.environ.get("HYPRLAND_INSTANCE_SIGNATURE"):
        return "", "", False
    try:
        w = json.loads(_run("hyprctl", "activewindow", "-j") or "{}")
    except ValueError:
        return "", "", False
    return str(w.get("class", "")).lower(), str(w.get("title", "")).lower(), bool(w.get("fullscreen"))


# --- Windows: the system media controls (GlobalSystemMediaTransportControls) --- #
_WIN_APPS = {"308046b0af4a39cb": "firefox", "msedge": "edge", "zunemusic": "media player", "microsoft.zunemusic": "media player"}


async def _gsmtc() -> list[dict]:
    from winrt.windows.media.control import (GlobalSystemMediaTransportControlsSessionManager as Manager,
                                             GlobalSystemMediaTransportControlsSessionPlaybackStatus as Status)
    out = []
    mgr = await Manager.request_async()
    for ses in mgr.get_sessions():
        info = ses.get_playback_info()
        if info is None or info.playback_status != Status.PLAYING:
            continue
        props = await ses.try_get_media_properties_async()
        app = str(ses.source_app_user_model_id or "").lower()
        app = next((v for k, v in _WIN_APPS.items() if k in app), app)
        genres = " ".join(str(g) for g in (props.genres or [])) if props else ""
        out.append({"player": app, "status": "Playing", "title": (props.title if props else "") or "",
                    "artist": (props.artist if props else "") or "", "album": (props.album_title if props else "") or "",
                    "url": "", "genre": genres})
    return out


_winrt = {"ok": True, "busy": False, "last": []}


def _winrt_refresh() -> None:
    """Runs in its own thread: WinRT wants its own COM apartment (Qt's main thread has another one),
    and the answer can take a moment, which must never make Primo stutter."""
    import asyncio
    try:
        _winrt["last"] = asyncio.run(asyncio.wait_for(_gsmtc(), 2.0))
    except ImportError:
        _winrt["ok"] = False                      # not installed: use window titles from now on
    except Exception:
        _winrt["last"] = []
    finally:
        _winrt["busy"] = False


def _win_players() -> list[dict]:
    if _winrt["ok"]:
        if not _winrt["busy"]:                    # ask again in the background; answer with the last result
            import threading
            _winrt["busy"] = True
            threading.Thread(target=_winrt_refresh, daemon=True, name="capy-media").start()
        return list(_winrt["last"])
    from . import winwatch                         # Spotify shows "Artist - Song" as its title while playing
    out = []
    for prog, title in winwatch.windows():
        if prog == "spotify.exe" and " - " in title and not title.startswith("spotify"):
            artist, _, song = title.partition(" - ")
            out.append({"player": "spotify", "status": "Playing", "title": song, "artist": artist,
                        "album": "", "url": "", "genre": ""})
    return out


# --- macOS: Spotify and Apple Music through AppleScript --------------------- #
def _mac_front() -> str:
    asn = _run("lsappinfo", "front").strip()
    line = _run("lsappinfo", "info", "-only", "name", asn) if asn else ""
    return line.split("=", 1)[1].strip().strip('"').lower() if "=" in line else ""


def _mac_players() -> list[dict]:
    try:
        import psutil
        running = {p.info["name"] for p in psutil.process_iter(["name"])}
    except Exception:
        return []
    out = []
    for app, proc in (("Spotify", "Spotify"), ("Music", "Music")):
        if proc not in running:                      # never start an app just by asking it
            continue
        script = (f'tell application "{app}" to if player state is playing then '
                  'return (name of current track) & tab & (artist of current track) & tab & (album of current track)')
        parts = _run("osascript", "-e", script).rstrip("\n").split("\t")
        if len(parts) == 3 and parts[0]:
            out.append({"player": app.lower() if app == "Spotify" else "apple music", "status": "Playing",
                        "title": parts[0], "artist": parts[1], "album": parts[2], "url": "", "genre": ""})
    return out


def _players() -> list[dict]:
    if sys.platform == "win32":
        return _win_players()
    if sys.platform == "darwin":
        return _mac_players()
    if not shutil.which("playerctl"):
        return []
    fmt = "\t".join("{{%s}}" % f for f in ("playerName", "status", "title", "artist", "album", "xesam:url", "xesam:genre"))
    out = []
    for line in _run("playerctl", "-a", "metadata", "--format", fmt).splitlines():
        parts = line.split("\t")
        if len(parts) == 7 and parts[1] == "Playing":
            out.append(dict(zip(("player", "status", "title", "artist", "album", "url", "genre"), parts)))
    return out


def _has(text: str, words) -> bool:
    return any(w in text for w in words)


def _media_kind(p: dict, wclass: str, wtitle: str, fullscreen: bool, study_words) -> str:
    player, url, title = p["player"].lower(), p["url"].lower(), p["title"].lower()
    words = f" {title} {p['artist'].lower()} {p['album'].lower()} "
    if _has(player, MUSIC_PLAYERS):
        return "study" if _has(words, STUDY_STRONG) else "listen"
    if _has(player, VIDEO_PLAYERS):
        if url.endswith(AUDIO_EXT):
            return "listen"
        return "study" if _has(words, study_words) else "movie"
    if _has(player, BROWSERS):
        if _has(words, study_words):
            return "study"                    # a tutorial / podcast, in front or in the background
        if _has(url, MUSIC_SITES) or _has(title, MUSIC_WORDS):
            return "listen"
        # a video you are looking at: the browser is in front and showing the tab that is playing
        in_front = _has(wclass, BROWSERS) and title[:24] and title[:24] in wtitle
        if in_front and not _has(wtitle, MUSIC_SITES):
            return "movie" if (fullscreen or _has(wtitle, MOVIE_WORDS)) else "watch"
        return "listen"                       # playing in a background tab: you are listening to it
    return "listen"


def detect(extra_study_words=()) -> Activity:
    study_words = STUDY_WORDS + tuple(str(w).lower() for w in extra_study_words if str(w).strip())
    wclass, wtitle, fullscreen = _active_window()
    reading = _has(wclass, READER_APPS) or _has(wtitle, READ_WORDS)
    best: Activity | None = None
    for p in _players():
        kind = _media_kind(p, wclass, wtitle, fullscreen, study_words)
        act = Activity(kind, p["title"].strip(), p["artist"].strip(),
                       guess_mood(p["title"], p["artist"], p["album"], p["genre"]), kind == "listen")
        if kind in ("watch", "movie", "study"):
            return act                        # something on screen wins over background music
        best = best or act
    if reading:
        return Activity("read", best.title if best else "", best.artist if best else "",
                        best.mood if best else "happy", bool(best))
    return best or Activity()


# --------------------------------------------------------------------------- #
# media keys and volume (system output volume through PipeWire's wpctl, or pactl)
# --------------------------------------------------------------------------- #
def media(cmd: str) -> None:
    """cmd: play-pause | next | previous"""
    if sys.platform == "win32":
        from . import winwatch
        winwatch.media_key(cmd)
        return
    if sys.platform == "darwin":
        for app in ("Spotify", "Music"):
            verb = {"play-pause": "playpause", "next": "next track", "previous": "previous track"}.get(cmd, "")
            if verb:
                _run("osascript", "-e", f'if application "{app}" is running then tell application "{app}" to {verb}')
        return
    if shutil.which("playerctl"):
        _run("playerctl", cmd)


def get_volume() -> tuple[int, bool] | None:
    """(percent, muted) of the default output, or None when it cannot be read."""
    if shutil.which("wpctl"):
        out = _run("wpctl", "get-volume", "@DEFAULT_AUDIO_SINK@")       # "Volume: 0.45 [MUTED]"
        try:
            return round(float(out.split()[1]) * 100), "MUTED" in out
        except (IndexError, ValueError):
            return None
    if shutil.which("pactl"):
        out = _run("pactl", "get-sink-volume", "@DEFAULT_SINK@")
        muted = "yes" in _run("pactl", "get-sink-mute", "@DEFAULT_SINK@")
        for part in out.split():
            if part.endswith("%"):
                try:
                    return int(part[:-1]), muted
                except ValueError:
                    pass
    return None


def set_volume(percent: int) -> None:
    percent = max(0, min(100, int(percent)))
    if shutil.which("wpctl"):
        _run("wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@", f"{percent / 100:.2f}")
    elif shutil.which("pactl"):
        _run("pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{percent}%")


def toggle_mute() -> None:
    if shutil.which("wpctl"):
        _run("wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle")
    elif shutil.which("pactl"):
        _run("pactl", "set-sink-mute", "@DEFAULT_SINK@", "toggle")
