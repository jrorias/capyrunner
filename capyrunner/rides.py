"""Rides: now and then Primo rides an animal across the screen.

Flying (dragon, eagle, parrot) up near the top, running (lion, tiger, wolf) along the bottom, and
swimming (whale) on a strip of sea at the bottom. The ride is its own see-through window that ignores the
mouse and never takes the focus, so you keep working right through it.

Everything is drawn in code at 256 x 176 and scaled once per ride; nothing is kept once the ride is over.
"""
from __future__ import annotations

import math
import random

from PySide6.QtCore import QPointF, QRectF, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QPainter, QPainterPath, QPen, QPixmap, QTransform
from PySide6.QtWidgets import QWidget

W, H = 256, 176
INK = QColor("#2A1A10")
FRAMES = 8

# key: label, how it travels, default colour
RIDES = {
    "dragon": ("🐉  Dragon", "fly", "#3FA34D"),
    "eagle": ("🦅  Eagle", "fly", "#6B4423"),
    "parrot": ("🦜  Parrot", "fly", "#D62839"),
    "lion": ("🦁  Lion", "run", "#D9A441"),
    "tiger": ("🐅  Tiger", "run", "#E8762B"),
    "wolf": ("🐺  Wolf", "run", "#8A929C"),
    "whale": ("🐋  Whale", "swim", "#3D6F9E"),
}
SAY = {
    "dragon": "🐉 Hold on tight… dragon ride!", "eagle": "🦅 Wheee, up with the eagle!",
    "parrot": "🦜 Polly wants a cracker… and a passenger!", "lion": "🦁 The king of the jungle gives me a lift!",
    "tiger": "🐅 Grrr… fast tiger!", "wolf": "🐺 Awoooo! Run with the pack!", "whale": "🐋 All aboard the whale!",
}


def _pen(w: float = 2.4, c: QColor = INK) -> QPen:
    return QPen(c, w, Qt.SolidLine, Qt.RoundCap, Qt.RoundJoin)


def _eye(p: QPainter, x: float, y: float, r: float = 3.2):
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("white"))
    p.drawEllipse(QPointF(x, y), r, r)
    p.setBrush(INK)
    p.drawEllipse(QPointF(x + r * 0.3, y), r * 0.6, r * 0.6)


def _put_rider(p: QPainter, rider, seat: QPointF, scale: float = 0.8):
    """Primo's seat (x 62, y 110 in his own frame) on the animal's back.
    rider = a picture, or (rider, passenger): the friend sits just behind, a little smaller."""
    if isinstance(rider, tuple):
        rider, passenger = rider
        _put_rider(p, passenger, QPointF(seat.x() - 34, seat.y() + 2), scale * 0.9)
    p.save()
    p.translate(seat.x() - 62 * scale, seat.y() - 110 * scale)
    p.scale(scale, scale)
    p.drawPixmap(0, 0, rider)
    p.restore()


