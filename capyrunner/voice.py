"""Primo and Jeo speak: their speech bubbles read out loud, each in their own voice.

Natural voices come from Piper (https://github.com/rhasspy/piper): small neural voices that run on this
computer, with no internet once a voice is downloaded and nothing sent anywhere. Each voice is a ~60 MB file
kept in the data folder. Without Piper the system voice is used (Windows speech, macOS `say`,
`spd-say` / `espeak-ng` on Linux), which sounds more robotic.

Every character has a voice, a pitch and a speed. Pitch is changed by playing the sound a little faster
while the voice speaks a little slower, so the speed stays what you chose and only the pitch moves.
"""
from __future__ import annotations

import io
import os
import queue
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import unicodedata
import urllib.request
import wave

from PySide6.QtCore import QObject, Signal

from .store import config_dir

VOICES = {
    "en_US-ryan-medium": "Ryan · warm and friendly (US)",
    "en_US-joe-medium": "Joe · easy-going (US)",
    "en_US-bryce-medium": "Bryce · young and lively (US)",
    "en_US-kusal-medium": "Kusal · upbeat (US)",
    "en_US-john-medium": "John · relaxed (US)",
    "en_US-norman-medium": "Norman · deep storyteller (US)",
    "en_US-hfc_male-medium": "Hal · clear (US)",
    "en_US-sam-medium": "Sam · soft (US)",
    "en_US-lessac-medium": "Lessac · bright and clear (US)",
    "en_US-amy-medium": "Amy · cheerful (US)",
    "en_US-kristin-medium": "Kristin · gentle (US)",
    "en_US-hfc_female-medium": "Hannah · crisp (US)",
    "en_GB-alan-medium": "Alan · calm (British)",
    "en_GB-northern_english_male-medium": "Northern · cosy (British)",
    "en_GB-cori-medium": "Cori · warm (British)",
    "en_US-ryan-high": "Ryan HD · best quality, a bit slower to start (US)",
}
SYSTEM = "system"          # the computer's own voice

DEFAULTS = {
    "main": {"voice": "en_US-ryan-medium", "pitch": 1.10, "speed": 1.0},
    "friend": {"voice": "en_US-bryce-medium", "pitch": 1.18, "speed": 1.08},
}

SAMPLE = {"main": "Hi! I'm {name}. Time for a little break: stand up and stretch with me!",
          "friend": "Yo! It's {name}. Ready for a dance battle? Let's go!"}

_URL = ("https://huggingface.co/rhasspy/piper-voices/resolve/main/{family}/{code}/{name}/{quality}/"
        "{voice}{ext}?download=true")


def voices_dir() -> str:
    d = os.path.join(config_dir(), "voices")
    os.makedirs(d, exist_ok=True)
    return d


def voice_path(voice: str) -> str:
    return os.path.join(voices_dir(), voice + ".onnx")


def has_voice(voice: str) -> bool:
    return voice == SYSTEM or (os.path.exists(voice_path(voice)) and os.path.exists(voice_path(voice) + ".json"))


def piper_ok() -> bool:
    try:
        import piper  # noqa: F401
        return True
    except Exception:
        return False


def can_install_piper() -> bool:
    """Piper can be added with pip when CapyRunner runs from Python (not from a packaged .exe)."""
    return not getattr(sys, "frozen", False)


def system_voice_ok() -> bool:
    if sys.platform == "win32" or sys.platform == "darwin":
        return True
    return bool(shutil.which("spd-say") or shutil.which("espeak-ng") or shutil.which("espeak"))


def settings_for(settings: dict, who: str) -> dict:
    out = dict(DEFAULTS[who])
    out.update(settings.get(f"voice_{who}") or {})
    return out


def clean(text: str) -> str:
    """What should be said: no emoji or symbols, no {placeholders}."""
    text = text.replace("…", "...").replace("“", '"').replace("”", '"').replace("’", "'").replace("—", ", ")
    text = re.sub(r"\{[^}]*\}", "", text)
    out = []
    for ch in text:
        cat = unicodedata.category(ch)
        if cat in ("So", "Sk", "Cs", "Co", "Cn", "Mn") or ch in "️‍":
            out.append(" ")
        else:
            out.append(ch)
    text = re.sub(r"\s+", " ", "".join(out)).strip(" ,")
    return text if re.search(r"[A-Za-z0-9]", text) else ""


