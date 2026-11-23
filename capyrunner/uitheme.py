"""App colour themes: the windows (tasks, settings, controls), the menus and Primo's speech bubbles.

"System" keeps the look of your desktop. The others use Qt's Fusion style with their own colours, so they
look the same on Windows 10, Windows 11 and Linux.
"""
from __future__ import annotations

from PySide6.QtGui import QColor, QPalette
from PySide6.QtWidgets import QApplication, QStyleFactory

# window, panel (lists, text boxes), text, button, accent, accent text, bubble, bubble text, bubble border
THEMES: dict[str, dict] = {
    "system":   {"label": "System (follow my desktop)"},
    "light":    {"label": "Light", "window": "#F6F6F4", "base": "#FFFFFF", "text": "#1B1B1B", "button": "#ECECEA",
                 "accent": "#2F6FD8", "accent_text": "#FFFFFF", "bubble": "#FFFFFF", "bubble_text": "#1B1B1B",
                 "border": "#3A2414"},
    "dark":     {"label": "Dark", "window": "#202124", "base": "#2A2B2F", "text": "#E8E8EA", "button": "#33353A",
                 "accent": "#5B9BFF", "accent_text": "#0E1116", "bubble": "#2A2B2F", "bubble_text": "#F2F2F2",
                 "border": "#9AA0A6"},
    "capytech": {"label": "Capytech (warm cream and orange)", "window": "#FFF7EC", "base": "#FFFFFF",
                 "text": "#3A2414", "button": "#FBE7CF", "accent": "#E8762B", "accent_text": "#FFFFFF",
                 "bubble": "#FFF9F0", "bubble_text": "#3A2414", "border": "#8E5A34"},
    "ocean":    {"label": "Ocean night", "window": "#0F1E2E", "base": "#152A40", "text": "#DCEBFA", "button": "#1C3550",
                 "accent": "#29A3DA", "accent_text": "#04121D", "bubble": "#152A40", "bubble_text": "#E6F3FF",
                 "border": "#4FB3E8"},
    "forest":   {"label": "Forest", "window": "#F1F5EE", "base": "#FFFFFF", "text": "#1F2D1C", "button": "#DDE8D6",
                 "accent": "#3E8E4A", "accent_text": "#FFFFFF", "bubble": "#F7FBF4", "bubble_text": "#1F2D1C",
                 "border": "#3E6B3A"},
    "sakura":   {"label": "Sakura pink", "window": "#FFF3F6", "base": "#FFFFFF", "text": "#3B1F2B", "button": "#FBDDE6",
                 "accent": "#E0567F", "accent_text": "#FFFFFF", "bubble": "#FFF7FA", "bubble_text": "#3B1F2B",
                 "border": "#B0456A"},
    "fiesta":   {"label": "Taco fiesta", "window": "#FFFBE6", "base": "#FFFFFF", "text": "#2B2111", "button": "#FFEFA8",
                 "accent": "#D62839", "accent_text": "#FFFFFF", "bubble": "#FFFDF2", "bubble_text": "#2B2111",
                 "border": "#58B368"},
}
ORDER = ("system", "light", "dark", "capytech", "ocean", "forest", "sakura", "fiesta")
DEFAULT_BUBBLE = {"bubble": "#FFFFFF", "bubble_text": "#1B1B1B", "border": "#3A2414"}

_original: tuple | None = None        # the desktop's own style and palette, to go back to "System"


def get(name: str) -> dict:
    return THEMES.get(name) or THEMES["system"]


def bubble_colors(name: str) -> dict:
    t = get(name)
    return {k: t.get(k, v) for k, v in DEFAULT_BUBBLE.items()}


def apply(app: QApplication, name: str) -> None:
    global _original
    if _original is None:
        _original = (app.style().name(), QPalette(app.palette()))
    t = get(name)
    if "window" not in t:                 # System: back to how the desktop draws it
        style = QStyleFactory.create(_original[0])
        if style is not None:
            app.setStyle(style)
        app.setPalette(_original[1])
        app.setStyleSheet("")
        return
    app.setStyle(QStyleFactory.create("Fusion"))
    c = {k: QColor(v) for k, v in t.items() if k != "label"}
    pal = QPalette()
    for group in (QPalette.Active, QPalette.Inactive):
        pal.setColor(group, QPalette.Window, c["window"])
        pal.setColor(group, QPalette.WindowText, c["text"])
        pal.setColor(group, QPalette.Base, c["base"])
        pal.setColor(group, QPalette.AlternateBase, c["button"])
        pal.setColor(group, QPalette.Text, c["text"])
        pal.setColor(group, QPalette.Button, c["button"])
        pal.setColor(group, QPalette.ButtonText, c["text"])
        pal.setColor(group, QPalette.Highlight, c["accent"])
        pal.setColor(group, QPalette.HighlightedText, c["accent_text"])
        pal.setColor(group, QPalette.ToolTipBase, c["base"])
        pal.setColor(group, QPalette.ToolTipText, c["text"])
        pal.setColor(group, QPalette.PlaceholderText, _mix(c["text"], c["base"], 0.5))
        pal.setColor(group, QPalette.Link, c["accent"])
        pal.setColor(group, QPalette.Mid, _mix(c["text"], c["window"], 0.55))
    dim = _mix(c["text"], c["window"], 0.55)
    for role in (QPalette.WindowText, QPalette.Text, QPalette.ButtonText):
        pal.setColor(QPalette.Disabled, role, dim)
    pal.setColor(QPalette.Disabled, QPalette.Window, c["window"])
    pal.setColor(QPalette.Disabled, QPalette.Base, c["window"])
    pal.setColor(QPalette.Disabled, QPalette.Button, c["button"])
    app.setPalette(pal)
    a, r = t["accent"], 8
    app.setStyleSheet(
        f"QPushButton {{ padding: 5px 12px; border-radius: {r}px; border: 1px solid {_hex(dim)}; }}"
        f"QPushButton:hover {{ border-color: {a}; }}"
        f"QPushButton:default {{ background: {a}; color: {t['accent_text']}; border-color: {a}; }}"
        f"QTabBar::tab:selected {{ color: {a}; }}"
        f"QGroupBox {{ font-weight: 600; }}")


def _mix(a: QColor, b: QColor, k: float) -> QColor:
    return QColor(int(a.red() * (1 - k) + b.red() * k), int(a.green() * (1 - k) + b.green() * k),
                  int(a.blue() * (1 - k) + b.blue() * k))


def _hex(c: QColor) -> str:
    return c.name()