# --------------------------------------------------------------------------- #
# flyers
# --------------------------------------------------------------------------- #
def _wing(p: QPainter, root: QPointF, flap: float, span: float, fill: QColor, kind: str):
    """A wing seen from the side, hinged at root. flap -1 (down) … 1 (up)."""
    rx, ry = root.x(), root.y()
    tip = QPointF(rx - span * 0.2, ry - span * 0.85 * flap - 4)
    back = QPointF(rx - span * 0.5, ry)                      # where the trailing edge meets the body
    w = QPainterPath(QPointF(rx + 16, ry))
    w.cubicTo(rx + 14, ry - span * 0.4 * flap, tip.x() + span * 0.25, tip.y() + 2 * flap, tip.x(), tip.y())
    if kind == "dragon":                                     # bat-like: a scalloped edge between the fingers
        pts = [QPointF(tip.x() + (back.x() - tip.x()) * a, tip.y() + (back.y() - tip.y()) * a) for a in (0.33, 0.66, 1.0)]
        prev = tip
        for q in pts:
            mid = QPointF((prev.x() + q.x()) / 2 + span * 0.05, (prev.y() + q.y()) / 2 + span * 0.12 * (1 if flap >= 0 else -1))
            w.quadTo(mid, q)
            prev = q
    else:                                                    # feathers: fingered tips along the trailing edge
        for i in range(5):
            a0 = (i + 0.5) / 5
            q = QPointF(tip.x() + (back.x() - tip.x()) * a0, tip.y() + (back.y() - tip.y()) * a0)
            w.lineTo(q.x() - span * 0.08, q.y() + span * 0.05 * (1 if flap >= 0 else -1))
            w.lineTo(q.x() + 2, q.y())
        w.lineTo(back)
    w.lineTo(rx - 20, ry + 2)
    w.closeSubpath()
    p.setPen(_pen(2.4))
    p.setBrush(fill)
    p.drawPath(w)
    if kind == "dragon":
        p.setPen(_pen(1.6, fill.darker(160)))
        for a in (0.33, 0.66):
            p.drawLine(QPointF(rx, ry - 2), QPointF(tip.x() + (back.x() - tip.x()) * a, tip.y() + (back.y() - tip.y()) * a))
    else:
        p.setPen(_pen(1.3, fill.lighter(140)))
        p.drawLine(QPointF(rx + 6, ry - 2), QPointF(tip.x() + span * 0.06, tip.y() + span * 0.12 * flap))


def _dragon(p: QPainter, t: float, col: QColor, rider: QPixmap):
    flap = math.sin(t)
    belly = QColor("#F2D27A")
    _wing(p, QPointF(132, 96), flap * 0.8 + 0.1, 92, col.darker(135), "dragon")       # far wing
    tail = QPainterPath(QPointF(80, 104))                                               # tail with a spade tip
    sw = math.sin(t + 1) * 8
    tail.cubicTo(52, 112 + sw, 30, 98 - sw, 10, 104 + sw)
    tail.cubicTo(30, 110 - sw, 54, 124 + sw, 82, 120)
    p.setPen(_pen())
    p.setBrush(col)
    p.drawPath(tail)
    spade = QPainterPath(QPointF(12, 104 + sw))
    spade.lineTo(0, 96 + sw)
    spade.lineTo(2, 110 + sw)
    spade.closeSubpath()
    p.drawPath(spade)
    for lx in (100, 146):                                                               # tucked legs
        p.drawEllipse(QPointF(lx, 132), 7, 5)
    p.drawEllipse(QPointF(122, 112), 50, 24)                                            # body
    p.setPen(Qt.NoPen)
    p.setBrush(belly)
    p.drawEllipse(QPointF(124, 124), 38, 10)
    p.setPen(_pen(1.3, belly.darker(140)))
    for bx in range(96, 154, 9):
        p.drawLine(QPointF(bx, 117), QPointF(bx + 3, 132))
    neck = QPainterPath(QPointF(156, 98))                                               # neck and head
    neck.cubicTo(176, 90, 182, 76, 194, 66)
    neck.lineTo(206, 76)
    neck.cubicTo(194, 88, 184, 108, 166, 116)
    neck.closeSubpath()
    p.setPen(_pen())
    p.setBrush(col)
    p.drawPath(neck)
    for hx_, hy_ in ((190, 50), (198, 48)):                                             # horns
        horn = QPainterPath(QPointF(hx_, 60))
        horn.quadTo(hx_ - 8, hy_ - 2, hx_ - 14, hy_ - 10)
        horn.quadTo(hx_ - 2, hy_ - 2, hx_ + 6, 58)
        p.setBrush(QColor("#F6EBD0"))
        p.drawPath(horn)
    p.setBrush(col)
    p.drawEllipse(QPointF(204, 64), 17, 13)
    snout = QPainterPath(QPointF(210, 56))
    snout.quadTo(234, 56, 236, 66)
    snout.quadTo(232, 76, 212, 76)
    snout.closeSubpath()
    p.drawPath(snout)
    p.setPen(_pen(1.6))
    p.drawLine(QPointF(220, 71), QPointF(234, 70))                                      # smile
    p.setBrush(INK)
    p.drawEllipse(QPointF(230, 61), 1.4, 1.4)                                           # nostril
    _eye(p, 204, 60)
    if int(t / (2 * math.pi) * FRAMES) % FRAMES in (2, 3):                              # a little puff of smoke
        p.setPen(_pen(1.2, QColor("#B8C0CC")))
        p.setBrush(QColor(255, 255, 255, 200))
        for i, r_ in enumerate((4, 5.5, 4.5)):
            p.drawEllipse(QPointF(242 + i * 4, 56 - i * 6), r_, r_)
    p.setPen(_pen(2))                                                                   # back spikes (behind the rider)
    p.setBrush(QColor("#F2D27A"))
    for sx_ in (78, 88, 160):
        sp = QPainterPath(QPointF(sx_ - 4, 96 + (4 if sx_ < 90 else 0)))
        sp.lineTo(sx_, 86 + (4 if sx_ < 90 else 0))
        sp.lineTo(sx_ + 4, 96 + (4 if sx_ < 90 else 0))
        p.drawPath(sp)
    _put_rider(p, rider, QPointF(122, 94))
    _wing(p, QPointF(118, 100), flap, 100, col, "dragon")                               # near wing, over his legs