# --------------------------------------------------------------------------- #
# playing a sound file
# --------------------------------------------------------------------------- #
def _player(path: str) -> list[str] | None:
    if sys.platform == "darwin":
        return ["afplay", path]
    for cmd in (["pw-play", path], ["paplay", path], ["aplay", "-q", path],
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path]):
        if shutil.which(cmd[0]):
            return cmd
    return None


class Voice(QObject):
    """Speaks one line at a time in a background thread. A new line cuts the old one short."""
    status = Signal(str)                 # progress / problems, for the Avatar Studio
    downloaded = Signal(str, bool)       # voice id, ok
    installed = Signal(bool)
    spoken = Signal(str)                 # who finished speaking

    def __init__(self, store):
        super().__init__()
        self.store = store
        self.speaking_who = ""           # "main" / "friend" while a line is playing
        self._q: queue.Queue = queue.Queue()
        self._proc: subprocess.Popen | None = None
        self._gen = 0
        self._models: dict = {}
        self._lock = threading.Lock()
        threading.Thread(target=self._worker, daemon=True, name="capy-voice").start()

    # ---- speaking ---------------------------------------------------------- #
    def engine(self) -> str:
        return "piper" if piper_ok() else ("system" if system_voice_ok() else "")

    def say(self, who: str, text: str, name: str = "") -> bool:
        text = clean(text)
        if not text:
            return False
        self.stop()
        self._q.put((self._gen, who, text))
        return True

    def test(self, who: str, cfg: dict, name: str) -> None:
        """Say the sample line with these settings (from the Avatar Studio)."""
        self.stop()
        self._q.put((self._gen, who, clean(SAMPLE[who].format(name=name or "Primo")), cfg))

    def stop(self):
        with self._lock:
            self._gen += 1
            p = self._proc
        while not self._q.empty():
            try:
                self._q.get_nowait()
            except queue.Empty:
                break
        if p is not None and p.poll() is None:
            try:
                p.terminate()
            except Exception:
                pass
        if sys.platform == "win32":
            try:
                import winsound
                winsound.PlaySound(None, 0)
            except Exception:
                pass

    def _worker(self):
        while True:
            item = self._q.get()
            gen, who, text = item[0], item[1], item[2]
            cfg = item[3] if len(item) > 3 else settings_for(self.store.settings, who)
            if gen != self._gen:
                continue
            try:
                self._speak(gen, who, text, cfg)
            except Exception as e:                       # never let a voice problem stop the app
                self.status.emit(f"Could not speak: {e}")
            finally:
                if self.speaking_who == who:
                    self.speaking_who = ""
                self.spoken.emit(who)

    def _speak(self, gen: int, who: str, text: str, cfg: dict):
        voice = cfg.get("voice", DEFAULTS[who]["voice"])
        pitch = max(0.7, min(1.6, float(cfg.get("pitch", 1.0))))
        speed = max(0.6, min(1.6, float(cfg.get("speed", 1.0))))
        volume = max(0.0, min(1.0, float(self.store.settings.get("voice_volume", 0.9))))
        if voice != SYSTEM and piper_ok() and has_voice(voice):
            wav = self._piper_wav(voice, text, pitch, speed, volume)
            if gen != self._gen:
                return
            self._play(gen, who, wav)
        else:
            self._system(gen, who, text, pitch, speed)

    def _piper_wav(self, voice: str, text: str, pitch: float, speed: float, volume: float) -> bytes:
        from piper import PiperVoice, SynthesisConfig
        model = self._models.get(voice)
        if model is None:
            model = self._models[voice] = PiperVoice.load(voice_path(voice))
        buf = io.BytesIO()
        with wave.open(buf, "wb") as w:
            # speak slower by the pitch factor, then play faster by it: higher voice, same speed
            model.synthesize_wav(text, w, SynthesisConfig(length_scale=pitch / speed, volume=volume,
                                                          noise_scale=0.6, noise_w_scale=0.75))
        buf.seek(0)
        with wave.open(buf, "rb") as r:
            params, frames = r.getparams(), r.readframes(r.getnframes())
        out = io.BytesIO()
        with wave.open(out, "wb") as w:
            w.setnchannels(params.nchannels)
            w.setsampwidth(params.sampwidth)
            w.setframerate(int(params.framerate * pitch))
            w.writeframes(frames)
        return out.getvalue()

    def _play(self, gen: int, who: str, wav: bytes):
        fd, path = tempfile.mkstemp(prefix="capyvoice-", suffix=".wav")
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(wav)
            with wave.open(path, "rb") as r:
                secs = r.getnframes() / float(r.getframerate())
            if gen != self._gen:
                return
            self.speaking_who = who
            if sys.platform == "win32":
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME)
                return
            cmd = _player(path)
            if not cmd:
                self.status.emit("No sound player found (install pipewire, pulseaudio-utils or ffmpeg).")
                return
            with self._lock:
                if gen != self._gen:
                    return
                self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                self._proc.wait(timeout=secs + 10)
            except subprocess.TimeoutExpired:
                self._proc.kill()
        finally:
            with self._lock:
                self._proc = None
            try:
                os.remove(path)
            except OSError:
                pass

    def _system(self, gen: int, who: str, text: str, pitch: float, speed: float):
        """The computer's own voice (more robotic), when Piper or the voice file is missing."""
        if sys.platform == "win32":
            rate = int(max(-10, min(10, (speed - 1) * 10)))
            safe = text.replace("'", "''")
            cmd = ["powershell", "-NoProfile", "-WindowStyle", "Hidden", "-Command",
                   "Add-Type -AssemblyName System.Speech; $s = New-Object System.Speech.Synthesis.SpeechSynthesizer; "
                   f"$s.Rate = {rate}; $s.Speak('{safe}')"]
        elif sys.platform == "darwin":
            cmd = ["say", "-r", str(int(185 * speed)), text]
        elif shutil.which("spd-say"):
            cmd = ["spd-say", "-w", "-r", str(int((speed - 1) * 100)), "-p", str(int((pitch - 1) * 100)), text]
        elif shutil.which("espeak-ng") or shutil.which("espeak"):
            exe = shutil.which("espeak-ng") or shutil.which("espeak")
            cmd = [exe, "-s", str(int(165 * speed)), "-p", str(int(50 * pitch)), text]
        else:
            self.status.emit("No voice engine found. Install the natural voices in the Avatar Studio.")
            return
        with self._lock:
            if gen != self._gen:
                return
            flags = 0x08000000 if sys.platform == "win32" else 0         # CREATE_NO_WINDOW
            self.speaking_who = who
            self._proc = subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                          creationflags=flags)
        try:
            self._proc.wait(timeout=60)
        except subprocess.TimeoutExpired:
            self._proc.kill()
        finally:
            with self._lock:
                self._proc = None

    # ---- getting voices ------------------------------------------------------ #
    def download(self, voice: str):
        threading.Thread(target=self._download, args=(voice,), daemon=True).start()

    def _download(self, voice: str):
        try:
            code, name, quality = voice.split("-", 2)
            dest = voice_path(voice)
            for ext in (".onnx.json", ".onnx"):
                url = _URL.format(family=code.split("_")[0], code=code, name=name, quality=quality, voice=voice,
                                  ext=ext)
                req = urllib.request.Request(url, headers={"User-Agent": "CapyRunner"})
                part = dest + ext[len(".onnx"):] + ".part"
                with urllib.request.urlopen(req, timeout=30) as r, open(part, "wb") as f:
                    total = int(r.headers.get("Content-Length") or 0)
                    got, last = 0, 0.0
                    while True:
                        chunk = r.read(256 * 1024)
                        if not chunk:
                            break
                        f.write(chunk)
                        got += len(chunk)
                        if total and ext == ".onnx" and time.time() - last > 0.3:
                            last = time.time()
                            self.status.emit(f"Downloading {VOICES.get(voice, voice).split(' ·')[0]}… "
                                             f"{got * 100 // total}%")
                os.replace(part, dest + ext[len(".onnx"):])
            self.status.emit(f"{VOICES.get(voice, voice).split(' ·')[0]} is ready ✓")
            self.downloaded.emit(voice, True)
        except Exception as e:
            self.status.emit(f"Download failed: {e}")
            self.downloaded.emit(voice, False)

    def install_engine(self):
        threading.Thread(target=self._install, daemon=True).start()

    def _install(self):
        self.status.emit("Installing the natural voice engine (Piper, about 40 MB)…")
        try:
            r = subprocess.run([sys.executable, "-m", "pip", "install", "-q", "piper-tts>=1.3"],
                               capture_output=True, text=True, timeout=900)
            ok = r.returncode == 0
            if ok:
                import importlib
                importlib.invalidate_caches()
                ok = piper_ok()
            self.status.emit("Natural voice engine installed ✓" if ok else
                             "Could not install Piper: " + (r.stderr.strip().splitlines() or ["unknown error"])[-1])
        except Exception as e:
            ok = False
            self.status.emit(f"Could not install Piper: {e}")
        self.installed.emit(ok)
