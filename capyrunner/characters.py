"""Running characters.

Built-in characters are drawn in code (no image files needed), so they can be
recoloured freely. Custom characters can be loaded from:
  * an animated GIF / WebP
  * a sprite sheet PNG (frames side by side, left to right)
  * a folder of PNG frames (sorted by file name)
"""
from __future__ import annotations

import math
import os
from dataclasses import dataclass, field
from contextlib import contextmanager
from functools import partial

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QImageReader, QPainter, QPainterPath,
                           QPen, QPixmap)

from . import avatars, themes

BASE = 128          # frames are drawn at 128x128 and scaled by Qt when shown
RUN_FRAMES = 10
ROPE_X = 104        # where the rope hangs inside a (right-facing) rope-pose frame

BUILTIN = {
    "capy": "Primo (Capytech mascot)",
    "capybara": "Capybara (simple)",
    "cat": "Cat",
    "dog": "Dog",
    "dots": "Bouncing dots",
}


@dataclass
class FrameSet:
    run: list[QPixmap]
    sleep: list[QPixmap] = field(default_factory=list)
    jump: list[QPixmap] = field(default_factory=list)   # played when a notification arrives
    extra: dict = field(default_factory=dict)           # optional rope poses: climb, slip, fall, dizzy, think, slide, cling

    def ensure_sleep(self) -> None:
        if not self.sleep and self.run:
            self.sleep = [_sleepify(self.run[0], k) for k in range(2)]


# --------------------------------------------------------------------------- #
# helpers
# --------------------------------------------------------------------------- #
def cy_desk(dy: float) -> float:
    """Body centre of a seated pose (same formula as in _capy)."""
    return 88 + dy