def _bird(p: QPainter, t: float, kind: str, col: QColor, rider: QPixmap):
    flap = math.sin(t)
    eagle = kind == "eagle"
    wing_c = col if eagle else QColor("#1E6FD9")
    head_c = QColor("#FAFAF5") if eagle else col
    tail_c = QColor("#FAFAF5") if eagle else QColor("#1E6FD9")
    _wing(p, QPointF(130, 100), flap * 0.8 + 0.1, 96, wing_c.darker(130), "bird")
    tail = QPainterPath(QPointF(84, 108))                                               # fan of tail feathers
    for i in range(4):
        tail.lineTo(36 - i * 2, 98 + i * 8)
        tail.lineTo(46, 102 + i * 8)
    tail.lineTo(86, 122)
    tail.closeSubpath()
    p.setPen(_pen())
    p.setBrush(tail_c)
    p.drawPath(tail)
    if not eagle:
        p.setBrush(QColor("#FFD54A"))
        p.drawEllipse(QPointF(58, 112), 10, 4)
    p.setBrush(QColor("#F2B705"))                                                       # talons tucked in
    for lx in (112, 132):
        p.drawEllipse(QPointF(lx, 134), 6, 4)
    p.setBrush(col)
    p.drawEllipse(QPointF(124, 112), 46, 22)                                            # body
    p.setBrush(head_c)
    p.drawEllipse(QPointF(176, 90), 20, 18)                                             # head
    beak = QPainterPath(QPointF(190, 84))
    if eagle:
        beak.quadTo(210, 82, 212, 96)
        beak.quadTo(206, 92, 192, 98)
    else:
        beak.quadTo(212, 80, 208, 100)
        beak.quadTo(202, 92, 192, 98)
    beak.closeSubpath()
    p.setBrush(QColor("#F2B705") if eagle else QColor("#2B2B33"))
    p.drawPath(beak)
    if not eagle:
        p.setPen(Qt.NoPen)
        p.setBrush(QColor("white"))
        p.drawEllipse(QPointF(182, 88), 7, 6)
    _eye(p, 182, 86, 3.4)
    if eagle:
        p.setPen(_pen(2.2))
        p.drawLine(QPointF(174, 80), QPointF(188, 82))                                  # a proud brow
    _put_rider(p, rider, QPointF(122, 96))
    _wing(p, QPointF(116, 104), flap, 104, wing_c, "bird")


