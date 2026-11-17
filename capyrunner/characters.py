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

from PySide6.QtCore import QPointF, QRectF, Qt
from PySide6.QtGui import (QColor, QFont, QImageReader, QPainter, QPainterPath,
                           QPen, QPixmap)

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


def _limb(p: QPainter, a: QPointF, angle: float, length: float, sleeve: QColor | None, paw_r: float):
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
    p.setBrush(PAW)
    p.drawEllipse(b, paw_r, paw_r)


def _capy(hoodie: QColor, mode: str, t: float = 0.0, k: float = 0.0, zk: int = 0) -> QPixmap:
    """mode: run | jump | sleep | climb | slip | fall | dizzy | think | slide | cling.
    t = animation phase, k = jump progress 0..1 (or a small variant counter)."""
    pm, p = _canvas()
    navy_ink = hoodie.darker(170)
    arm_len, eyes, mouth_kind, jx, sweat, fx, look = 15, "normal", "smile", 0.0, 0, "", 0.0
    hand_b = hand_f = None         # rope poses: where the paws grip (the rope hangs at x = ROPE_X)
    foot_b = foot_f = None         # …and where the hind feet grip
    bx, tilt = 0.0, 0.0            # body pressed toward the rope; head tilt (negative = looking up)
    lookx = 0.0                    # wide eyes: pupils glancing forward (+) / back (-)

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
    else:  # sleep (sitting, eyes closed)
        dy = 8
        both_happy, mouth = True, 0.0

    if jx:
        p.translate(jx, 0)

    if mode == "run":              # lean forward like it's really running
        p.translate(60, 120)
        p.rotate(8 + math.sin(t * 2) * 1.5)
        p.translate(-62, -122)

    cy = 88 + dy + squash          # body centre
    hy = 50 + dy + squash * 1.4    # head centre

    # ---- sparkles at jump apex ------------------------------------------ #
    if mode == "jump" and 0.35 < k < 0.95:
        for (x, y, r) in [(14, 30, 7), (114, 18, 6), (20, 74, 4.5), (116, 66, 5)]:
            _star(p, QPointF(x, y + dy * 0.3), r)

    # ---- legs ------------------------------------------------------------ #
    if mode not in ("sleep", "dizzy", "laugh", "tampo"):
        for hx, a, foot in ((54 + bx, leg_a[1], foot_b), (70 + bx, leg_a[0], foot_f)):
            ln = 13.0
            if foot is not None:
                a, ln = math.atan2(foot[0] - hx, foot[1] - (cy + 12)), math.hypot(foot[0] - hx, foot[1] - (cy + 12))
            _limb(p, QPointF(hx, cy + 12), a, ln, None, 5.5)
    else:
        p.setPen(QPen(INK, 2.2))
        p.setBrush(PAW)
        p.drawEllipse(QPointF(76, cy + 18), 9, 6)

    # ---- back arm -------------------------------------------------------- #
    len_b = len_f = arm_len
    if hand_b is not None:
        arm_back, len_b = (math.atan2(hand_b[0] - 58 - bx, hand_b[1] - (cy - 6)),
                           math.hypot(hand_b[0] - 58 - bx, hand_b[1] - (cy - 6)))
        arm_front, len_f = (math.atan2(hand_f[0] - 70 - bx, hand_f[1] - (cy - 6)),
                            math.hypot(hand_f[0] - 70 - bx, hand_f[1] - (cy - 6)))
    _limb(p, QPointF(58 + bx, cy - 6), arm_back, len_b, hoodie, 5.5)

    # ---- hoodie body ----------------------------------------------------- #
    p.setPen(QPen(navy_ink, 3))
    p.setBrush(hoodie)
    p.drawRoundedRect(QRectF(40 + bx, cy - 17 + squash * 0.3, 44, 36 - squash * 0.3), 16, 16)
    # pocket
    p.setPen(QPen(navy_ink, 2))
    p.setBrush(Qt.NoBrush)
    p.drawRoundedRect(QRectF(50 + bx, cy + 2, 24, 11), 5, 5)

    # ---- hood behind head ------------------------------------------------ #
    p.save()
    if tilt:
        p.translate(66 + bx * 0.5, hy + 22)
        p.rotate(tilt)
        p.translate(-66, -(hy + 22))
    p.setPen(QPen(navy_ink, 3))
    p.setBrush(hoodie)
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
        p.setPen(QPen(INK, 2.4, Qt.SolidLine, Qt.RoundCap))          # worried brows
        p.drawLine(QPointF(53, hy - 14), QPointF(63, hy - 17))
        p.drawLine(QPointF(75, hy - 21), QPointF(86, hy - 17))
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
    p.restore()

    # ---- front arm + drawstrings ---------------------------------------- #
    p.setPen(QPen(QColor("white"), 2, Qt.SolidLine, Qt.RoundCap))
    p.drawLine(QPointF(66 + bx, cy - 13), QPointF(66 + bx, cy - 4))
    _limb(p, QPointF(70 + bx, cy - 6), arm_front, len_f, hoodie, 5.5)

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
    elif fx == "stars":                     # stars circling the head
        for i in range(3):
            a = t + i * 2 * math.pi / 3
            _star(p, QPointF(68 + math.cos(a) * 30, hy - 34 + math.sin(a) * 7), 7.5 if math.sin(a) > 0 else 6)
    p.end()
    return pm


def capy_frames(hoodie_color: str) -> FrameSet:
    h = QColor(hoodie_color)
    run = [_capy(h, "run", t=i / RUN_FRAMES * 2 * math.pi) for i in range(RUN_FRAMES)]
    jump = [_capy(h, "jump", k=i / 11) for i in range(12)]
    sleep = [_capy(h, "sleep", zk=k) for k in range(2)]
    tau = 2 * math.pi
    extra = {
        "climb": [_capy(h, "climb", t=i / 12 * tau) for i in range(12)],
        "slip": [_capy(h, "slip", t=i / 4 * tau) for i in range(4)],
        "fall": [_capy(h, "fall", t=i / 6 * tau) for i in range(6)],
        "dizzy": [_capy(h, "dizzy", t=i / 10 * tau) for i in range(10)],
        "think": [_capy(h, "think", k=i) for i in (0, 1, 2, 2)],
        "slide": [_capy(h, "slide", t=i / 6 * tau, k=i % 2) for i in range(6)],
        "cling": [_capy(h, "cling", t=i / 6 * tau) for i in range(6)],
        "sneak": [_capy(h, "sneak", t=i / 10 * tau) for i in range(10)],
        "peek": [_capy(h, "peek", k=i) for i in range(2)],
        "laugh": [_capy(h, "laugh", t=i / 8 * tau) for i in range(8)],
        "angry": [_capy(h, "angry", t=i / 8 * tau) for i in range(8)],
        "tampo": [_capy(h, "tampo", t=0.0), _capy(h, "tampo", t=1.0), _capy(h, "tampo", t=2.0),
                  _capy(h, "tampo", t=0.5), _capy(h, "tampo", t=1.5, k=1), _capy(h, "tampo", t=2.0, k=1)],
    }
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
    return builtin_frames(kind, settings.get("color", "#1F2A5A")), None


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