def _chair(p: QPainter, cy: float, color: QColor):
    """An office chair: backrest behind him, seat under him, gas lift and a base with wheels."""
    dark = color.darker(170)
    p.setPen(QPen(INK, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(QColor("#7A8698"))
    p.drawRect(QRectF(60, cy + 24, 6, 7))                       # gas lift
    p.setBrush(QColor("#55606F"))
    p.drawRoundedRect(QRectF(36, cy + 29.5, 54, 5), 2.5, 2.5)        # base
    p.setBrush(QColor("#2B2B33"))
    for wx in (39, 63, 87):                                        # wheels
        p.drawEllipse(QPointF(wx, cy + 35.5), 3.2, 3.2)
    p.setBrush(QColor("#7A8698"))
    p.drawRect(QRectF(29, cy - 4, 5, 22))                          # backrest post
    p.setPen(QPen(INK, 2.4))
    p.setBrush(color)
    p.drawRoundedRect(QRectF(19, cy - 34, 19, 36), 8, 8)            # backrest
    p.drawRoundedRect(QRectF(30, cy + 15, 62, 10), 5, 5)            # seat cushion
    p.setPen(QPen(dark, 1.6, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(24, cy - 24), QPointF(24, cy - 6))          # stitching
    p.drawLine(QPointF(36, cy + 20), QPointF(86, cy + 20))


def _canvas() -> tuple[QPixmap, QPainter]:
    pm = QPixmap(BASE, BASE)
    pm.fill(Qt.transparent)
    p = QPainter(pm)
    p.setRenderHint(QPainter.Antialiasing)
    return pm, p


def _outline(color: QColor) -> QColor:
    return color.darker(260) if color.lightness() > 60 else color.lighter(300)


def _leg(p: QPainter, hip: QPointF, angle: float, length: float, width: float, color: QColor):
    end = QPointF(hip.x() + math.sin(angle) * length, hip.y() + math.cos(angle) * length)
    p.setPen(QPen(_outline(color), width + 4, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(hip, end)
    p.setPen(QPen(color, width, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(hip, end)


def _zz(p: QPainter, k: int, color: QColor) -> None:
    f = QFont()
    f.setBold(True)
    for i, (x, y, s) in enumerate([(84, 40, 18), (98, 24, 24)]):
        if i > k:
            break
        f.setPixelSize(s)
        path = QPainterPath()
        path.addText(QPointF(x, y), f, "z")
        p.setPen(QPen(QColor("#222222"), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(path)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#ffffff"))
        p.drawPath(path)


def _sleepify(pm: QPixmap, k: int) -> QPixmap:
    out, p = _canvas()
    p.setOpacity(0.75)
    p.drawPixmap(0, 12, pm)
    p.setOpacity(1)
    _zz(p, k, QColor("#ffffff"))
    p.end()
    return out


# --------------------------------------------------------------------------- #
# built-in characters
# --------------------------------------------------------------------------- #
def _quadruped(kind: str, color: QColor, t: float, sleeping: bool = False, zk: int = 0) -> QPixmap:
    pm, p = _canvas()
    out = _outline(color)
    bob = 0 if sleeping else abs(math.sin(t)) * -5
    body_y = 66 + bob + (14 if sleeping else 0)

    # body dimensions per animal
    if kind == "capybara":
        body = QRectF(22, body_y - 22, 74, 44)
        head = QRectF(80, body_y - 34, 34, 28)
        leg_len, leg_w = 16, 9
    elif kind == "dog":
        body = QRectF(26, body_y - 16, 62, 32)
        head = QRectF(80, body_y - 36, 30, 28)
        leg_len, leg_w = 24, 7
    else:  # cat
        body = QRectF(28, body_y - 14, 60, 28)
        head = QRectF(82, body_y - 34, 28, 26)
        leg_len, leg_w = 24, 6

    swing = 0 if sleeping else 0.75
    if not sleeping:
        # legs: back pair and front pair, opposite phases (gallop)
        hips = [(body.left() + 14, t), (body.left() + 20, t + 0.6),
                (body.right() - 14, t + math.pi), (body.right() - 8, t + math.pi + 0.6)]
        for hx, ph in hips:
            _leg(p, QPointF(hx, body.bottom() - 6), math.sin(ph) * swing, leg_len, leg_w, color)

    # tail
    if kind in ("cat", "dog"):
        wag = math.sin(t * 2) * 8 if not sleeping else 0
        path = QPainterPath(QPointF(body.left() + 6, body.top() + 8))
        if kind == "cat":
            path.cubicTo(body.left() - 18, body.top() + 4, body.left() - 14, body.top() - 26 + wag,
                         body.left() - 2, body.top() - 30 + wag)
        else:
            path.quadTo(body.left() - 14, body.top() - 4, body.left() - 16, body.top() - 18 + wag)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(out, 11, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)
        p.setPen(QPen(color, 7, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)

    # body + head
    p.setPen(QPen(out, 3))
    p.setBrush(color)
    p.drawRoundedRect(body, 20, 20)

    # ears (behind head outline is fine)
    if kind == "cat":
        for ex in (head.left() + 4, head.left() + 16):
            ear = QPainterPath(QPointF(ex, head.top() + 6))
            ear.lineTo(ex + 5, head.top() - 10)
            ear.lineTo(ex + 11, head.top() + 4)
            ear.closeSubpath()
            p.drawPath(ear)
    elif kind == "capybara":
        p.drawEllipse(QRectF(head.left() + 4, head.top() - 5, 9, 9))
    p.drawRoundedRect(head, 12, 12)
    if kind == "dog":
        flop = math.sin(t) * 3 if not sleeping else 0
        p.drawEllipse(QRectF(head.left() + 2, head.top() + 2 + flop, 11, 20))

    # face
    p.setBrush(out)
    p.setPen(Qt.NoPen)
    if sleeping:
        p.setPen(QPen(out, 2.5, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(head.right() - 14, head.top() + 11), QPointF(head.right() - 7, head.top() + 11))
        _zz(p, zk, color)
    else:
        p.drawEllipse(QPointF(head.right() - 10, head.top() + 10), 3, 3)
    p.setPen(Qt.NoPen)
    p.drawEllipse(QPointF(head.right() - 2, head.top() + 16), 3, 2.5)  # nose
    p.end()
    return pm


def _dots(color: QColor, t: float, sleeping: bool = False, zk: int = 0) -> QPixmap:
    pm, p = _canvas()
    p.setPen(QPen(_outline(color), 3))
    p.setBrush(color)
    for i in range(3):
        h = 0 if sleeping else max(0.0, math.sin(t - i * 0.9)) * 34
        p.drawEllipse(QPointF(30 + i * 34, 86 - h), 13, 13)
    if sleeping:
        _zz(p, zk, color)
    p.end()
    return pm


# --------------------------------------------------------------------------- #
# Capy — the Capytech mascot (tan capybara in a navy hoodie)
# --------------------------------------------------------------------------- #
INK = QColor("#3A2414")
FUR = QColor("#C98A50")
FUR_DARK = QColor("#8E5A34")
PAW = QColor("#B9773F")
PINK = QColor("#F07C8E")
# who is being drawn right now: fur colour and headwear (see avatars.py). set_avatars() picks the main avatar
# (the one on screen) and the friend (the dance rival); _wearing() switches for a while.
_MAIN = {"fur": "#C98A50", "acc": "", "acc_color": ""}
_FRIEND = {"fur": "#E3B273", "acc": "bandana", "acc_color": "#D62839"}
_CUR = dict(_MAIN)
BLUSH = QColor(240, 120, 130, 150)


def _star(p: QPainter, c: QPointF, r: float, color: str = "#FFD54A"):
    path = QPainterPath()
    for i in range(8):
        rr = r if i % 2 == 0 else r * 0.32
        a = i * math.pi / 4 - math.pi / 2
        pt = QPointF(c.x() + math.cos(a) * rr, c.y() + math.sin(a) * rr)
        path.moveTo(pt) if i == 0 else path.lineTo(pt)
    path.closeSubpath()
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(color))
    p.drawPath(path)


def _happy_eye(p: QPainter, x: float, y: float, w: float = 9):
    p.setPen(QPen(INK, 3.2, Qt.SolidLine, Qt.RoundCap))
    p.setBrush(Qt.NoBrush)
    path = QPainterPath(QPointF(x - w / 2, y + 2))
    path.quadTo(x, y - w * 0.75, x + w / 2, y + 2)
    p.drawPath(path)


def _limb(p: QPainter, a: QPointF, angle: float, length: float, sleeve: QColor | None, paw_r: float,
          paw: QColor | None = None):
    b = QPointF(a.x() + math.sin(angle) * length, a.y() + math.cos(angle) * length)
    if sleeve is not None:
        p.setPen(QPen(INK, 13, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(a, b)
        p.setPen(QPen(sleeve, 9, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(a, b)
    else:
        p.setPen(QPen(INK, 12, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(a, b)
        p.setPen(QPen(PAW, 8, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(a, b)
    p.setPen(QPen(INK, 2.2))
    p.setBrush(paw or PAW)
    p.drawEllipse(b, paw_r, paw_r)


def _lantern(p: QPainter, c: QPointF, r: float):
    """The fiesta star: a glowing yellow star."""
    p.setPen(Qt.NoPen)
    p.setBrush(QColor(255, 213, 74, 70))
    p.drawEllipse(c, r * 1.55, r * 1.55)
    _star(p, c, r + 1.8, "#D98A00")
    _star(p, c, r)


SUIT_GREY = QColor("#8D99AB")
SUIT_LIGHT = QColor("#DDE3EC")
PARTY = ("#F0527A", "#FFD54A", "#29A3DA", "#58B368", "#FF8A00")


def _headset(p: QPainter, hy: float):
    """Call-centre headset: band over the head, one ear cup, a boom microphone at the mouth."""
    band = QPainterPath(QPointF(46, hy - 2))
    band.cubicTo(38, hy - 30, 60, hy - 40, 80, hy - 30)
    boom = QPainterPath(QPointF(45, hy + 9))
    boom.quadTo(56, hy + 27, 79, hy + 18)
    p.setBrush(Qt.NoBrush)
    for path, w_ in ((band, 6.6), (boom, 4.4)):
        p.setPen(QPen(INK, w_, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)
        p.setPen(QPen(QColor("#4A5060"), w_ - 3, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(path)
    p.setPen(QPen(INK, 2.2))
    p.setBrush(QColor("#2B2B33"))
    p.drawRoundedRect(QRectF(37, hy - 9, 14, 21), 6.5, 6.5)
    p.drawEllipse(QPointF(80, hy + 18), 3.8, 3.8)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#29A3DA"))
    p.drawRoundedRect(QRectF(40.5, hy - 4, 3, 9), 1.5, 1.5)


def _dance_pose(mv: dict, t: float) -> dict:
    """A dance move at phase t (0..2π): where the body, the paws and the feet are.
    mv = {"arms", "legs", "body", "fx"}: one pattern each (dance.MOVES lists the 100 combinations).
    Paw and foot positions are canvas points for a body at rest; they follow the body's bounce."""
    s, c = math.sin(t), math.cos(t)
    a_s, up, ph = abs(s), math.sin(t) >= 0, (t / (2 * math.pi)) % 1.0
    s2 = math.sin(2 * t)
    q = {"dy": 0.0, "squash": 0.0, "tilt": 0.0, "jx": 0.0, "bx": 0.0, "hb": None, "hf": None, "ab": 0.5, "af": 0.7,
         "alen": 15, "legs": [0.0, 0.0], "fb": None, "ff": None, "xf": None, "mouth": 1.2, "happy": True,
         "fx": mv.get("fx", "")}
    arms, legs, body = mv.get("arms", "bob"), mv.get("legs", "bounce"), mv.get("body", "bounce")

    # ---- body: bounce, sway, turns and flips ---- #
    if body == "bounce":
        q["dy"] = -4 * a_s
    elif body == "sway":
        q.update(dy=-3 * a_s, tilt=8 * s, jx=3 * s)
    elif body == "hips":                    # hips one way, head the other
        q.update(bx=5 * s, tilt=-5 * s, dy=-1.5 * abs(c))
    elif body == "roll":                    # body roll: down through the knees and round
        q.update(squash=3 + 3 * s, tilt=6 * c, bx=3 * c)
    elif body == "low":                     # down low, bouncing
        q.update(dy=6 + 2.5 * s2, tilt=4 * s)
    elif body == "jump":
        q["dy"] = -9 * a_s
    elif body == "shimmy":
        q.update(jx=2.5 * math.sin(3 * t), tilt=3 * math.sin(3 * t), dy=-2 * a_s)
    elif body in ("spin", "headspin", "stand"):
        q.update(dy=-2, xf=(body,), jx=(2 * s if body == "stand" else 0.0))
    elif body == "lean":                    # leaning right over without falling
        q["xf"] = ("rot", 13 * s, 64, 120)
    elif body in ("flip", "fflip"):         # crouch, all the way round in the air, land
        if ph < 0.2:
            q["squash"] = 5
        elif ph < 0.8:
            k_ = (ph - 0.2) / 0.6
            q["dy"] = -6 * math.sin(k_ * math.pi)
            q["xf"] = ("rot", (-360 if body == "flip" else 360) * k_, 64, 74 + q["dy"])
        else:
            q["squash"] = 3
    elif body == "cartwheel":
        q["xf"] = ("rot", 360 * ph, 64, 72)
    elif body == "worm":                    # on his belly, rocking
        q["xf"] = ("rot", 90 + 8 * s, 64, 78)
    elif body == "bang":                    # nodding hard
        q.update(tilt=14 * max(0.0, s2) - 3, dy=-2 * a_s)
    elif body == "slide":
        q.update(jx=8 * s, tilt=-3 * s)
    elif body == "groove":
        q.update(dy=-3 * abs(s2), tilt=4 * s, bx=2 * s)
    elif body == "pop":                     # hit a pose, hold, hit the next
        i = int(ph * 4) % 4
        q.update(dy=(-5, 0, -5, 0)[i], tilt=(-8, 0, 8, 0)[i])
    off = q["dy"] + q["squash"]

    # ---- legs ---- #
    if legs == "bounce":
        q["legs"] = [0.18 * s, -0.18 * s]
    elif legs == "run":
        q["legs"] = [s, -s]
    elif legs == "kick":
        q["legs"] = [1.3 * a_s, -0.1] if up else [0.1, -1.2 * a_s]
    elif legs == "wide":
        q["legs"] = [0.5, -0.5]
    elif legs == "step":
        q["legs"] = [0.3 * s + 0.12, 0.3 * s - 0.12]
    elif legs == "cross":
        q["ff"], q["fb"] = (62 - 9 * s, 114 + off), (62 + 9 * s, 114 + off)
    elif legs == "tap":
        q["legs"] = [0.7 - 0.35 * abs(s2), -0.1]
    elif legs == "jack":
        q["legs"] = [0.7 * (1 - c) / 2, -0.7 * (1 - c) / 2]
    elif legs == "squat":                   # feet planted wide, however low the body goes
        q["fb"], q["ff"] = (38, 117), (88, 117)
    elif legs == "hop":
        q["legs"] = [0.12, -0.12]
    elif legs == "moon":                    # feet sliding past each other
        q["ff"], q["fb"] = (72 + 10 * s, 114 + off), (52 - 10 * s, 114 + off - 3 * max(0.0, c))
    elif legs == "twist":
        q["ff"], q["fb"] = (72 + 7 * s, 114 + off), (52 + 7 * s, 114 + off)
    elif legs == "cancan":
        q["legs"] = [1.5 * max(0.0, s), -0.15]

    # ---- arms: (back paw, front paw), or swinging from the shoulder ---- #
    h = None
    if arms == "bob":
        q.update(ab=0.5 + 0.4 * s, af=0.7 - 0.4 * s, mouth=1.0)
    elif arms == "pump":
        q.update(ab=0.4 - 1.1 * s, af=0.4 + 1.1 * s)
    elif arms == "chicken":
        q.update(alen=10, ab=-1.6 - 0.6 * a_s, af=1.6 + 0.6 * a_s)
    elif arms == "cross":
        q.update(alen=14, ab=1.35, af=-1.2)
    elif arms == "up":
        h = (24 + 8 * s, 52), (104 + 8 * s, 48)
    elif arms == "point":
        h = ((40, 104), (110, 42 - 5 * a_s)) if up else ((26, 46 - 5 * a_s), (94, 106))
    elif arms == "tee":
        h = (22, 80 + 4 * s), (112, 80 - 4 * s)
    elif arms == "roll":
        h = (96 - 7 * c, 84 - 7 * s), (96 + 7 * c, 84 + 7 * s)
    elif arms == "clap":
        a = (1 + c) / 2
        h = (62 - 32 * a, 16 + 26 * a), (74 + 32 * a, 16 + 26 * a)
    elif arms == "disco":
        h = ((42, 96), (110, 38)) if up else ((42, 96), (50, 106))
    elif arms == "hips":
        h = (42, 96 + 2 * s), (86, 97 - 2 * s)
    elif arms == "head":
        h = (35, 40 + 2 * s), (99, 30 - 2 * s)
    elif arms == "ripple":
        h = (22, 80 - 14 * s), (112, 80 - 14 * math.sin(t - 1.6))
    elif arms == "roof":
        h = (30, 46 - 8 * a_s), (102, 42 - 8 * a_s)
    elif arms == "lasso":
        h = (42, 96), (86 + 12 * c, 17 + 4 * s)
    elif arms == "dab":
        h = ((20, 58), (54, 52)) if up else ((30, 98), (110, 44))
        q["tilt"] = -12 if up else 8
    elif arms == "floss":
        h = (40 + 18 * s, 100), (78 + 18 * s, 100)
    elif arms == "robot":
        h = (((22, 80), (100, 56)), ((30, 56), (112, 80)), ((30, 56), (100, 56)), ((46, 104), (112, 80)))[int(ph * 4) % 4]
    elif arms == "swim":
        h = (30 - 12 * c, 66 - 16 * s), (98 + 12 * c, 66 + 16 * s)
    elif arms == "heart":
        h = (57, 15 + 2 * a_s), (79, 15 + 2 * a_s)
    elif arms == "snap":
        h = (40, 100 + 3 * s), (96, 92 - 4 * s)
    elif arms == "touch":                   # reaching out, one paw then the other
        h = ((42, 96), (114, 72 - 4 * a_s)) if up else ((20, 72 - 4 * a_s), (86, 97))
    elif arms == "slide":                   # one paw behind the head, the other sliding down
        h = (35, 40), (86, 86 + 14 * s)
    elif arms == "vogue":
        h = (34, 60 - 6 * s), (104, 38 + 6 * s)
    elif arms == "punch":
        h = ((44, 100), (100, 34)) if up else ((28, 38), (86, 100))
    elif arms == "twirl":
        h = (60, 14), (76, 14)
    elif arms == "egypt":
        h = ((26, 96), (108, 62)) if up else ((26, 60), (108, 90))
    elif arms == "sprinkler":
        h = (35, 40), (112, 70 + 10 * s2)
    elif arms == "guns":
        h = (104, 90 - 3 * s), (112, 78 + 3 * s)
    elif arms == "windmill":
        h = (58 - 24 * s, 82 - 24 * c), (70 + 24 * s, 82 - 24 * c)
    elif arms == "shrug":
        h = (34, 92 - 5 * a_s), (98, 92 - 5 * a_s)
    if h:
        q["hb"], q["hf"] = (h[0][0] + q["bx"], h[0][1] + off), (h[1][0] + q["bx"], h[1][1] + off)
    if q["fx"] == "hearts":                 # the slow ones come with a wink
        q["happy"], q["mouth"] = s < 0.2, 0.9
    return q


def _capy(hoodie: QColor, mode: str, t: float = 0.0, k: float = 0.0, zk: int = 0, outfit: str = "",
          bandana: bool | str = False, style: str = "", mv: dict | None = None, chair: str = "",
          specs: bool = False, cup: str = "") -> QPixmap:
    """mode: run | jump | sleep | climb | slip | fall | dizzy | think | slide | cling | float …
    t = animation phase, k = jump progress 0..1 (or a small variant counter).
    outfit: '' | hike | space | jungle | fiesta : the clothes of the day (see themes.py).
    bandana: True (red) or a colour. style: office (in a call) or a dance style (see dance.py).
    mode "dance": mv = the move, one of dance.MOVES (arms + legs + body patterns).
    mode "desk": chair = the chair colour, specs = wearing glasses while he works.
    mode "sip": coffee break with a mug (cup = its colour). mode "ride": sitting on an animal, holding on (k=1 waving)."""
    pm, p = _canvas()
    acc, acc_col = _CUR.get("acc", ""), _CUR.get("acc_color") or "#D62839"
    if bandana is True:            # "his own headwear": the bandana only if this avatar wears one
        bandana = acc_col if acc == "bandana" else False
    elif not bandana and acc == "bandana":
        bandana = acc_col
    xf = None                      # dance: the whole of him turned round / upside down (see _dance_pose)
    navy_ink = hoodie.darker(170)
    arm_len, eyes, mouth_kind, jx, sweat, fx, look = 15, "normal", "smile", 0.0, 0, "", 0.0
    hand_b = hand_f = None         # rope poses: where the paws grip (the rope hangs at x = ROPE_X)
    foot_b = foot_f = None         # …and where the hind feet grip
    bx, tilt = 0.0, 0.0            # body pressed toward the rope; head tilt (negative = looking up)
    lookx = 0.0                    # wide eyes: pupils glancing forward (+) / back (-)
    worried = True                 # wide eyes come with worried brows unless this is off
    hp = False                     # wearing headphones
    prop, note_col = "", ""        # popcorn | book | bed | notes ; colour of floating music notes
    glasses, brows, glow = False, "", 0
    mood = ""
    boot = {"hike": QColor("#5B3A22"), "space": SUIT_LIGHT, "jungle": QColor("#6B4A2A")}.get(outfit)
    glove = SUIT_LIGHT if outfit == "space" else None
    leg_sleeve = hoodie if outfit == "space" else None

    # ---- pose parameters ------------------------------------------------- #
    dy, squash = 0.0, 0.0
    leg_a = [0.0, 0.0]
    arm_back, arm_front = 0.0, 0.0
    both_happy, mouth = False, 1.0
    if mode == "run":
        dy = -abs(math.sin(t)) * 5
        leg_a = [math.sin(t) * 0.9, math.sin(t + math.pi) * 0.9]
        arm_back, arm_front = math.sin(t + math.pi) * 0.9 + 0.3, math.sin(t) * 0.9 + 0.3
    elif mode == "jump":
        if k < 0.18:                       # crouch
            squash = 5
            arm_back = arm_front = 0.6
            leg_a = [0.5, -0.5]
        else:                               # in the air: arms up, legs tucked, ^^ face
            up = math.sin((k - 0.18) / 0.82 * math.pi)
            dy = -up * 6           # the pet window adds the big hop
            arm_back, arm_front = math.pi - 0.5, math.pi - 0.15
            leg_a = [0.9, -0.6]
            both_happy, mouth = True, 1.35
    elif mode == "climb":                  # hand over hand up the rope
        s_ = math.sin(t)
        dy = -2.5 * s_ * s_
        bx, tilt = 12, -20                           # hugging the rope, nose up, like a capybara on a tree
        hand_b = (ROPE_X - 2, 68 - 9 * s_)           # one paw reaches up while the other pulls, then swap
        hand_f = (ROPE_X - 2, 76 + 9 * s_)
        foot_b = (ROPE_X - 2, 106 + 6 * s_)          # hind feet push in the opposite rhythm
        foot_f = (ROPE_X - 2, 114 - 6 * s_)
        mouth = 0.0
    elif mode == "slide":                  # inching down the rope, nervous
        bx, tilt = 12, 10                            # peeking down while inching lower
        hand_b, hand_f = (ROPE_X - 2, 66 + math.sin(t) * 2), (ROPE_X - 2, 80 - math.sin(t) * 2)
        foot_b, foot_f = (ROPE_X - 2, 108), (ROPE_X - 2, 117)
        jx = math.sin(t) * 0.9
        eyes, mouth_kind, sweat, look = "wide", "wavy", 1 + int(k), 2.0
    elif mode == "cling":                  # frozen on the rope, eyes shut, trembling
        bx, tilt = 13, -6                            # hugging the rope tight
        hand_b, hand_f = (ROPE_X - 2, 70), (ROPE_X - 2, 78)
        foot_b, foot_f = (ROPE_X - 2, 108), (ROPE_X - 2, 114)
        jx, dy = math.sin(t) * 2.0, math.cos(t * 2) * 0.8
        eyes, mouth_kind, sweat = "shut", "wavy", 2
    elif mode in ("slip", "fall"):         # lost the grip!
        w = math.sin(t) * 0.4
        arm_len = 17
        arm_back, arm_front = math.pi + 0.9 + w, math.pi - 0.9 - w
        leg_a = [0.9 - w, -0.9 + w]
        eyes, mouth_kind = "wide", "o"
        fx = "!" if mode == "slip" else ""
    elif mode == "think":                  # at the top: paw on chin, looking down... hmm
        arm_len = 13
        arm_back, arm_front = 0.25, math.pi - 0.75
        eyes, mouth_kind, sweat, look, fx = "wide", "wavy", 1, 2.2, "..."
        if outfit in ("hike", "jungle", "fiesta"):   # the high point of the day's adventure: no worries up here
            eyes, mouth_kind, sweat, look, both_happy = "normal", "smile", 0, 0.0, True
            hand_b = (60, 96)
            if outfit == "hike":                     # planting the summit flag
                fx, hand_f = "flag", (103, 82)
            elif outfit == "jungle":                 # holding up the star he found
                fx, hand_f, mouth = "found", (104, 60), 1.25
            else:                                    # hanging the star lantern
                fx, hand_f, mouth, tilt = "lantern", (106, 56), 1.2, -8
    elif mode == "float":                  # zero gravity: arms and legs out, drifting (k = holding the star)
        s_ = math.sin(t)
        dy = -4 + s_ * 2
        arm_len = 16
        arm_back, arm_front = -1.9 - s_ * 0.25, 1.9 + s_ * 0.25
        leg_a = [0.55 + s_ * 0.2, -0.55 - s_ * 0.2]
        both_happy, mouth = True, 1.2
    elif mode == "sneak":                  # tiptoeing: crouched, paws tucked up, eyes darting
        dy = 4 - abs(math.sin(t)) * 3
        leg_a = [math.sin(t) * 0.5, math.sin(t + math.pi) * 0.5]
        arm_len = 12
        arm_back, arm_front = math.pi - 1.0 + math.sin(t) * 0.12, math.pi - 1.25 - math.sin(t) * 0.12
        eyes, lookx, mouth = "wide", math.sin(t * 0.5) * 2.0, 0.0
    elif mode == "peek":                   # frozen, checking that nobody is watching
        dy = 5
        arm_len = 12
        arm_back, arm_front = math.pi - 1.0, math.pi - 1.25
        eyes, mouth_kind, sweat, lookx = "wide", "wavy", 1, (2.4 if int(k) % 2 else -2.4)
    elif mode == "laugh":                  # sitting on the floor laughing
        dy = 8 - abs(math.sin(t)) * 5
        arm_back, arm_front = 0.9 + math.sin(t) * 0.35, 1.15 - math.sin(t) * 0.35
        both_happy, mouth, fx = True, 1.5, "haha"
        tilt = -8 + math.sin(t) * 6
    elif mode == "angry":                  # picked up: kicking, flailing, furious
        w = math.sin(t)
        arm_len = 16
        arm_back, arm_front = math.pi + 0.7 + w * 0.5, math.pi - 0.7 - w * 0.5
        leg_a = [0.7 * w, -0.7 * w]
        jx = math.sin(t * 2) * 1.5
        eyes, mouth_kind, fx = "angry", "grit", "anger"
    elif mode == "tampo":                  # sulking: sitting, arms crossed, cheeks puffed, looking away
        dy, tilt = 8, 9
        arm_len = 14
        arm_back, arm_front = 1.35, -1.2
        eyes, mouth_kind, fx = ("peekback" if int(k) == 1 else "pout"), "pout", "hmph"
    elif mode == "dizzy":                  # sitting on the floor seeing stars
        dy = 8
        jx = math.sin(t) * 2.2
        eyes, mouth_kind, fx = "dizzy", "o", "stars"
    elif mode == "listen":                 # sitting with headphones on; k picks the mood of the song
        mood = ("happy", "hype", "chill", "sad", "love")[int(k) % 5]
        hp, fx = True, "notes"
        s_ = math.sin(t)
        if mood == "hype":                           # head-banging, paws in the air
            dy, tilt = 8 - abs(s_) * 5, s_ * 12
            arm_back, arm_front = math.pi - 0.7 + s_ * 0.5, math.pi - 0.3 - s_ * 0.5
            both_happy, mouth, note_col = True, 1.45, "#E53935"
        elif mood == "chill":                        # eyes closed, slow sway
            dy, tilt = 8, s_ * 5
            arm_back, arm_front = 0.5, 0.75
            both_happy, mouth, note_col = True, 0.0, "#29A3DA"
        elif mood == "sad":                          # droopy, a tear rolling down
            dy, tilt = 9, 7 + s_ * 2.5
            arm_back, arm_front = 0.25, 0.35
            eyes, mouth_kind, note_col = "sad", "pout", "#5C7CBA"
        elif mood == "love":                         # paw on the cheek, hearts floating up
            dy, tilt = 8 - abs(s_) * 1.5, -4 + s_ * 6
            arm_len = 13
            arm_back, arm_front = 0.6, math.pi - 0.8
            both_happy, mouth, fx, note_col = True, 0.9, "hearts", "#F0527A"
        else:                                        # happy: bobbing along, tapping the floor
            dy, tilt = 8 - abs(s_) * 2.5, s_ * 8
            arm_back, arm_front = 0.9 + s_ * 0.35, 1.15 - s_ * 0.35
            both_happy, mouth, note_col = True, 1.0, "#FF8A00"
    elif mode == "watch":                  # sitting with popcorn, eyes glued to the screen
        dy, prop, eyes, worried, lookx = 8, "popcorn", "wide", False, 1.6
        step = int(k) % 8                            # reach into the bucket, bring it to the mouth, munch
        if step in (4, 5):
            hand_f = (88, 60 + dy)
            mouth_kind = "o"
        else:
            hand_f = (97, 86 + dy + (2 if step % 2 else 0))
            mouth = 0.0 if step in (6, 7) else 0.55
        hand_b = (86, 92 + dy)
    elif mode == "bed":                    # cosy: pillow, blanket, headphones, a video on the phone
        dy, tilt, prop, hp, eyes, worried = 8, 8, "bed", True, "wide", False
        step = int(k) % 12
        glow = step % 3                              # the screen flickers as the video plays
        look, lookx, mouth = 2.3, 1.5, 0.0
        if step in (7, 8, 9):                        # something funny on screen
            eyes, both_happy, mouth, tilt = "normal", True, 1.0, 5
        hand_b, hand_f = (91, 94 + dy), (101, 96 + dy)
    elif mode == "study":                  # tutorial / podcast: glasses on, sitting up straight, taking notes
        dy, prop, eyes, worried, glasses, brows = 7, "notes", "wide", False, True, "focus"
        step = int(k) % 12
        mouth = 0.0
        if step >= 7:                                # head down, writing it down
            tilt, look, lookx = 10, 2.5, 0.9
            hand_f = (90 + (step % 2) * 5, 91 + dy + (step % 3))
        else:                                        # listening closely, pencil ready, a little nod
            tilt, look, lookx = -4 + (2 if step % 2 else 0), -0.4, 1.9
            hand_f = (97, 74 + dy)
            if step in (5, 6):
                fx = "bulb"                          # aha!
        hand_b = (83, 97 + dy)
    elif mode in ("read", "read_hp"):      # sitting with a book and reading glasses
        dy, tilt, prop, eyes, worried, glasses = 8, 9, "book", "wide", False, True
        hp = mode == "read_hp"
        look, lookx, mouth = 2.4, math.sin(t) * 1.3, 0.0     # eyes travelling along the lines
        hand_b, hand_f = (88, 98 + dy), (96, 100 + dy)
        if hp:
            tilt += math.sin(t * 2) * 3
            fx, note_col = "notes", "#FF8A00"
    elif mode == "breathe":                # breathing exercise: k = how full the lungs are, t > 0 = breathing out
        dy = 8
        both_happy, mouth = True, 0.0
        arm_back, arm_front = 0.35 + k * 0.55, 0.55 + k * 0.55
        tilt = -5 * k                                # chin lifts a little on the way in
        if t > 0:
            mouth_kind = "o"
            if k > 0.12:
                fx = "hmph"                          # the air going out
    elif mode == "stretch":                # break time: arms up high, swaying side to side
        s_ = math.sin(t)
        arm_len = 17
        dy, tilt = -1 - abs(s_) * 1.5, s_ * 7
        hand_b, hand_f = (23, 62 + dy - s_ * 7), (114, 68 + dy + s_ * 7)   # arms out wide, tipping side to side
        both_happy, mouth = True, 1.25
    elif mode == "meet":                   # in a call: sitting up at the laptop; k = talking
        dy, prop, eyes, worried, lookx = 7, "laptop", "wide", False, 1.5
        hand_b, hand_f = (86, 104), (97, 102)
        if k:                                        # speaking: the mouth moves, one paw explains
            mouth = (0.3, 0.95, 0.55, 1.15, 0.4, 0.0, 0.8, 1.1, 0.35, 0.9, 0.15, 0.7)[int(round(t / (2 * math.pi) * 12)) % 12]
            hand_f = (106, 80 + math.sin(t) * 6)
            tilt, fx = math.sin(t) * 3, "talk"
        else:                                        # listening: a small nod now and then
            mouth = 0.0
            tilt = max(0.0, math.sin(t)) * 5
    elif mode == "desk":                   # work mode: on an office chair, typing on the laptop; k = frame
        dy, prop, eyes, worried, lookx, glasses = 1, "laptop", "wide", False, 1.6, specs
        step = int(k) % 12
        mouth, look = 0.0, 1.2
        tap = step % 2                               # paws taking turns on the keys
        hand_b = (88, cy_desk(dy) + 12 - (2.5 if tap else 0))
        hand_f = (99, cy_desk(dy) + 11 - (0 if tap else 2.5))
        tilt = 3 + (1.5 if step in (3, 4, 9) else 0)
        if step in (6, 7):                           # a little pause: an idea!
            fx, tilt, look, mouth = "bulb", -3, -0.4, 1.0
            hand_b, hand_f = (88, cy_desk(dy) + 13), (99, cy_desk(dy) + 13)
        elif step in (10, 11):
            both_happy, mouth = True, 0.8            # it works :)
    elif mode == "sip":                    # coffee break: sitting with a warm mug, a sip now and then
        dy, prop, worried = 8, "cup", False
        step = int(k) % 10
        mouth, tilt = 0.6, 2
        hand_b = (84, cy_desk(dy) - 4)
        hand_f = (92, cy_desk(dy) - 6)
        if step in (5, 6, 7):                        # cup up to the mouth, eyes closed: aah
            hand_b, hand_f = (80, 64 + dy), (88, 62 + dy)
            both_happy, mouth, tilt = True, 0.0, -4
        elif step == 8:
            both_happy, mouth = True, 1.1
    elif mode == "ride":                   # sitting on an animal's back, holding on; k = 1 waving hello
        s_ = math.sin(t)
        dy, tilt, worried = 8 - abs(s_) * 2, s_ * 3, False
        hand_b, hand_f = (92, cy_desk(dy) + 8), (100, cy_desk(dy) + 6)
        both_happy, mouth = True, 1.2
        if k:
            hand_f = None
            arm_front = math.pi - 0.5 + s_ * 0.35
            hand_b = None
            arm_back = 1.1
    elif mode == "d_bob":                  # grooving on the spot (watching the other one dance)
        s_ = math.sin(t)
        dy, tilt = -abs(s_) * 3, s_ * 5
        arm_back, arm_front = 0.5 + s_ * 0.4, 0.7 - s_ * 0.4
        leg_a = [0.18 * s_, -0.18 * s_]
        both_happy, mouth = True, 1.0
    elif mode == "d_wave":                 # both arms up, waving side to side
        s_ = math.sin(t)
        dy, tilt, jx = -abs(s_) * 4, s_ * 9, s_ * 3
        hand_b, hand_f = (22 + s_ * 8, 54), (104 + s_ * 8, 48)
        leg_a = [0.3 * s_, -0.3 * s_]
        both_happy, mouth = True, 1.3
    elif mode == "dance":                  # one of the 100 moves
        q = _dance_pose(mv or {}, t)
        dy, squash, tilt, jx, bx, xf = q["dy"], q["squash"], q["tilt"], q["jx"], q["bx"], q["xf"]
        hand_b, hand_f, arm_back, arm_front, arm_len = q["hb"], q["hf"], q["ab"], q["af"], q["alen"]
        leg_a, foot_b, foot_f = q["legs"], q["fb"], q["ff"]
        both_happy, mouth = q["happy"], q["mouth"]
        if q["fx"] == "hearts":
            fx, note_col = "hearts", "#F0527A"
    else:  # sleep (sitting, eyes closed)
        dy = 8
        both_happy, mouth = True, 0.0

    if xf:
        if xf[0] in ("headspin", "stand"):  # head on the floor, feet in the air
            p.translate(64, 66)
            p.rotate(180)
            p.translate(-64, -66)
        if xf[0] in ("spin", "headspin"):   # turning round on the spot
            c_ = math.cos(t)
            p.translate(64, 0)
            p.scale(c_ if abs(c_) > 0.18 else math.copysign(0.18, c_), 1)
            p.translate(-64, 0)
        if xf[0] == "rot":                  # leaning, flipping, cartwheeling, lying down: (deg, round x, y)
            p.translate(xf[2], xf[3])
            p.rotate(xf[1])
            p.translate(-xf[2], -xf[3])
    if jx:
        p.translate(jx, 0)
    if mode == "breathe" and k:    # the whole of him fills up like a balloon, feet staying on the floor
        p.translate(64, 122)
        p.scale(1 + 0.20 * k, 1 + 0.10 * k)
        p.translate(-64, -122)

    if mode == "float":
        for i, (sx_, sy_, r_) in enumerate(((10, 14, 3.4), (119, 28, 2.8), (11, 98, 2.6), (117, 96, 3.2))):
            if (i + int(t * 2 / math.pi)) % 4:      # twinkling
                _star(p, QPointF(sx_, sy_), r_, "#FFF4B8")
        if k:                                       # home, far below
            earth = QPainterPath()
            earth.addEllipse(QPointF(104, 131), 27, 27)
            p.setPen(QPen(QColor("#1F4E9A"), 2.2))
            p.setBrush(QColor("#3F8FD8"))
            p.drawPath(earth)
            p.save()
            p.setClipPath(earth)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#58B368"))
            p.drawEllipse(QPointF(94, 116), 9, 6)
            p.drawEllipse(QPointF(114, 122), 8, 5)
            p.setBrush(QColor(255, 255, 255, 190))
            p.drawEllipse(QPointF(104, 110), 7, 2.4)
            p.restore()
        p.translate(64, 76)
        p.rotate(math.sin(t) * 9)
        p.translate(-64, -76)

    if mode == "run":              # lean forward like it's really running
        p.translate(60, 120)
        p.rotate(8 + math.sin(t * 2) * 1.5)
        p.translate(-62, -122)

    cy = 88 + dy + squash          # body centre
    hy = 50 + dy + squash * 1.4    # head centre

    # ---- sparkles at jump apex ------------------------------------------ #
    if mode == "jump" and 0.35 < k < 0.95:
        for i, (x, y, r) in enumerate([(14, 30, 7), (114, 18, 6), (20, 74, 4.5), (116, 66, 5)]):
            _star(p, QPointF(x, y + dy * 0.3), r, PARTY[i] if outfit == "fiesta" else "#FFD54A")

    if mode == "desk":
        _chair(p, cy, QColor(chair or "#3B4A63"))

    if prop == "bed":                       # big soft pillow behind the back
        p.setPen(QPen(QColor("#6C8EAD"), 2.4))
        p.setBrush(QColor("#FDFDFB"))
        p.save()
        p.translate(38, cy + 2)
        p.rotate(-12)
        p.drawRoundedRect(QRectF(-17, -27, 34, 52), 14, 14)
        p.setPen(QPen(QColor("#C9D6E2"), 1.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(-8, -12), QPointF(-3, 14))
        p.restore()

    # ---- things carried on the back -------------------------------------- #
    if outfit == "hike":                    # backpack with a bedroll on top
        p.setPen(QPen(INK, 2.4))
        p.setBrush(QColor("#2F6B4F"))
        p.drawRoundedRect(QRectF(27 + bx, cy - 16, 20, 30), 7, 7)
        p.setBrush(QColor("#E0B24A"))
        p.drawRoundedRect(QRectF(25 + bx, cy - 22, 22, 8), 4, 4)
    elif outfit == "space":                 # life-support pack
        p.setPen(QPen(SUIT_GREY, 2.4))
        p.setBrush(SUIT_LIGHT)
        p.drawRoundedRect(QRectF(27 + bx, cy - 20, 19, 34), 6, 6)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E53935"))
        p.drawRoundedRect(QRectF(30.5 + bx, cy - 14, 4, 9), 2, 2)
    elif outfit == "fiesta" and mode != "think":      # the star, carried on a pole until it is hung up
        top_ = QPointF(25 + bx, hy - 20)
        p.setPen(QPen(INK, 4.4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(45 + bx, cy + 8), top_)
        p.setPen(QPen(QColor("#A9743A"), 2.2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(45 + bx, cy + 8), top_)
        _lantern(p, QPointF(23 + bx, hy - 27), 9.5)

    # ---- legs ------------------------------------------------------------ #
    if mode not in ("sleep", "dizzy", "laugh", "tampo", "listen", "watch", "read", "read_hp", "bed", "study", "breathe",
                    "meet", "desk", "sip", "ride"):
        for hx, a, foot in ((54 + bx, leg_a[1], foot_b), (70 + bx, leg_a[0], foot_f)):
            ln = 13.0
            if foot is not None:
                a, ln = math.atan2(foot[0] - hx, foot[1] - (cy + 12)), math.hypot(foot[0] - hx, foot[1] - (cy + 12))
            _limb(p, QPointF(hx, cy + 12), a, ln, leg_sleeve, 5.5, boot)
    else:
        p.setPen(QPen(INK, 2.2))
        p.setBrush(boot or PAW)
        p.drawEllipse(QPointF(76, cy + 18), 9, 6)

    # ---- back arm -------------------------------------------------------- #
    len_b = len_f = arm_len
    if hand_b is not None:
        arm_back, len_b = (math.atan2(hand_b[0] - 58 - bx, hand_b[1] - (cy - 6)),
                           math.hypot(hand_b[0] - 58 - bx, hand_b[1] - (cy - 6)))
        arm_front, len_f = (math.atan2(hand_f[0] - 70 - bx, hand_f[1] - (cy - 6)),
                            math.hypot(hand_f[0] - 70 - bx, hand_f[1] - (cy - 6)))
    _limb(p, QPointF(58 + bx, cy - 6), arm_back, len_b, hoodie, 5.5, glove)
    # dancing with a paw up above the head: that arm goes up behind the head, not across the face
    behind_f = mode == "dance" and hand_f is not None and hand_f[0] >= 60 and hand_f[1] < cy - 30
    if behind_f:
        _limb(p, QPointF(70 + bx, cy - 6), arm_front, len_f, hoodie, 5.5, glove)

    # ---- hoodie body ----------------------------------------------------- #
    p.setPen(QPen(navy_ink, 3))
    p.setBrush(hoodie)
    p.drawRoundedRect(QRectF(40 + bx, cy - 17 + squash * 0.3, 44, 36 - squash * 0.3), 16, 16)
    # pocket
    p.setPen(QPen(navy_ink, 2))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(50 + bx, cy + 2, 24, 11), 5, 5)
    if outfit == "space":                   # chest panel with little lights, mission patch
        p.setPen(QPen(SUIT_GREY, 1.8))
        p.setBrush(QColor("#C9D1DC"))
        p.drawRoundedRect(QRectF(51 + bx, cy + 2, 22, 11), 3, 3)
        p.setPen(Qt.NoPen)
        for i, col in enumerate(("#E53935", "#58B368", "#29A3DA")):
            p.setBrush(QColor(col))
            p.drawEllipse(QPointF(56 + bx + i * 6, cy + 7.5), 2, 2)
        p.setBrush(QColor("#1F4E9A"))
        p.drawEllipse(QPointF(49 + bx, cy - 8), 4.2, 4.2)
        _star(p, QPointF(49 + bx, cy - 8), 2.6, "#FFFFFF")
    elif outfit == "hike":                  # zip and the backpack strap
        p.setPen(QPen(navy_ink, 1.6))
        p.drawLine(QPointF(64 + bx, cy - 15), QPointF(64 + bx, cy + 1))
        p.setPen(QPen(QColor("#2F6B4F"), 4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(46 + bx, cy - 13), QPointF(50 + bx, cy + 1))
    elif outfit == "jungle":                # satchel on a strap
        p.setPen(QPen(QColor("#6B4A2A"), 3.2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(46 + bx, cy - 14), QPointF(74 + bx, cy + 8))
        p.setPen(QPen(INK, 2))
        p.setBrush(QColor("#8A5A2B"))
        p.drawRoundedRect(QRectF(67 + bx, cy + 5, 15, 12), 3.5, 3.5)
        p.setPen(QPen(QColor("#E0B24A"), 2))
        p.drawPoint(QPointF(74.5 + bx, cy + 10))

    # ---- hood behind head ------------------------------------------------ #
    p.save()
    if tilt:
        p.translate(66 + bx * 0.5, hy + 22)
        p.rotate(tilt)
        p.translate(-66, -(hy + 22))
    p.setPen(QPen(navy_ink, 3))
    p.setBrush(hoodie)
    if style == "office":                   # a white shirt collar instead of the hood
        p.setPen(QPen(SUIT_GREY, 2.6))
        p.setBrush(QColor("#FFFFFF"))
    p.drawEllipse(QRectF(32, hy + 6, 58, 30))

    # ---- ears ------------------------------------------------------------ #
    for ex, ey in ((50, hy - 26), (72, hy - 30)):
        p.setPen(QPen(INK, 2.6))
        p.setBrush(FUR)
        p.drawEllipse(QPointF(ex, ey), 8.5, 8.5)
        p.setPen(Qt.NoPen)
        p.setBrush(FUR_DARK)
        p.drawEllipse(QPointF(ex + 1, ey + 1), 4.5, 4.5)

    # ---- head with fluffy tufts ----------------------------------------- #
    head = QPainterPath()
    head.addEllipse(QPointF(68, hy), 30, 28)
    tufts = QPainterPath()
    for i, (ax, ay) in enumerate([(40, hy - 6), (38, hy + 4), (41, hy + 14)]):
        tufts.moveTo(ax + 3, ay - 5)
        tufts.lineTo(ax - 6, ay + (1 if i else -2))
        tufts.lineTo(ax + 4, ay + 5)
        tufts.closeSubpath()
    p.setPen(QPen(INK, 2.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(FUR)
    p.drawPath(head.united(tufts))

    # ---- snout patch, nose, mouth --------------------------------------- #
    p.setPen(Qt.NoPen)
    p.setBrush(FUR_DARK)
    p.drawEllipse(QPointF(87, hy + 4), 15, 15)
    p.setBrush(INK)
    p.drawEllipse(QPointF(96, hy - 4), 4.2, 3)            # nose
    if mouth_kind == "wavy":
        p.setPen(QPen(INK, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        wv = QPainterPath(QPointF(81, hy + 8))
        for i in range(1, 6):
            wv.lineTo(81 + i * 3, hy + 8 + (-2.2 if i % 2 else 2.2))
        p.drawPath(wv)
    elif mouth_kind == "o":
        p.setPen(QPen(INK, 2.2))
        p.setBrush(QColor("#C0394B"))
        p.drawEllipse(QPointF(89, hy + 10), 5, 6.5)
    elif mouth_kind == "grit":              # gritted teeth
        p.setPen(QPen(INK, 2))
        p.setBrush(QColor("white"))
        p.drawRoundedRect(QRectF(81, hy + 5, 16, 8), 3, 3)
        p.setPen(QPen(INK, 1.2))
        for gx in (85, 89, 93):
            p.drawLine(QPointF(gx, hy + 5), QPointF(gx, hy + 13))
    elif mouth_kind == "pout":              # little frown
        p.setPen(QPen(INK, 2.2, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        fr = QPainterPath(QPointF(85, hy + 11))
        fr.quadTo(89, hy + 6, 93, hy + 11)
        p.drawPath(fr)
    elif mouth > 0:
        mw, mh = 7 * mouth, 8 * mouth
        mpath = QPainterPath(QPointF(89 - mw, hy + 4))
        mpath.quadTo(89, hy + 4 + mh * 2, 89 + mw, hy + 4)
        mpath.closeSubpath()
        p.setPen(QPen(INK, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("#C0394B"))
        p.drawPath(mpath)
        p.setPen(Qt.NoPen)
        p.setBrush(PINK)
        p.drawEllipse(QPointF(89, hy + 4 + mh * 0.85), mw * 0.55, mh * 0.42)   # tongue
    else:
        p.setPen(QPen(INK, 2, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        sm = QPainterPath(QPointF(85, hy + 6))
        sm.quadTo(89, hy + 9, 93, hy + 6)
        p.drawPath(sm)

    # ---- eyes + blush ---------------------------------------------------- #
    if eyes == "wide":
        for (ex_, ey_, r) in ((60, hy - 6, 5.0), (80, hy - 9, 5.6)):
            p.setPen(QPen(INK, 2))
            p.setBrush(QColor("white"))
            p.drawEllipse(QPointF(ex_, ey_), r, r + 0.6)
            p.setPen(Qt.NoPen)
            p.setBrush(INK)
            p.drawEllipse(QPointF(ex_ + 0.8 + lookx, ey_ + look), 2.3, 2.6)
        if brows == "focus":                # level, serious brows
            p.setPen(QPen(INK, 2.6, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(53, hy - 18), QPointF(64, hy - 18.5))
            p.drawLine(QPointF(74, hy - 21.5), QPointF(86, hy - 20.5))
        if worried:
            p.setPen(QPen(INK, 2.4, Qt.SolidLine, Qt.RoundCap))      # worried brows
            p.drawLine(QPointF(53, hy - 14), QPointF(63, hy - 17))
            p.drawLine(QPointF(75, hy - 21), QPointF(86, hy - 17))
    elif eyes == "sad":                     # drooping lids, brows raised in the middle, one tear
        p.setPen(QPen(INK, 2.8, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        for (ex_, ey_, w_) in ((60, hy - 5, 9), (80, hy - 8, 8)):
            lid = QPainterPath(QPointF(ex_ - w_ / 2, ey_ - 1))
            lid.quadTo(ex_, ey_ + w_ * 0.6, ex_ + w_ / 2, ey_ - 1)
            p.drawPath(lid)
        p.setPen(QPen(INK, 2.4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(53, hy - 12), QPointF(64, hy - 17))
        p.drawLine(QPointF(75, hy - 20), QPointF(86, hy - 15))
        ty = hy + 1 + (t / (2 * math.pi) % 1) * 12
        tear = QPainterPath(QPointF(80, ty - 5))
        tear.cubicTo(84, ty, 82.5, ty + 4, 80, ty + 4)
        tear.cubicTo(77.5, ty + 4, 76, ty, 80, ty - 5)
        p.setPen(QPen(QColor("#2E6FA8"), 1.4))
        p.setBrush(QColor("#8FD3FF"))
        p.drawPath(tear)
    elif eyes == "shut":
        p.setPen(QPen(INK, 2.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        for (ex_, ey_, d) in ((60, hy - 6, 1), (80, hy - 9, -1)):
            pa = QPainterPath(QPointF(ex_ - 4 * d, ey_ - 4))
            pa.lineTo(ex_ + 3 * d, ey_)
            pa.lineTo(ex_ - 4 * d, ey_ + 4)
            p.drawPath(pa)
    elif eyes == "dizzy":
        p.setPen(QPen(INK, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        for (ex_, ey_) in ((60, hy - 6), (80, hy - 9)):
            sp = QPainterPath(QPointF(ex_, ey_))
            for i in range(1, 26):
                a = i * 0.55 + t
                sp.lineTo(ex_ + math.cos(a) * i * 0.24, ey_ + math.sin(a) * i * 0.24)
            p.drawPath(sp)
    elif eyes in ("angry", "pout", "peekback"):
        p.setPen(QPen(INK, 2.8, Qt.SolidLine, Qt.RoundCap))          # brows pulled down in the middle
        p.drawLine(QPointF(53, hy - 16), QPointF(65, hy - 11))
        p.drawLine(QPointF(74, hy - 14), QPointF(87, hy - 20))
        if eyes == "angry":
            p.setPen(Qt.NoPen)
            p.setBrush(INK)
            p.drawEllipse(QPointF(60, hy - 5), 3.2, 3.8)
            p.drawEllipse(QPointF(80, hy - 8), 3.6, 4.2)
        else:                               # eyes shut in a huff…
            p.drawLine(QPointF(55, hy - 4), QPointF(65, hy - 5))
            if eyes == "peekback":          # …but sneaking a look to see if you care
                p.setPen(QPen(INK, 2))
                p.setBrush(QColor("white"))
                p.drawEllipse(QPointF(80, hy - 7), 5, 5.4)
                p.setPen(Qt.NoPen)
                p.setBrush(INK)
                p.drawEllipse(QPointF(77.6, hy - 6.5), 2.3, 2.6)
            else:
                p.drawLine(QPointF(75, hy - 7), QPointF(85, hy - 8))
    elif both_happy:
        _happy_eye(p, 60, hy - 6)
        _happy_eye(p, 80, hy - 9, 8)
    else:
        _happy_eye(p, 60, hy - 6)
        p.setPen(Qt.NoPen)
        p.setBrush(INK)
        p.drawEllipse(QPointF(80, hy - 9), 3.6, 4.6)
        p.setBrush(QColor("white"))
        p.drawEllipse(QPointF(81.2, hy - 10.6), 1.4, 1.4)
    p.setPen(Qt.NoPen)
    p.setBrush(BLUSH)
    p.drawEllipse(QPointF(57, hy + 6), 6.5, 4)
    if mode == "tampo":                     # puffed cheek
        p.setBrush(QColor(240, 110, 120, 190))
        p.drawEllipse(QPointF(58, hy + 7), 9, 6.5)
    if glasses:                             # round reading glasses
        p.setPen(QPen(INK, 1.9))
        p.setBrush(QColor(255, 255, 255, 40))
        p.drawEllipse(QPointF(60, hy - 5), 8.2, 8.2)
        p.drawEllipse(QPointF(81, hy - 8), 8.8, 8.8)
        p.drawLine(QPointF(68.2, hy - 6), QPointF(72.2, hy - 7))
        p.drawLine(QPointF(51.8, hy - 5), QPointF(44, hy - 8))
    if hp:                                  # headphones: band over the top, big cushion on the near side
        band = QPainterPath(QPointF(46, hy - 2))
        band.cubicTo(38, hy - 30, 60, hy - 40, 80, hy - 30)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(INK, 8.5, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(band)
        p.setPen(QPen(QColor("#F2F2F2"), 4.5, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(band)
        p.setPen(QPen(INK, 2.6))
        p.setBrush(QColor("#E94B5B"))
        p.drawRoundedRect(QRectF(36, hy - 10, 17, 25), 8, 8)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 110))
        p.drawRoundedRect(QRectF(39.5, hy - 6, 4, 11), 2, 2)
    if bandana:                             # Jeo's bandana, tied round the head, knot and tails at the back
        red = QColor(bandana if isinstance(bandana, str) else "#D62839")
        p.setPen(QPen(INK, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(red)
        for pts in (((40, hy - 21), (22, hy - 17), (27, hy - 28)), ((40, hy - 18), (25, hy - 3), (33, hy - 14))):
            tail = QPainterPath(QPointF(*pts[0]))
            tail.lineTo(*pts[1])
            tail.lineTo(*pts[2])
            tail.closeSubpath()
            p.drawPath(tail)
        skull = QPainterPath()
        skull.addEllipse(QPointF(68, hy), 31, 29)
        cut = QPainterPath()
        cut.addRect(QRectF(30, hy - 34, 80, 16))
        band = skull.intersected(cut)
        p.drawPath(band)
        p.save()
        p.setClipPath(band)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("white"))
        for i, (dx_, dy_) in enumerate(((46, -22), (56, -25), (66, -22), (76, -25), (86, -22), (61, -30), (71, -30), (81, -30))):
            p.drawEllipse(QPointF(dx_, hy + dy_), 1.5, 1.5)
        p.restore()
        p.setPen(QPen(INK, 2.2))
        p.setBrush(red)
        p.drawEllipse(QPointF(40, hy - 20), 4.2, 4.2)
    if style == "hiphop":                   # snapback cap, flat brim forward
        cap = QColor("#1E1E24") if hoodie.lightness() > 60 else QColor("#F2C230")
        brim = QPainterPath(QPointF(86, hy - 29))
        brim.lineTo(113, hy - 25)
        brim.lineTo(111, hy - 19)
        brim.lineTo(86, hy - 22)
        brim.closeSubpath()
        dome = QPainterPath(QPointF(42, hy - 23))
        dome.cubicTo(43, hy - 45, 91, hy - 47, 94, hy - 25)
        dome.closeSubpath()
        p.setPen(QPen(INK, 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(cap.darker(130))
        p.drawPath(brim)
        p.setBrush(cap)
        p.drawPath(dome)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        p.drawRoundedRect(QRectF(70, hy - 36, 12, 8), 2, 2)
    elif style == "classy":                 # top hat
        p.setPen(QPen(INK, 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("#22222A"))
        p.drawRoundedRect(QRectF(51, hy - 44, 34, 19), 2.5, 2.5)
        p.drawEllipse(QPointF(68, hy - 25), 27, 4.6)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#C0392B"))
        p.drawRect(QRectF(52.3, hy - 32.5, 31.4, 4))
    if style in ("disco", "budots"):        # shades
        p.setPen(QPen(INK, 2))
        p.setBrush(QColor("#E0328C") if style == "disco" else QColor("#16161C"))
        p.drawRoundedRect(QRectF(51, hy - 12.5, 16, 11), 4, 4)
        p.drawRoundedRect(QRectF(72, hy - 15.5, 17, 12), 4, 4)
        p.drawLine(QPointF(67, hy - 8), QPointF(72, hy - 10))
        p.drawLine(QPointF(51, hy - 8), QPointF(43, hy - 10))
        p.setPen(QPen(QColor(255, 255, 255, 190), 1.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(54.5, hy - 9.5), QPointF(58, hy - 9.8))
        p.drawLine(QPointF(75.5, hy - 12.3), QPointF(79.5, hy - 12.7))
    if style in ("office", "kpop"):         # headset with a microphone
        _headset(p, hy)
    if outfit == "hike":                    # bobble hat
        p.setPen(QPen(INK, 2.4))
        p.setBrush(QColor("#F2E9D8"))
        p.drawEllipse(QPointF(68, hy - 40), 4.5, 4.5)
        dome = QPainterPath(QPointF(42, hy - 26))
        dome.cubicTo(43, hy - 45, 92, hy - 47, 95, hy - 28)
        dome.closeSubpath()
        p.setPen(QPen(INK, 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("#1F7A8C"))
        p.drawPath(dome)
        p.setBrush(QColor("#F2E9D8"))
        p.drawRoundedRect(QRectF(39, hy - 31, 59, 9), 4.5, 4.5)
    elif outfit == "jungle":                # explorer hat with a wide brim
        crown = QPainterPath(QPointF(46, hy - 26))
        crown.cubicTo(47, hy - 44, 88, hy - 46, 90, hy - 28)
        crown.closeSubpath()
        p.setPen(QPen(INK, 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("#D9C08A"))
        p.drawPath(crown)
        p.setBrush(QColor("#CDB17A"))
        p.drawEllipse(QPointF(68, hy - 26), 35, 5.5)
        p.setPen(QPen(QColor("#7A4B2A"), 3.4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(48, hy - 31.5), QPointF(88, hy - 33.5))
    elif outfit == "fiesta":                # party hat
        cone = QPainterPath(QPointF(56, hy - 24))
        cone.lineTo(72, hy - 42)
        cone.lineTo(85, hy - 27)
        cone.closeSubpath()
        p.setPen(QPen(INK, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("#F0527A"))
        p.drawPath(cone)
        p.save()
        p.setClipPath(cone)
        p.setPen(QPen(QColor("#FFD54A"), 3.2))
        for off in (0, 9):
            p.drawLine(QPointF(52, hy - 30 - off), QPointF(90, hy - 26 - off))
        p.restore()
        p.setPen(QPen(INK, 1.8))
        p.setBrush(QColor("#29A3DA"))
        p.drawEllipse(QPointF(72, hy - 42), 3.2, 3.2)
    elif outfit == "space":                 # glass helmet and collar ring
        p.setPen(QPen(SUIT_GREY, 2.2))
        p.setBrush(SUIT_LIGHT)
        p.drawRoundedRect(QRectF(46, hy + 26, 44, 8), 4, 4)
        p.setPen(QPen(SUIT_GREY, 2.6))
        p.setBrush(QColor(190, 225, 255, 55))
        p.drawEllipse(QPointF(68, hy - 3), 37, 35.5)
        shine = QPainterPath(QPointF(39, hy - 12))
        shine.quadTo(43, hy - 29, 58, hy - 34)
        p.setPen(QPen(QColor(255, 255, 255, 210), 3, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        p.drawPath(shine)
    hatted = outfit in ("hike", "jungle", "fiesta", "space") or style in ("hiphop", "classy", "office")
    if acc in ("bow", "flower", "cap", "crown") and not (hatted and acc in ("cap", "crown")) and outfit != "space":
        _headwear(p, acc, QColor(acc_col), hy)
    p.restore()
    if style == "office":                   # tie
        tie = QPainterPath(QPointF(63.3 + bx, cy - 4))
        tie.lineTo(68.7 + bx, cy - 4)
        tie.lineTo(70.5 + bx, cy + 9)
        tie.lineTo(66 + bx, cy + 15)
        tie.lineTo(61.5 + bx, cy + 9)
        tie.closeSubpath()
        p.setPen(QPen(INK, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("#C0392B"))
        p.drawPath(tie)
    elif style in ("hiphop", "touch"):      # gold chain
        chain = QPainterPath(QPointF(53 + bx, cy - 3))
        chain.quadTo(66 + bx, cy + 13, 79 + bx, cy - 3)
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(INK, 4.2, Qt.SolidLine, Qt.RoundCap))
        p.drawPath(chain)
        p.setPen(QPen(QColor("#F2C230"), 2.2, Qt.DotLine, Qt.RoundCap))
        p.drawPath(chain)
        p.setPen(QPen(INK, 1.6))
        p.setBrush(QColor("#F2C230"))
        p.drawEllipse(QPointF(66 + bx, cy + 7), 4, 4)
    elif style == "classy":                 # bow tie
        p.setPen(QPen(INK, 1.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("#C0392B"))
        for sg in (-1, 1):
            wing = QPainterPath(QPointF(66 + bx, cy + 1))
            wing.lineTo(66 + bx + sg * 9, cy - 4)
            wing.lineTo(66 + bx + sg * 9, cy + 6)
            wing.closeSubpath()
            p.drawPath(wing)
        p.drawEllipse(QPointF(66 + bx, cy + 1), 2.4, 2.4)
    if style == "touch":                    # sequins on the jacket
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 220))
        for sx_, sy_ in ((46, -9), (52, 12), (60, -12), (74, -11), (79, 10), (80, -4), (45, 4)):
            p.drawEllipse(QPointF(sx_ + bx, cy + sy_), 1.3, 1.3)
    if outfit == "fiesta":                  # garland of flowers round the neck
        p.setPen(QPen(INK, 1.2))
        for i in range(7):
            p.setBrush(QColor(PARTY[i % len(PARTY)]))
            p.drawEllipse(QPointF(47 + bx + i * 5.6, cy - 13 + math.sin(i / 6 * math.pi) * 5), 3.3, 3.3)

    # ---- things held in the lap ------------------------------------------ #
    if prop == "popcorn":
        bucket = QPainterPath(QPointF(84, cy - 2))
        bucket.lineTo(110, cy - 2)
        bucket.lineTo(106, cy + 22)
        bucket.lineTo(88, cy + 22)
        bucket.closeSubpath()
        for (kx, ky, kr) in ((88, cy - 5, 4.6), (95, cy - 8, 5.2), (102, cy - 6, 4.8), (107, cy - 3, 3.8), (98, cy - 3, 4.4)):
            p.setPen(QPen(INK, 1.6))
            p.setBrush(QColor("#FFF3C4"))
            p.drawEllipse(QPointF(kx, ky), kr, kr)
        p.setPen(QPen(INK, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("white"))
        p.drawPath(bucket)
        p.save()
        p.setClipPath(bucket)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E53935"))
        for sx_ in (84, 94, 104):
            p.drawRect(QRectF(sx_, cy - 3, 5, 26))
        p.restore()
        p.setPen(QPen(INK, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(bucket)
        if hand_f is not None and hand_f[1] < cy - 20:      # a piece on its way to the mouth
            p.setPen(QPen(INK, 1.4))
            p.setBrush(QColor("#FFF3C4"))
            p.drawEllipse(QPointF(hand_f[0] + 4, hand_f[1] - 5), 3.6, 3.6)
    elif prop == "bed":
        blanket = QPainterPath(QPointF(28, cy + 12))
        blanket.cubicTo(44, cy + 3, 60, cy + 13, 76, cy + 8)
        blanket.cubicTo(90, cy + 3, 104, cy + 12, 116, cy + 9)
        blanket.cubicTo(122, cy + 16, 121, cy + 25, 116, cy + 29)
        blanket.lineTo(26, cy + 29)
        blanket.cubicTo(21, cy + 24, 22, cy + 16, 28, cy + 12)
        p.setPen(QPen(QColor("#3F6E9A"), 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("#8EC3EE"))
        p.drawPath(blanket)
        p.save()
        p.setClipPath(blanket)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#FFFFFF"))
        for (dx_, dy_) in ((36, 20), (52, 15), (66, 23), (82, 16), (97, 22), (110, 16)):
            p.drawEllipse(QPointF(dx_, cy + dy_), 2.3, 2.3)
        p.restore()
        p.save()                                    # the phone, tilted toward the face
        p.translate(97, cy - 9)
        p.rotate(14)
        p.setPen(QPen(INK, 2.2))
        p.setBrush(QColor("#2B2B33"))
        p.drawRoundedRect(QRectF(-8, -14, 16, 28), 3.5, 3.5)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(("#9FE3FF", "#FFE08A", "#C9B6FF")[glow % 3]))
        p.drawRoundedRect(QRectF(-8, -14, 3.2, 28), 1.5, 1.5)      # the lit screen, seen from the side
        p.restore()
    elif prop == "laptop":                          # open on the lap, the screen lighting his face
        base = QPainterPath(QPointF(80, cy + 13))
        base.lineTo(110, cy + 10)
        base.lineTo(113, cy + 16)
        base.lineTo(83, cy + 19)
        base.closeSubpath()
        lid = QPainterPath(QPointF(103, cy + 11))
        lid.lineTo(111, cy + 10)
        lid.lineTo(121, cy - 14)
        lid.lineTo(113, cy - 13)
        lid.closeSubpath()
        p.setPen(QPen(INK, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("#C3CAD5"))
        p.drawPath(base)
        p.setBrush(QColor("#7A8698"))
        p.drawPath(lid)
        p.setPen(QPen(QColor("#9FE3FF"), 2.4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(104.5, cy + 8), QPointF(113, cy - 11))
    elif prop == "notes":
        pad = QPainterPath(QPointF(80, cy + 1))     # notebook resting on the lap
        pad.lineTo(108, cy - 3)
        pad.lineTo(112, cy + 14)
        pad.lineTo(84, cy + 18)
        pad.closeSubpath()
        p.setPen(QPen(INK, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("#FFF6C9"))
        p.drawPath(pad)
        p.setPen(QPen(QColor("#E53935"), 1.3))
        p.drawLine(QPointF(85.5, cy + 0.4), QPointF(89.5, cy + 17.2))
        p.setPen(QPen(QColor("#7A8794"), 1.2, Qt.SolidLine, Qt.RoundCap))
        n_lines = 4 if int(k) % 12 >= 7 else 2      # the page fills up while writing
        for li in range(n_lines):
            p.drawLine(QPointF(91 + li * 0.6, cy + 3 + li * 3.6), QPointF(105 + li * 0.6 - (li % 2) * 4, cy + 1 + li * 3.6))
        p.setPen(QPen(INK, 1.3))
        p.setBrush(QColor("#B0BEC5"))
        for ri in range(5):                         # spiral rings along the top edge
            p.drawEllipse(QPointF(83 + ri * 6.2, cy + 0.4 - ri * 0.9), 1.7, 2.3)
    elif prop == "cup" and hand_f is not None:      # the mug, held in both paws, steam curling up
        mx, my = hand_f[0] + 4, hand_f[1] + 2
        col = QColor(cup or "#E8762B")
        p.setPen(QPen(INK, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawEllipse(QPointF(mx + 9, my + 6), 4.2, 4.6)          # handle
        p.setBrush(col)
        p.drawRoundedRect(QRectF(mx - 7, my - 4, 15, 17), 3.5, 3.5)
        p.setPen(Qt.NoPen)
        p.setBrush(col.lighter(135))
        p.drawRoundedRect(QRectF(mx - 5, my - 2, 3.2, 12), 1.5, 1.5)  # shine
        p.setBrush(QColor("#6B3E22"))
        p.drawEllipse(QPointF(mx + 0.5, my - 3.4), 6, 1.8)        # the coffee
        if hand_f[1] > 70:                                        # steam (not while sipping)
            p.setPen(QPen(QColor(255, 255, 255, 210), 1.8, Qt.SolidLine, Qt.RoundCap))
            p.setBrush(Qt.NoBrush)
            for i, sx_ in enumerate((-2.5, 3.5)):
                w_ = math.sin(k * 1.3 + i * 2)
                st_ = QPainterPath(QPointF(mx + sx_, my - 7))
                st_.cubicTo(mx + sx_ + 3 * w_, my - 11, mx + sx_ - 3 * w_, my - 14, mx + sx_ + w_, my - 19)
                p.drawPath(st_)
    elif prop == "book":
        by = cy - 10
        for sgn, col in ((-1, "#FFFFFF"), (1, "#F4F1E8")):
            page = QPainterPath(QPointF(95, by + 3))
            page.lineTo(95 + sgn * 17, by - 3)
            page.lineTo(95 + sgn * 17, by + 21)
            page.lineTo(95, by + 27)
            page.closeSubpath()
            cover = QPainterPath(QPointF(95, by + 5))
            cover.lineTo(95 + sgn * 19.5, by - 1)
            cover.lineTo(95 + sgn * 19.5, by + 24)
            cover.lineTo(95, by + 30)
            cover.closeSubpath()
            p.setPen(QPen(INK, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(QColor("#2E8B74"))
            p.drawPath(cover)
            p.setPen(QPen(INK, 1.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(QColor(col))
            p.drawPath(page)
            p.setPen(QPen(QColor("#9AA0A6"), 1.1, Qt.SolidLine, Qt.RoundCap))
            for li in range(4):
                p.drawLine(QPointF(95 + sgn * 3.5, by + 8 + li * 4.3 - 1), QPointF(95 + sgn * 14, by + 4.5 + li * 4.3 - 1))

    # ---- front arm + drawstrings ---------------------------------------- #
    p.setPen(QPen(QColor("white"), 2, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(66 + bx, cy - 13), QPointF(66 + bx, cy - 4))
    paw_f = QPointF(70 + bx + math.sin(arm_front) * len_f, cy - 6 + math.cos(arm_front) * len_f)
    if outfit == "hike" and mode == "run":           # walking stick
        a_, b_ = QPointF(paw_f.x() + 1, paw_f.y() - 12), QPointF(paw_f.x() + 7, 121)
        p.setPen(QPen(INK, 4.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(a_, b_)
        p.setPen(QPen(QColor("#A9743A"), 2.4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(a_, b_)
    elif fx == "flag":                               # summit flag, waving
        p.setPen(QPen(INK, 4.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(105, 28), QPointF(105, 122))
        p.setPen(QPen(QColor("#D9D9D9"), 2.2, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(105, 28), QPointF(105, 122))
        w_ = 2.5 if int(k) % 2 else -2.5
        flag = QPainterPath(QPointF(106, 29))
        flag.quadTo(115, 31 + w_, 126, 37 - w_)
        flag.quadTo(115, 41 + w_, 106, 47)
        flag.closeSubpath()
        p.setPen(QPen(INK, 2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("#E53935"))
        p.drawPath(flag)
    elif fx == "lantern":                            # the star lantern hanging from the top, with tassels
        sw = (1.5 if int(k) % 2 else -1.5)
        c_ = QPointF(112 + sw, 28)
        p.setPen(QPen(INK, 1.6))
        p.drawLine(QPointF(112, 0), c_)
        for dx_ in (-7, 7):
            p.setPen(QPen(QColor(PARTY[0 if dx_ < 0 else 2]), 2.2, Qt.SolidLine, Qt.RoundCap))
            p.drawLine(QPointF(c_.x() + dx_, c_.y() + 9), QPointF(c_.x() + dx_ * 1.3 + sw, c_.y() + 22))
        _lantern(p, c_, 10.5)
    if not behind_f:
        _limb(p, QPointF(70 + bx, cy - 6), arm_front, len_f, hoodie, 5.5, glove)
    if fx == "found" or (mode == "float" and k):     # the star itself, in his paw
        c_ = QPointF(paw_f.x() + 6, paw_f.y() - 11) if fx == "found" else QPointF(paw_f.x() + 9, paw_f.y() + 3)
        p.setPen(QPen(QColor("#FFB300"), 2, Qt.SolidLine, Qt.RoundCap))
        for i in range(8):
            a = i * math.pi / 4 + (0.4 if int(k) % 2 else 0) + t
            p.drawLine(QPointF(c_.x() + math.cos(a) * 13, c_.y() + math.sin(a) * 13),
                       QPointF(c_.x() + math.cos(a) * 17, c_.y() + math.sin(a) * 17))
        _lantern(p, c_, 9)
    if prop == "notes" and hand_f is not None:      # pencil in the writing paw
        tip = QPointF(hand_f[0] + 1, hand_f[1] + 8)
        end = QPointF(hand_f[0] + 9, hand_f[1] - 12)
        p.setPen(QPen(INK, 6.4, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(tip, end)
        p.setPen(QPen(QColor("#FFC93C"), 3.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(tip.x() + 1.6, tip.y() - 4), end)
        p.setPen(QPen(QColor("#F28B82"), 3.6, Qt.SolidLine, Qt.RoundCap))
        p.drawLine(QPointF(end.x() - 0.8, end.y() + 2), end)

    if mode == "sleep":
        _zz(p, zk, hoodie)
    # ---- emotion extras -------------------------------------------------- #
    for i in range(sweat):
        sx, sy = ((104, hy - 24), (36, hy - 20))[i % 2]
        sy += (t * 2.5 + i * 3) % 7
        drop = QPainterPath(QPointF(sx, sy - 7))
        drop.cubicTo(sx + 6, sy + 1, sx + 3, sy + 6, sx, sy + 6)
        drop.cubicTo(sx - 3, sy + 6, sx - 6, sy + 1, sx, sy - 7)
        p.setPen(QPen(QColor("#2E6FA8"), 1.6))
        p.setBrush(QColor("#8FD3FF"))
        p.drawPath(drop)
    if fx == "!":
        f = QFont()
        f.setBold(True)
        f.setPixelSize(26)
        ex = QPainterPath()
        ex.addText(QPointF(102, hy - 14), f, "!")
        ex.addText(QPointF(22, hy - 10), f, "!")
        p.setPen(QPen(QColor("white"), 4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(Qt.NoBrush)
        p.drawPath(ex)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#E53935"))
        p.drawPath(ex)
    elif fx == "...":                       # thought dots, appearing one by one
        for i in range(min(3, int(k) + 1)):
            p.setPen(QPen(INK, 1.8))
            p.setBrush(QColor("white"))
            p.drawEllipse(QPointF(100 + i * 8, hy - 26 - i * 7), 2.6 + i * 1.2, 2.6 + i * 1.2)
    elif fx == "anger":                     # red cross-vein mark
        p.setPen(QPen(QColor("#E53935"), 3, Qt.SolidLine, Qt.RoundCap))
        p.setBrush(Qt.NoBrush)
        pulse = 1 + 0.15 * math.sin(t * 2)
        for (mx, my, sc) in ((106, hy - 26, 1.0), (22, hy - 16, 0.75)):
            for qx, qy in ((1, 1), (1, -1), (-1, 1), (-1, -1)):
                v = QPainterPath(QPointF(mx + qx * 2.5 * sc, my + qy * 8 * sc * pulse))
                v.quadTo(mx + qx * 2.5 * sc, my + qy * 2.5 * sc, mx + qx * 8 * sc * pulse, my + qy * 2.5 * sc)
                p.drawPath(v)
    elif fx == "hmph":                      # little huff of air
        p.setPen(QPen(INK, 1.4))
        p.setBrush(QColor("white"))
        d = (t * 4) % 8
        for i, r in enumerate((4.5, 3.4, 2.4)):
            p.drawEllipse(QPointF(108 + i * 6 + d * 0.6, hy + 2 - i * 3 - d * 0.4), r, r)
    elif fx == "haha":
        f = QFont()
        f.setBold(True)
        for i, (hx_, hy_, sz) in enumerate([(98, hy - 22, 17), (4, hy - 14, 14), (104, hy + 14, 12)]):
            if (i + int(t * 3 / math.pi)) % 3 == 0:
                continue                    # the "ha"s flicker in turn
            f.setPixelSize(sz)
            ha = QPainterPath()
            ha.addText(QPointF(hx_, hy_), f, "ha")
            p.setPen(QPen(QColor("white"), 3.5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.setBrush(Qt.NoBrush)
            p.drawPath(ha)
            p.setPen(Qt.NoPen)
            p.setBrush(QColor("#FF8A00"))
            p.drawPath(ha)
    elif fx == "talk":                      # speaking: sound coming out
        n_ = int(t * 6 / math.pi) % 3 + 1
        p.setBrush(Qt.NoBrush)
        p.setPen(QPen(QColor("#29A3DA"), 2.4, Qt.SolidLine, Qt.RoundCap))
        for i in range(n_):
            r_ = 7 + i * 6
            p.drawArc(QRectF(103 - r_, hy + 8 - r_, 2 * r_, 2 * r_), -38 * 16, 76 * 16)
    elif fx == "bulb":                      # a bright idea
        c_ = QPointF(108, hy - 30)
        p.setPen(QPen(QColor("#FFB300"), 2.2, Qt.SolidLine, Qt.RoundCap))
        for i in range(7):
            a = math.pi * (0.95 + i * 0.35)
            p.drawLine(QPointF(c_.x() + math.cos(a) * 12, c_.y() + math.sin(a) * 12),
                       QPointF(c_.x() + math.cos(a) * 16.5, c_.y() + math.sin(a) * 16.5))
        p.setPen(QPen(INK, 1.8))
        p.setBrush(QColor("#9E9E9E"))
        p.drawRoundedRect(QRectF(c_.x() - 3.8, c_.y() + 6, 7.6, 6.5), 1.5, 1.5)
        p.setBrush(QColor("#FFE54A"))
        p.drawEllipse(c_, 8.5, 8.5)
    elif fx in ("notes", "hearts"):         # music drifting up from the headphones
        col = QColor(note_col or "#FF8A00")
        for i, (nx, sway) in enumerate(((18, 5), (108, -5), (30, -4))):
            if mood in ("chill", "sad") and i == 2:
                continue
            ph_ = (t / (2 * math.pi) + i / 3) % 1.0
            x = nx + math.sin(ph_ * 2 * math.pi) * sway
            y = hy - 2 - ph_ * 34
            sz = 0.75 + 0.35 * math.sin(ph_ * math.pi)
            alpha = int(255 * min(1.0, 3.2 * (1 - ph_), 6 * ph_ + 0.2))
            c2 = QColor(col)
            c2.setAlpha(max(0, alpha))
            white = QColor(255, 255, 255, max(0, alpha))
            if fx == "hearts" and i != 1:
                h_ = QPainterPath(QPointF(x, y + 6 * sz))
                h_.cubicTo(x - 11 * sz, y - 2 * sz, x - 5 * sz, y - 9 * sz, x, y - 3 * sz)
                h_.cubicTo(x + 5 * sz, y - 9 * sz, x + 11 * sz, y - 2 * sz, x, y + 6 * sz)
                p.setPen(QPen(white, 3, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
                p.setBrush(c2)
                p.drawPath(h_)
                continue
            note = QPainterPath()
            note.addEllipse(QPointF(x, y), 4.6 * sz, 3.6 * sz)
            stem = QPainterPath(QPointF(x + 4.2 * sz, y))
            stem.lineTo(x + 4.2 * sz, y - 14 * sz)
            stem.quadTo(x + 9 * sz, y - 13 * sz, x + 10 * sz, y - 7 * sz)
            p.setBrush(Qt.NoBrush)
            p.setPen(QPen(white, 5, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(stem)
            p.setPen(QPen(white, 3))
            p.drawPath(note)
            p.setPen(QPen(c2, 2.4, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
            p.drawPath(stem)
            p.setPen(Qt.NoPen)
            p.setBrush(c2)
            p.drawPath(note)
    elif fx == "stars":                     # stars circling the head
        for i in range(3):
            a = t + i * 2 * math.pi / 3
            _star(p, QPointF(68 + math.cos(a) * 30, hy - 34 + math.sin(a) * 7), 7.5 if math.sin(a) > 0 else 6)
    p.end()
    return pm


def _rocket(face: QPixmap, hy: float, t: float, flame: bool, face2: QPixmap | None = None) -> QPixmap:
    """Primo's rocket, his face at the window. flame=False: still on the pad, steam puffing.
    face2: a passenger (Jeo) at a second window below."""
    pm, p = _canvas()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.translate(math.sin(t * 3) * (1.3 if flame else 0.4), 0)
    if flame:
        f = 0.72 + 0.28 * math.sin(t * 2)
        for w_, len_, col in ((15, 44, "#FF8A00"), (9, 30, "#FFD54A"), (4.5, 16, "#FFFFFF")):
            fl = QPainterPath(QPointF(64 - w_, 106))
            fl.quadTo(64 + math.sin(t * 4) * 3, 106 + len_ * f, 64 + w_, 106)
            fl.closeSubpath()
            p.setPen(Qt.NoPen)
            p.setBrush(QColor(col))
            p.drawPath(fl)
    else:
        p.setPen(QPen(QColor("#B8C0CC"), 1.4))
        p.setBrush(QColor(255, 255, 255, 225))
        for i, (sx_, sy_, r_) in enumerate(((34, 118, 8), (94, 118, 8), (22, 121, 5.5), (106, 121, 5.5), (48, 121, 5), (80, 121, 5))):
            g_ = 0.75 + 0.25 * math.sin(t + i * 1.3)
            p.drawEllipse(QPointF(sx_, sy_), r_ * g_, r_ * g_)
    for sgn in (-1, 1):                                  # fins
        fin = QPainterPath(QPointF(64 + sgn * 22, 72))
        fin.lineTo(64 + sgn * 41, 108)
        fin.lineTo(64 + sgn * 22, 99)
        fin.closeSubpath()
        p.setPen(QPen(INK, 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(QColor("#E53935"))
        p.drawPath(fin)
    noz = QPainterPath(QPointF(52, 98))
    noz.lineTo(76, 98)
    noz.lineTo(80, 108)
    noz.lineTo(48, 108)
    noz.closeSubpath()
    p.setBrush(QColor("#6E7A8A"))
    p.drawPath(noz)
    body = QPainterPath(QPointF(64, 3))
    body.cubicTo(84, 14, 88, 34, 88, 50)
    body.lineTo(88, 95)
    body.quadTo(88, 100, 83, 100)
    body.lineTo(45, 100)
    body.quadTo(40, 100, 40, 95)
    body.lineTo(40, 50)
    body.cubicTo(40, 34, 44, 14, 64, 3)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#F4F6FA"))
    p.drawPath(body)
    p.save()
    p.setClipPath(body)
    p.setBrush(QColor("#E53935"))
    p.drawRect(QRectF(38, 0, 52, 25))                    # nose cone
    if face2 is None:
        p.setBrush(QColor("#1F4E9A"))
        p.drawRect(QRectF(38, 80, 52, 7))                # stripe
    p.restore()
    p.setPen(QPen(INK, 2.8, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPath(body)
    ports = [(52, 18.5, face)] if face2 is None else [(44, 15.5, face), (78, 15.5, face2)]
    for wy, wr, who in ports:                            # the windows, with them looking out
        win = QPainterPath()
        win.addEllipse(QPointF(64, wy), wr, wr)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("#17264A"))
        p.drawPath(win)
        p.save()
        p.setClipPath(win)
        r_ = wr + 0.5
        p.drawPixmap(QRectF(64 - r_, wy - r_, 2 * r_, 2 * r_), who, QRectF(68 - 39, hy - 3 - 39, 78, 78))
        p.restore()
        p.setPen(QPen(INK, 5.2 if face2 is None else 4.4))
        p.setBrush(Qt.NoBrush)
        p.drawPath(win)
        p.setPen(QPen(QColor("#AEB8C6"), 3 if face2 is None else 2.4))
        p.drawPath(win)
    p.end()
    return pm


def _chute(body: QPixmap, t: float) -> QPixmap:
    """Floating down under a parachute (body = a frame of the arms-out stretch pose)."""
    pm, p = _canvas()
    p.setRenderHint(QPainter.SmoothPixmapTransform)
    p.translate(64, 6)
    p.rotate(math.sin(t) * 5)
    p.translate(-64, -6)
    s_ = math.sin(t)
    dy = -1 - abs(s_) * 1.5
    sc, ox, oy = 0.6, 26, 51
    hl = QPointF(ox + 23 * sc, oy + (62 + dy - s_ * 7) * sc)
    hr = QPointF(ox + 114 * sc, oy + (68 + dy + s_ * 7) * sc)
    p.setPen(QPen(INK, 1.3, Qt.SolidLine, Qt.RoundCap))
    for top_, hand in ((QPointF(12, 40), hl), (QPointF(44, 41), hl), (QPointF(84, 41), hr), (QPointF(116, 40), hr)):
        p.drawLine(top_, hand)
    can = QPainterPath(QPointF(10, 41))
    can.cubicTo(12, -8, 116, -8, 118, 41)
    for i in range(4):
        x0 = 118 - i * 27
        can.quadTo(x0 - 13.5, 31, x0 - 27, 41)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#FFFFFF"))
    p.drawPath(can)
    p.save()
    p.setClipPath(can)
    p.setBrush(QColor("#E53935"))
    for i in (0, 2):                                     # red and white panels
        gore = QPainterPath(QPointF(64, -2))
        gore.lineTo(10 + i * 27, 44)
        gore.lineTo(37 + i * 27, 44)
        gore.closeSubpath()
        p.drawPath(gore)
    p.restore()
    p.setPen(QPen(INK, 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
    p.setBrush(Qt.NoBrush)
    p.drawPath(can)
    p.drawPixmap(QRectF(ox, oy, BASE * sc, BASE * sc), body, QRectF(0, 0, BASE, BASE))
    p.end()
    return pm


def _headwear(p: QPainter, acc: str, col: QColor, hy: float):
    """An avatar's own headwear: bow | flower | cap | crown."""
    pen = QPen(INK, 2.2, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)
    if acc == "bow":                                     # big bow by the right ear
        cx_, cy_ = 86, hy - 27
        p.setPen(pen)
        p.setBrush(col)
        for sg in (-1, 1):
            loop = QPainterPath(QPointF(cx_, cy_))
            loop.cubicTo(cx_ + sg * 6, cy_ - 13, cx_ + sg * 16, cy_ - 8, cx_ + sg * 13, cy_ + 1)
            loop.cubicTo(cx_ + sg * 12, cy_ + 8, cx_ + sg * 5, cy_ + 5, cx_, cy_)
            p.drawPath(loop)
        p.setPen(Qt.NoPen)
        p.setBrush(QColor(255, 255, 255, 120))
        p.drawEllipse(QPointF(cx_ + 8, cy_ - 5), 2.2, 1.6)
        p.setPen(pen)
        p.setBrush(col.darker(120))
        p.drawEllipse(QPointF(cx_, cy_), 3.8, 3.8)
    elif acc == "flower":                                # a flower tucked by the ear
        cx_, cy_ = 85, hy - 25
        p.setPen(QPen(INK, 1.6))
        p.setBrush(col)
        for i in range(5):
            a = i / 5 * 2 * math.pi - math.pi / 2
            p.drawEllipse(QPointF(cx_ + math.cos(a) * 6, cy_ + math.sin(a) * 6), 4.6, 4.6)
        p.setBrush(QColor("#FFD54A"))
        p.drawEllipse(QPointF(cx_, cy_), 3.6, 3.6)
    elif acc == "cap":                                   # baseball cap, brim forward
        brim = QPainterPath(QPointF(86, hy - 29))
        brim.lineTo(108, hy - 23)
        brim.quadTo(104, hy - 18, 86, hy - 22)
        brim.closeSubpath()
        dome = QPainterPath(QPointF(42, hy - 23))
        dome.cubicTo(43, hy - 45, 91, hy - 47, 94, hy - 25)
        dome.closeSubpath()
        p.setPen(QPen(INK, 2.6, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin))
        p.setBrush(col.darker(125))
        p.drawPath(brim)
        p.setBrush(col)
        p.drawPath(dome)
        p.setPen(Qt.NoPen)
        p.setBrush(col.lighter(150))
        p.drawEllipse(QPointF(68, hy - 41), 3, 2)
    elif acc == "crown":                                 # a little golden crown
        cr = QPainterPath(QPointF(54, hy - 30))
        for x_, y_ in ((54, hy - 44), (61, hy - 36), (68, hy - 47), (75, hy - 36), (82, hy - 44), (82, hy - 30)):
            cr.lineTo(x_, y_)
        cr.closeSubpath()
        p.setPen(pen)
        p.setBrush(col)
        p.drawPath(cr)
        p.setBrush(QColor("#E53935"))
        p.drawEllipse(QPointF(68, hy - 35), 2.4, 2.4)


def _dance_frames(pose) -> dict:
    """What every dancer has before the outfit change: grooving on the spot, and waving goodbye."""
    tau = 2 * math.pi
    return {"d_bob": [pose("d_bob", t=i / 8 * tau) for i in range(8)],
            "d_wave": [pose("d_wave", t=i / 12 * tau) for i in range(12)]}


def _fur_set(color: str):
    global FUR, FUR_DARK, PAW
    FUR = QColor(color)
    FUR_DARK, PAW = FUR.darker(142), FUR.darker(110)


def set_avatars(main: dict, friend: dict) -> None:
    """main / friend: {'fur', 'acc', 'acc_color'} (see avatars.py)."""
    _MAIN.update({k: main.get(k, _MAIN[k]) for k in _MAIN})
    _FRIEND.update({k: friend.get(k, _FRIEND[k]) for k in _FRIEND})
    _CUR.clear()
    _CUR.update(_MAIN)
    _fur_set(_MAIN["fur"])


@contextmanager
def _wearing(av: dict):
    """Draw as another avatar (fur and headwear) for a while."""
    keep = dict(_CUR), FUR
    _CUR.clear()
    _CUR.update(av)
    _fur_set(av["fur"])
    try:
        yield
    finally:
        _CUR.clear()
        _CUR.update(keep[0])
        _fur_set(keep[1].name())


def _jeo_fur():
    """Draw as the friend (Jeo, or whoever you picked) for a while."""
    return _wearing(_FRIEND)


FRIEND_HOODIE = {"color": "#12857E"}     # the friend's jacket colour (set by the app from the settings)


def friend_frames(space: bool = False) -> FrameSet:
    """Jeo OngBack, Primo's friend and dance rival: lighter fur, teal hoodie, red bandana.
    space=True: in a space suit (bandana under the helmet) for the rocket trip with Primo."""
    tau = 2 * math.pi
    with _jeo_fur():
        if space:
            pose = partial(_capy, QColor("#F2F4F8"), outfit="space", bandana=True)
            extra = {"d_bob": [pose("d_bob", t=i / 8 * tau) for i in range(8)],
                     "float": [pose("float", t=i / 12 * tau + 2.0) for i in range(12)],
                     "chute": [_chute(pose("stretch", t=i / 12 * tau), i / 12 * tau + 1.5) for i in range(12)]}
        else:
            pose = partial(_capy, QColor(FRIEND_HOODIE["color"]), bandana=True)
            extra = _dance_frames(pose)
            extra["laugh"] = [pose("laugh", t=i / 8 * tau) for i in range(8)]
        run = [pose("run", t=i / RUN_FRAMES * tau) for i in range(RUN_FRAMES)]
        jump = [pose("jump", k=i / 11) for i in range(12)]
        return FrameSet(run, [pose("sleep", zk=0)], jump, extra)


def office_frames() -> dict:
    """Primo in a call: blazer, shirt and tie, headset; listening, and talking when you do."""
    pose = partial(_capy, QColor("#2F3A4F"), style="office")
    tau = 2 * math.pi
    return {"meet_listen": [pose("meet", t=i / 12 * tau) for i in range(12)],
            "meet_talk": [pose("meet", t=i / 12 * tau, k=1) for i in range(12)]}


def desk_frames(color: str = "#1F2A5A", look: str = "hoodie", outfit: str = "", chair: str = "#3B4A63",
                glasses: bool = True) -> list[QPixmap]:
    """Work mode: Primo on an office chair, typing on his laptop.
    look: hoodie (his own colour) | office (blazer and tie) | adventure (the outfit of the day)."""
    style = "office" if look == "office" else ""
    hoodie = QColor("#2F3A4F") if look == "office" else QColor(color)
    pose = partial(_capy, hoodie, "desk", outfit=outfit if look == "adventure" else "", style=style,
                   chair=chair, specs=glasses)
    return [pose(k=i) for i in range(12)]


def move_frames(mv: dict, style: str, color: str, jeo: bool = False, bandana: bool | str = False) -> list[QPixmap]:
    """One dance move (see dance.MOVES) in the outfit of a showdown style (see dance.STYLES)."""
    tau, n = 2 * math.pi, (8 if mv.get("arms") == "bob" else 12)
    pose = partial(_capy, QColor(color), "dance", style=style, bandana=bandana, mv=mv)
    if jeo:
        with _jeo_fur():
            return [pose(t=i / n * tau) for i in range(n)]
    return [pose(t=i / n * tau) for i in range(n)]


def poof_frames() -> list[QPixmap]:
    """A magician's puff of smoke and stars, drawn over the pet while the outfit changes."""
    out = []
    for i in range(8):
        k = i / 7
        pm, p = _canvas()
        p.setPen(Qt.NoPen)
        for j in range(8):
            a = j * math.pi / 4 + k * 0.8
            rad, r = 14 + 30 * k, 21 * (1 - 0.55 * k)
            p.setBrush(QColor(255, 255, 255, int(240 * (1 - k) ** 0.6)))
            p.drawEllipse(QPointF(64 + math.cos(a) * rad, 72 + math.sin(a) * rad * 0.9), r, r)
        if k < 0.5:
            p.setBrush(QColor(255, 255, 255, int(250 * (1 - 2 * k))))
            p.drawEllipse(QPointF(64, 72), 30, 32)
        for j in range(6):
            a = j * math.pi / 3 + 0.5 - k
            rad = 26 + 34 * k
            _star(p, QPointF(64 + math.cos(a) * rad, 70 + math.sin(a) * rad), 8 * (1 - k) + 2.5,
                  PARTY[j % len(PARTY)] if j % 2 else "#FFD54A")
        p.end()
        out.append(pm)
    return out


def capy_frames(hoodie_color: str, outfit: str = "", cup: str = "") -> FrameSet:
    h = QColor(hoodie_color)
    pose = partial(_capy, h, outfit=outfit, cup=cup)      # every pose wears the outfit of the day
    run = [pose("run", t=i / RUN_FRAMES * 2 * math.pi) for i in range(RUN_FRAMES)]
    jump = [pose("jump", k=i / 11) for i in range(12)]
    sleep = [pose("sleep", zk=k) for k in range(2)]
    tau = 2 * math.pi
    extra = {
        "climb": [pose("climb", t=i / 12 * tau) for i in range(12)],
        "slip": [pose("slip", t=i / 4 * tau) for i in range(4)],
        "fall": [pose("fall", t=i / 6 * tau) for i in range(6)],
        "dizzy": [pose("dizzy", t=i / 10 * tau) for i in range(10)],
        "think": [pose("think", k=i) for i in (0, 1, 2, 2)],
        "slide": [pose("slide", t=i / 6 * tau, k=i % 2) for i in range(6)],
        "cling": [pose("cling", t=i / 6 * tau) for i in range(6)],
        "sneak": [pose("sneak", t=i / 10 * tau) for i in range(10)],
        "peek": [pose("peek", k=i) for i in range(2)],
        "laugh": [pose("laugh", t=i / 8 * tau) for i in range(8)],
        "angry": [pose("angry", t=i / 8 * tau) for i in range(8)],
        "tampo": [pose("tampo", t=0.0), pose("tampo", t=1.0), pose("tampo", t=2.0),
                  pose("tampo", t=0.5), pose("tampo", t=1.5, k=1), pose("tampo", t=2.0, k=1)],
        # joining in with what you are doing (see activity.py)
        "watch": [pose("watch", k=i) for i in range(8)],
        "bed": [pose("bed", k=i) for i in range(12)],
        "study": [pose("study", k=i) for i in range(12)],
        "read": [pose("read", t=i / 12 * tau) for i in range(12)],
        "read_hp": [pose("read_hp", t=i / 12 * tau) for i in range(12)],
        # wellbeing: the breathing exercise (frames ordered by how full the lungs are) and the stretch
        "breathe_in": [pose("breathe", k=i / 15) for i in range(16)],
        "breathe_out": [pose("breathe", t=1.0, k=i / 15) for i in range(16)],
        "stretch": [pose("stretch", t=i / 12 * tau) for i in range(12)],
        "sip": [pose("sip", k=i) for i in range(10)],          # coffee break
    }
    for mi, mood in enumerate(("happy", "hype", "chill", "sad", "love")):
        extra[f"listen_{mood}"] = [pose("listen", t=i / 12 * tau, k=mi) for i in range(12)]
    extra.update(_dance_frames(pose))   # dance showdowns with Jeo (see dance.py)
    if outfit == "space":               # the rocket trip: pad, launch, floating in orbit, parachute home
        extra["float"] = [pose("float", t=i / 12 * tau) for i in range(12)]
        extra["think"] = [pose("float", t=i / 12 * tau, k=1) for i in range(12)]
        extra["rocket"] = [_rocket(pose("jump", k=0.6), 44, i / 8 * tau, True) for i in range(8)]
        extra["pad"] = [_rocket(pose("peek", k=i % 2), 55, i / 6 * tau, False) for i in range(6)]
        extra["chute"] = [_chute(pose("stretch", t=i / 12 * tau), i / 12 * tau) for i in range(12)]
        with _jeo_fur():                # the same rocket with Jeo on board, at a second window
            jeo = partial(_capy, h, outfit="space", bandana=True)
            j_up, j_pad = jeo("jump", k=0.6), [jeo("peek", k=i) for i in range(2)]
        extra["rocket2"] = [_rocket(pose("jump", k=0.6), 44, i / 8 * tau, True, j_up) for i in range(8)]
        extra["pad2"] = [_rocket(pose("peek", k=i % 2), 55, i / 6 * tau, False, j_pad[(i + 1) % 2]) for i in range(6)]
    return FrameSet(run, sleep, jump, extra)


def builtin_frames(kind: str, color: str) -> FrameSet:
    if kind == "capy":
        return capy_frames(color)
    c = QColor(color)
    run, sleep = [], []
    for i in range(RUN_FRAMES):
        t = i / RUN_FRAMES * 2 * math.pi
        run.append(_dots(c, t) if kind == "dots" else _quadruped(kind, c, t))
    for k in range(2):
        sleep.append(_dots(c, 0, True, k) if kind == "dots" else _quadruped(kind, c, 0, True, k))
    return FrameSet(run, sleep)


# --------------------------------------------------------------------------- #
# custom characters
# --------------------------------------------------------------------------- #
def _fit(img) -> QPixmap:
    pm = QPixmap.fromImage(img) if not isinstance(img, QPixmap) else img
    return pm.scaled(BASE, BASE, Qt.KeepAspectRatio, Qt.SmoothTransformation)


def custom_frames(path: str, sprite_frames: int = 0) -> FrameSet:
    """Load a custom runner. Raises ValueError with a readable message on failure."""
    if not path or not os.path.exists(path):
        raise ValueError(f"File not found: {path}")

    frames: list[QPixmap] = []
    if os.path.isdir(path):
        names = sorted(n for n in os.listdir(path) if n.lower().endswith((".png", ".webp", ".jpg")))
        sleep_names = [n for n in names if n.lower().startswith("sleep")]
        jump_names = [n for n in names if n.lower().startswith("jump")]
        run_names = [n for n in names if n not in sleep_names and n not in jump_names]
        load = lambda ns: [_fit(QPixmap(os.path.join(path, n))) for n in ns]  # noqa: E731
        frames = load(run_names)
        fs = FrameSet(frames, load(sleep_names), load(jump_names))
    else:
        reader = QImageReader(path)
        if reader.supportsAnimation() and reader.imageCount() > 1:
            while True:
                img = reader.read()
                if img.isNull():
                    break
                frames.append(_fit(img))
        else:
            sheet = QPixmap(path)
            if sheet.isNull():
                raise ValueError(f"Cannot read image: {path}")
            n = sprite_frames
            if n <= 0:  # auto: square frames laid out horizontally
                n = max(1, round(sheet.width() / max(1, sheet.height())))
            w = sheet.width() // n
            frames = [_fit(sheet.copy(i * w, 0, w, sheet.height())) for i in range(n)]
        fs = FrameSet(frames)

    if not fs.run:
        raise ValueError("No frames found in the custom character.")
    fs.ensure_sleep()
    return fs


def load_frames(settings: dict) -> tuple[FrameSet, str | None]:
    """Return frames for current settings; falls back to capybara on error."""
    kind = settings.get("character", "capy")
    if kind == "custom":
        try:
            return custom_frames(settings.get("custom_path", ""), int(settings.get("sprite_frames", 0))), None
        except ValueError as e:
            return capy_frames("#1F2A5A"), str(e)
    if kind not in BUILTIN:
        kind = "capy"
    color = settings.get("color", "#1F2A5A")
    friend = avatars.get(settings, "friend")
    set_avatars(avatars.look(avatars.get(settings, "main")) if kind == "capy" else _MAIN, avatars.look(friend))
    FRIEND_HOODIE["color"] = friend["hoodie"]
    if kind == "capy":                  # Primo dresses for the adventure of the day
        th = themes.get(themes.current(settings))
        jacket = color if settings.get("my_color_always") else (th["jacket"] or color)
        return capy_frames(jacket, th["outfit"], settings.get("cup_color", "#E8762B")), None
    return builtin_frames(kind, color), None


def with_badge(pm: QPixmap, count: int, right: bool = False) -> QPixmap:
    if count <= 0:
        return pm
    out = QPixmap(pm)
    p = QPainter(out)
    p.setRenderHint(QPainter.Antialiasing)
    d = out.width() * 0.4
    # behind the head (opposite the way the runner faces) so it never covers the face
    rect = QRectF(out.width() - d - 2 if right else 2, 2, d, d)
    p.setBrush(QColor("#E53935"))
    p.setPen(QPen(QColor("white"), 4))
    p.drawEllipse(rect)
    f = QFont()
    f.setBold(True)
    f.setPixelSize(int(rect.height() * 0.6))
    p.setFont(f)
    p.drawText(rect, Qt.AlignCenter, "9+" if count > 9 else str(count))
    p.end()
    return out


def friend_rider_frames(n: int = 8) -> list[QPixmap]:
    """The friend riding along behind (see rides.py), waving now and then."""
    h = QColor(FRIEND_HOODIE["color"])
    with _jeo_fur():
        return [_capy(h, "ride", t=i / n * 2 * math.pi + 1.0, k=1 if i in (5, 6) else 0, bandana=True)
                for i in range(n)]


def rider_frames(color: str = "#1F2A5A", outfit: str = "", n: int = 8) -> tuple[list[QPixmap], list[QPixmap]]:
    """Primo sitting on an animal's back (see rides.py): holding on, and waving hello."""
    h = QColor(color)
    hold = [_capy(h, "ride", t=i / n * 2 * math.pi, outfit=outfit) for i in range(n)]
    wave = [_capy(h, "ride", t=i / n * 2 * math.pi, k=1, outfit=outfit) for i in range(n)]
    return hold, wave


def avatar_preview(av: dict, n: int = 10) -> list[QPixmap]:
    """An avatar (see avatars.py) running, then waving: for the avatar picker."""
    tau = 2 * math.pi
    with _wearing({"fur": av["fur"], "acc": av["acc"], "acc_color": av["acc_color"]}):
        h = QColor(av["hoodie"])
        run = [_capy(h, "run", t=i / n * tau) for i in range(n)]
        wave = [_capy(h, "d_wave", t=i / 12 * tau) for i in range(12)]
    return run + run + wave