# --------------------------------------------------------------------------- #
# runners
# --------------------------------------------------------------------------- #
def _beast(p: QPainter, t: float, kind: str, col: QColor, rider: QPixmap):
    s = math.sin(t)
    lift = abs(math.sin(t)) * 4
    dark = col.darker(150)
    p.translate(0, -lift)
    tail = QPainterPath(QPointF(76, 112))                                               # tail
    if kind == "wolf":
        tail.cubicTo(56, 106 + s * 6, 40, 112 + s * 6, 30, 122 + s * 8)
        tail.cubicTo(46, 128 + s * 4, 62, 124, 78, 122)
        tail.closeSubpath()
        p.setPen(_pen())
        p.setBrush(col)
        p.drawPath(tail)
    else:
        tail.cubicTo(56, 104 + s * 8, 44, 92 + s * 10, 34, 96 + s * 10)
        p.setPen(_pen(4))
        p.setBrush(Qt.NoBrush)
        p.drawPath(tail)
        p.setPen(_pen(4, col))
        p.drawPath(tail)
        p.setPen(_pen())
        p.setBrush(dark if kind == "lion" else INK)
        p.drawEllipse(QPointF(33, 96 + s * 10), 6, 7)
    legs = ((92, s), (106, -s), (150, -s), (164, s))                                    # galloping legs
    for i, (lx, a) in enumerate(legs):
        far = i in (1, 2)
        c = col.darker(120) if far else col
        top = QPointF(lx, 118)
        foot = QPointF(lx + a * 16, 162 + lift - abs(a) * 4)
        p.setPen(_pen(12, INK))
        p.drawLine(top, foot)
        p.setPen(_pen(8, c))
        p.drawLine(top, foot)
        p.setPen(_pen(2))
        p.setBrush(c)
        p.drawEllipse(foot, 7, 4.5)
    p.setPen(_pen())
    p.setBrush(col)
    p.drawEllipse(QPointF(128, 110), 52, 22)                                            # body
    p.setPen(Qt.NoPen)
    p.setBrush(col.lighter(125))
    p.drawEllipse(QPointF(130, 124), 36, 7)
    if kind == "tiger":                                                                 # stripes
        body = QPainterPath()
        body.addEllipse(QPointF(128, 110), 50, 20)
        p.save()
        p.setClipPath(body)
        p.setPen(_pen(4, INK))
        for sx_ in range(88, 176, 13):
            st = QPainterPath(QPointF(sx_, 90))
            st.quadTo(sx_ + 5, 100, sx_ - 1, 112)
            p.drawPath(st)
        p.restore()
    hx, hy = 184, 88                                                                    # head
    if kind == "lion":
        mane = QPainterPath()
        for i in range(14):
            a = i / 14 * 2 * math.pi
            r = 31 if i % 2 else 25
            pt = QPointF(hx - 4 + math.cos(a) * r, hy + math.sin(a) * r)
            mane.moveTo(pt) if i == 0 else mane.lineTo(pt)
        mane.closeSubpath()
        p.setPen(_pen())
        p.setBrush(QColor("#9A5B1E"))
        p.drawPath(mane)
    p.setPen(_pen())
    p.setBrush(col)
    for ex in (-10, 8):                                                                 # ears
        ear = QPainterPath(QPointF(hx + ex - 7, hy - 12))
        ear.lineTo(hx + ex - 2, hy - (32 if kind == "wolf" else 24))
        ear.lineTo(hx + ex + 6, hy - 12)
        ear.closeSubpath()
        p.drawPath(ear)
    p.drawEllipse(QPointF(hx, hy), 20, 18)
    snout = QPainterPath(QPointF(hx + 8, hy - 4))                                       # muzzle
    reach = 26 if kind == "wolf" else 18
    snout.quadTo(hx + reach + 6, hy - 2, hx + reach + 4, hy + 8)
    snout.quadTo(hx + reach - 4, hy + 16, hx + 6, hy + 12)
    snout.closeSubpath()
    p.setBrush(col.lighter(130))
    p.drawPath(snout)
    p.setBrush(INK)
    p.drawEllipse(QPointF(hx + reach + 2, hy + 1), 3.6, 3)                              # nose
    p.setPen(_pen(1.6))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(hx + reach - 10, hy + 4, 10, 7), 200 * 16, 140 * 16)               # grin
    if kind == "tiger":
        p.setPen(_pen(2.4, INK))
        for dx in (-10, -4):
            p.drawLine(QPointF(hx + dx, hy - 16), QPointF(hx + dx + 2, hy - 8))
    _eye(p, hx + 4, hy - 5, 3.4)
    _put_rider(p, rider, QPointF(126, 94))
    p.translate(0, lift)


