"""Updates: once a day CapyRunner asks GitHub whether a newer release is out.

Only the public "latest release" page is read; nothing about you or your computer is sent.
- Windows (installed with CapyRunner-Setup): downloads the new setup, checks its SHA-256 against the one GitHub
  publishes, runs it silently and starts again. Settings and tasks are kept (they live in your user folder).
- Everywhere else: opens the release page (or run install.sh again for a Linux / macOS source install).
"""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import threading
import urllib.error
import urllib.request

from PySide6.QtCore import QObject, QUrl, Signal
from PySide6.QtGui import QDesktopServices

from . import __version__

DEVELOPER = "Devjr"
REPO = "jrorias/capyrunner"
API = f"https://api.github.com/repos/{REPO}/releases/latest"
PAGE = f"https://github.com/{REPO}/releases/latest"
SETUP = "CapyRunner-Setup-x64.exe"
UA = f"CapyRunner/{__version__}"


def _ver(text: str) -> tuple:
    out = []
    for part in text.strip().lstrip("vV").split("."):
        num = "".join(ch for ch in part if ch.isdigit())
        out.append(int(num) if num else 0)
    return tuple(out + [0] * (3 - len(out)))


def _get(url: str, timeout: float = 15):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/vnd.github+json"})
    return urllib.request.urlopen(req, timeout=timeout)


def latest() -> dict:
    try:
        with _get(API) as r:
            data = json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            raise RuntimeError("No public release found. If the GitHub repository is private, automatic updates "
                               "need it to be public (or download the new version from GitHub yourself).") from None
        raise
    tag = str(data.get("tag_name") or "")
    info = {"version": tag.lstrip("vV"), "page": data.get("html_url") or PAGE, "setup": "", "sha256": "",
            "newer": _ver(tag) > _ver(__version__)}
    for a in data.get("assets") or []:
        if a.get("name") == SETUP:
            info["setup"] = a.get("browser_download_url", "")
            dig = str(a.get("digest") or "")
            info["sha256"] = dig.split(":", 1)[1] if dig.startswith("sha256:") else ""
    return info


def how_to_update() -> str:
    """installer (Windows app from the setup) | script (source install: run install.sh again) | page"""
    if sys.platform == "win32" and getattr(sys, "frozen", False):
        exe = os.path.normcase(sys.executable)
        if os.path.normcase(os.path.join(os.environ.get("LOCALAPPDATA", ""), "Programs", "CapyRunner")) in exe:
            return "installer"
    if not getattr(sys, "frozen", False) and sys.platform != "win32":
        return "script"
    return "page"


def open_page(info: dict | None = None) -> None:
    QDesktopServices.openUrl(QUrl((info or {}).get("page") or PAGE))


class Checker(QObject):
    """Asks GitHub in a background thread, so Primo never stutters while it waits."""
    found = Signal(dict)
    failed = Signal(str)
    ready = Signal()                 # the new setup is running: quit now so it can replace the files
    install_failed = Signal(str)

    def check(self) -> None:
        def run():
            try:
                self.found.emit(latest())
            except Exception as e:                 # offline, rate-limited… try again tomorrow
                self.failed.emit(str(e) or e.__class__.__name__)
        threading.Thread(target=run, daemon=True, name="capy-update-check").start()

    def install(self, info: dict) -> None:
        """Windows: download the new setup in the background, check it, run it silently, then emit ready
        (the app quits; the setup replaces the files and starts the new version)."""
        url = info.get("setup")
        if not url:
            self.install_failed.emit("This release has no Windows installer yet.")
            return

        def run():
            try:
                path = os.path.join(tempfile.gettempdir(), f"CapyRunner-Setup-{info.get('version', 'new')}.exe")
                h = hashlib.sha256()
                with _get(url, timeout=60) as r, open(path, "wb") as f:
                    while chunk := r.read(1 << 16):
                        h.update(chunk)
                        f.write(chunk)
                if info.get("sha256") and h.hexdigest().lower() != info["sha256"].lower():
                    os.remove(path)
                    self.install_failed.emit("The download was damaged (checksum does not match). Try again later.")
                    return
                flags = 0x00000008 | 0x00000200        # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
                subprocess.Popen([path, "/SILENT", "/SP-", "/SUPPRESSMSGBOXES", "/NOCANCEL", "/NORESTART"],
                                 creationflags=flags, close_fds=True)
                self.ready.emit()
            except Exception as e:
                self.install_failed.emit(str(e) or e.__class__.__name__)

        threading.Thread(target=run, daemon=True, name="capy-update-download").start()