# --------------------------------------------------------------------------- #
# swimmer
# --------------------------------------------------------------------------- #
def _whale(p: QPainter, t: float, col: QColor, rider: QPixmap):
    s = math.sin(t)
    bob = s * 3
    sea, sea2 = QColor(41, 128, 200, 150), QColor(120, 200, 245, 170)
    fluke = QPainterPath(QPointF(48, 122 + bob))                                        # tail flukes, beating
    fy = 96 + s * 14 + bob
    fluke.quadTo(26, 118 + bob, 22, fy - 10)
    fluke.quadTo(16, fy, 4, fy - 4)
    fluke.quadTo(12, fy + 10, 30, fy + 8)
    fluke.quadTo(30, 126 + bob, 52, 134 + bob)
    fluke.closeSubpath()
    p.setPen(_pen())
    p.setBrush(col)
    p.drawPath(fluke)
    body = QPainterPath(QPointF(40, 130 + bob))
    body.cubicTo(60, 92 + bob, 150, 82 + bob, 214, 104 + bob)
    body.cubicTo(236, 112 + bob, 236, 148 + bob, 206, 154 + bob)
    body.cubicTo(150, 166 + bob, 80, 160 + bob, 40, 130 + bob)
    p.drawPath(body)
    p.save()
    p.setClipPath(body)
    p.setPen(Qt.NoPen)
    p.setBrush(QColor("#DCE8F2"))
    p.drawEllipse(QPointF(170, 160 + bob), 64, 18)                                      # pale grooved belly
    p.setPen(_pen(1.2, QColor("#9FB4C8")))
    for i in range(5):
        p.drawLine(QPointF(120 + i * 2, 148 + i * 3 + bob), QPointF(226, 140 + i * 3 + bob))
    p.restore()
    p.setPen(_pen(2))
    p.setBrush(col.darker(115))
    fin = QPainterPath(QPointF(150, 140 + bob))
    fin.quadTo(140, 160 + bob, 124, 166 + bob)
    fin.quadTo(146, 160 + bob, 166, 144 + bob)
    p.drawPath(fin)
    _eye(p, 200, 128 + bob, 3.4)
    p.setPen(_pen(1.8))
    p.setBrush(Qt.NoBrush)
    p.drawArc(QRectF(200, 134 + bob, 26, 10), 200 * 16, 120 * 16)                       # smile
    phase = (t / (2 * math.pi)) % 1.0                                                   # the spout
    if phase < 0.5:
        h_ = 34 * (1 - abs(phase - 0.25) * 4) + 10
        p.setPen(_pen(1.4, QColor("#5BA7DE")))
        p.setBrush(QColor(200, 235, 255, 220))
        jet = QPainterPath(QPointF(176, 96 + bob))
        jet.quadTo(170, 96 - h_ * 0.6 + bob, 160, 96 - h_ + bob)
        jet.quadTo(176, 90 - h_ + bob, 192, 96 - h_ + bob)
        jet.quadTo(182, 96 - h_ * 0.6 + bob, 180, 96 + bob)
        p.drawPath(jet)
    _put_rider(p, rider, QPointF(110, 94 + bob))
    for i, (c, y0) in enumerate(((sea, 150), (sea2, 160))):                             # the sea, over his belly
        wave = QPainterPath(QPointF(0, H))
        wave.lineTo(0, y0)
        for x in range(0, W + 16, 16):
            wave.quadTo(x + 8, y0 - 6 * math.sin(t + x / 30 + i), x + 16, y0)
        wave.lineTo(W, H)
        wave.closeSubpath()
        p.setPen(_pen(1.6, QColor("#1E5F96")) if i == 0 else Qt.NoPen)
        p.setBrush(c)
        p.drawPath(wave)


def ride_frames(kind: str, color: str, riders: list[QPixmap], passengers: list[QPixmap] | None = None) -> list[QPixmap]:
    """FRAMES pictures of Primo on the animal, facing right (passengers: the friend riding along)."""
    col = QColor(color or RIDES[kind][2])
    out = []
    for i in range(FRAMES):
        t = i / FRAMES * 2 * math.pi
        pm = QPixmap(W, H)
        pm.fill(Qt.transparent)
        p = QPainter(pm)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        rider = riders[i % len(riders)]
        if passengers:
            rider = (rider, passengers[i % len(passengers)])
        if kind == "dragon":
            _dragon(p, t, col, rider)
        elif kind in ("eagle", "parrot"):
            _bird(p, t, kind, col, rider)
        elif kind == "whale":
            _whale(p, t, col, rider)
        else:
            _beast(p, t, kind, col, rider)
        p.end()
        out.append(pm)
    return out


# --------------------------------------------------------------------------- #
# the window that crosses the screen
# --------------------------------------------------------------------------- #
class RideWindow(QWidget):
    """See-through, click-through, never focused: the ride goes over your windows without getting in the way."""
    finished = Signal()

    TICK_MS = 33

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)   # macOS hides tool windows when another app is in front
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowTitle("CapyRunner")
        self.frames: list[QPixmap] = []
        self.i = 0
        self.kind = ""
        self.timer = QTimer(self)
        self.timer.setTimerType(Qt.PreciseTimer)
        self.timer.timeout.connect(self._tick)

    @property
    def running(self) -> bool:
        return self.timer.isActive()

    def start(self, kind: str, frames: list[QPixmap], area, size: int, go_left: bool, lift: int = 0):
        """area = the screen's work area (QRect); size = Primo's height in px (the ride is scaled to match)."""
        sc = max(0.5, size / 128 * 1.15)
        w, h = int(W * sc), int(H * sc)
        mirror = QTransform().scale(-1, 1)
        self.frames = [f.scaled(w, h, Qt.IgnoreAspectRatio, Qt.SmoothTransformation) for f in frames]
        if go_left:
            self.frames = [f.transformed(mirror) for f in self.frames]
        self.kind, self.i, self.n = kind, 0, 0
        self.resize(w, h)
        how = RIDES[kind][1]
        self.dir = -1 if go_left else 1
        self.x = float(area.right() + 1) if go_left else float(area.left() - w)
        self.end_x = float(area.left() - w) if go_left else float(area.right() + 1)
        self.speed = {"fly": 6.0, "run": 6.5, "swim": 3.2}[how] * max(0.8, sc)
        if how == "fly":
            self.base_y = area.top() + area.height() * random.uniform(0.08, 0.22)
            self.wave = area.height() * 0.05
        else:
            self.base_y = area.bottom() + 1 - h - lift + (int(h * 0.04) if how == "swim" else 0)
            self.wave = 0.0
        self.y = self.base_y
        self.move(int(self.x), int(self.y))
        self.show()
        self.raise_()
        self.timer.start(self.TICK_MS)

    def stop(self):
        self.timer.stop()
        self.hide()
        self.frames = []
        self.finished.emit()

    def _tick(self):
        self.n += 1
        self.x += self.speed * self.dir
        if self.wave:
            self.y = self.base_y + math.sin(self.n / 28) * self.wave
        if (self.dir > 0 and self.x >= self.end_x) or (self.dir < 0 and self.x <= self.end_x):
            self.stop()
            return
        if self.n % 3 == 0:                       # ~10 pictures a second, smooth movement at 30
            self.i = (self.i + 1) % len(self.frames)
            self.update()
        self.move(int(self.x), int(self.y))

    def paintEvent(self, _):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        if self.frames:
            p.drawPixmap(0, 0, self.frames[self.i])
