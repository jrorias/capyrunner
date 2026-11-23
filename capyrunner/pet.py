"""Floating desktop pet: a small always-on-top window you can drag anywhere."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPen, QPixmap
from PySide6.QtWidgets import QWidget


class PetWindow(QWidget):
    open_panel = Signal()
    context_menu = Signal(QPoint)
    moved = Signal(int, int)
    clicked = Signal()
    grabbed = Signal()            # user started dragging (pause roaming)
    released = Signal()           # mouse button let go (hand keyboard focus back)
    missed = Signal()             # pressed on the empty area around the sprite
    wheeled = Signal()            # scrolled over the pet (let the scroll through)

    BUBBLE_H = 64

    def __init__(self, size: int = 96):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowDoesNotAcceptFocus)      # touchable, but never takes the keyboard
        self.setFocusPolicy(Qt.NoFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)   # macOS hides tool windows when another app is in front
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("CapyRunner")
        self._pix: QPixmap | None = None
        self._bubble = ""
        self._caption = ""            # small standing line (what is playing), shown when no bubble is up
        self.font_px = 13
        self._clip_l = self._clip_r = 0   # how much of the window hangs off the left / right screen edge
        self._hop = 0
        self._spin = 0.0
        self.top_layout = False       # True while running along the top edge: pet on top, bubble below
        self._bubble_timer = QTimer(self, singleShot=True, timeout=self._clear_bubble)
        self._save_timer = QTimer(self, singleShot=True, interval=600)
        self._save_timer.timeout.connect(lambda: self.moved.emit(self.x(), self.y()))
        self._press: QPoint | None = None
        self._down = QPoint()
        self._dragging = False
        self.width_pct = 100          # sprite width as a % of its height (100 = as drawn)
        self.bubble_bg, self.bubble_fg, self.bubble_border = QColor("#FFFFFF"), QColor("#1B1B1B"), QColor("#3A2414")
        self.set_pet_size(size)

    @property
    def sprite_w(self) -> int:
        """How wide the sprite is drawn (the height is pet_size)."""
        return max(24, round(self.pet_size * self.width_pct / 100))

    def set_bubble_colors(self, bg: str, fg: str, border: str) -> None:
        self.bubble_bg, self.bubble_fg, self.bubble_border = QColor(bg), QColor(fg), QColor(border)
        self.update()

    def set_passthrough(self, on: bool) -> None:
        """Click-through: the pet never takes focus, clicks or scroll, so whatever is under it keeps working.
        Changing window flags hides the window; the caller shows it again."""
        if on == bool(self.windowFlags() & Qt.WindowTransparentForInput):
            return
        self.setWindowFlag(Qt.WindowTransparentForInput, on)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, on)
        self._press = None
        self._dragging = False

    def set_pet_size(self, size: int, width_pct: int | None = None) -> None:
        self.pet_size = max(32, min(320, size))
        if width_pct is not None:
            self.width_pct = max(50, min(200, int(width_pct)))
        w = max(self.sprite_w + 40, 240)
        self.setFixedSize(w, self.pet_size + self.BUBBLE_H)
        self.update()

    def set_frame(self, pm: QPixmap, hop: int = 0, spin: float = 0.0) -> None:
        self._pix, self._hop, self._spin = pm, hop, spin
        self.update()

    def set_top_layout(self, on: bool) -> None:
        if on != self.top_layout:
            self.top_layout = on
            self.update()

    def say(self, text: str, ms: int = 6000) -> None:
        self._bubble = text
        self._bubble_timer.start(ms)
        self.update()

    def set_caption(self, text: str) -> None:
        if text != self._caption:
            self._caption = text
            self.update()

    def set_font_px(self, px: int) -> None:
        px = max(10, min(18, int(px)))
        if px != self.font_px:
            self.font_px = px
            self.update()

    def set_clip(self, left: int, right: int) -> None:
        left, right = max(0, int(left)), max(0, int(right))
        if (left, right) != (self._clip_l, self._clip_r):
            self._clip_l, self._clip_r = left, right
            self.update()

    def _clear_bubble(self):
        self._bubble = ""
        self.update()

    # ---- painting ----------------------------------------------------- #
    def paintEvent(self, _):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode_Source)      # wipe the previous frame completely
        p.fillRect(self.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        p.setRenderHint(QPainter.Antialiasing)
        p.setRenderHint(QPainter.SmoothPixmapTransform)
        text = self._bubble or self._caption
        if text:
            small = not self._bubble                 # the quiet "now playing" line is a size smaller
            f = QFont()
            f.setPixelSize(max(9, self.font_px - (2 if small else 0)))
            f.setWeight(QFont.Medium if small else QFont.DemiBold)
            p.setFont(f)
            fm = QFontMetrics(f)
            # only the part of the window that is on the screen may be used
            lo, hi = 4 + self._clip_l, self.width() - 4 - self._clip_r
            max_w = max(60, hi - lo)
            lines_h = self.BUBBLE_H - 12 - 8
            max_lines = 1 if small else max(1, lines_h // fm.lineSpacing())
            text = fm.elidedText(" ".join(text.split()), Qt.ElideRight, int((max_w - 18) * max_lines * 0.92))
            flags = Qt.AlignCenter | (Qt.TextWordWrap if max_lines > 1 else Qt.TextSingleLine)
            br = fm.boundingRect(QRect(0, 0, max_w - 18, lines_h), flags, text)
            bw = min(max_w, max(44, br.width() + 20))
            bh = min(self.BUBBLE_H - 12, br.height() + 12)
            cx = self.width() // 2
            bx = int(min(max(cx - bw / 2, lo), hi - bw))     # centred on the pet, pushed back on screen
            px = min(max(cx, bx + 12), bx + bw - 12)         # the little pointer stays over the pet
            path = QPainterPath()
            if self.top_layout:           # bubble under the pet, pointer up
                r = QRect(bx, self.pet_size + 10, bw, bh)
                path.addRoundedRect(r, 9, 9)
                path.moveTo(px - 7, r.top())
                path.lineTo(px, r.top() - 8)
                path.lineTo(px + 7, r.top())
            else:
                r = QRect(bx, self.BUBBLE_H - 10 - bh, bw, bh)
                path.addRoundedRect(r, 9, 9)
                path.moveTo(px - 7, r.bottom())
                path.lineTo(px, r.bottom() + 8)
                path.lineTo(px + 7, r.bottom())
            p.setPen(QPen(self.bubble_border, 1.6))
            bg = QColor(self.bubble_bg)
            bg.setAlpha(215 if small else 250)
            p.setBrush(bg)
            p.drawPath(path.simplified())
            p.setPen(self.bubble_fg)
            p.drawText(r.adjusted(8, 3, -8, -3), flags, text)
        if self._pix:
            s, sw = self.pet_size, self.sprite_w
            x = (self.width() - sw) // 2
            y = 0 if self.top_layout else self.BUBBLE_H - self._hop
            if self._spin:
                p.save()
                p.translate(x + sw / 2, y + s / 2)
                p.rotate(self._spin)
                p.drawPixmap(QRect(-sw // 2, -s // 2, sw, s), self._pix)
                p.restore()
            else:
                p.drawPixmap(QRect(x, y, sw, s), self._pix)

    # ---- mouse: click = say hi, drag = move, double-click = panel ----- #
    def _hit(self, pos: QPoint) -> bool:
        """True on the sprite or a visible speech bubble; the rest of the window is empty space."""
        s, sw, m = self.pet_size, self.sprite_w, 8
        x = (self.width() - sw) // 2
        y = 0 if self.top_layout else self.BUBBLE_H
        if QRect(x - m, y - m, sw + 2 * m, s + 2 * m).contains(pos):
            return True
        if self._bubble:
            by = self.pet_size if self.top_layout else 0
            return QRect(0, by, self.width(), self.BUBBLE_H).contains(pos)
        return False

    def wheelEvent(self, e):
        self.wheeled.emit()
        e.ignore()

    def mousePressEvent(self, e):
        if not self._hit(e.position().toPoint()):
            self._press = None
            self.missed.emit()
            return
        if e.button() == Qt.LeftButton:
            self._down = e.globalPosition().toPoint()
            self._press = self._down - self.frameGeometry().topLeft()
            self._dragging = False
        elif e.button() == Qt.RightButton:
            self.context_menu.emit(e.globalPosition().toPoint())

    def mouseMoveEvent(self, e):
        if self._press is None or not (e.buttons() & Qt.LeftButton):
            return
        pos = e.globalPosition().toPoint()
        if not self._dragging and (pos - self._down).manhattanLength() > 4:
            self._dragging = True
            self.grabbed.emit()
            handle = self.windowHandle()
            # native Wayland can't move windows itself; ask the compositor
            if handle and self.app_is_wayland() and handle.startSystemMove():
                self._press = None
                return
        if self._dragging:
            self.move(pos - self._press)

    def mouseReleaseEvent(self, e):
        if e.button() == Qt.LeftButton and self._press is not None and not self._dragging:
            self.clicked.emit()
        self._press = None
        self._dragging = False
        self.released.emit()

    @staticmethod
    def app_is_wayland() -> bool:
        from PySide6.QtGui import QGuiApplication
        return QGuiApplication.platformName().startswith("wayland")

    def mouseDoubleClickEvent(self, e):
        if e.button() == Qt.LeftButton:
            self.open_panel.emit()

    def moveEvent(self, e):
        super().moveEvent(e)
        self._save_timer.start()


class RopeWindow(QWidget):
    """Thin click-through strip down a screen edge: the rope the pet climbs."""
    WIDTH = 30
    FLAGS = ("#F0527A", "#FFD54A", "#29A3DA", "#58B368", "#FF8A00")

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_MacAlwaysShowToolWindow)   # macOS hides tool windows when another app is in front
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowTitle("CapyRunner")
        self.active = False
        self.color = QColor("#C79A5B")
        self.style_ = "rope"              # rope | vine | bunting | none (see themes.py)
        self.resize(self.WIDTH, 100)

    def set_style(self, style: str) -> None:
        if style != self.style_:
            self.style_ = style
            self.update()

    def set_color(self, color: str) -> None:
        c = QColor(color)
        if c.isValid() and c != self.color:
            self.color = c
            self.update()

    def set_active(self, on: bool) -> None:
        if on != self.active:
            self.active = on
            self.update()

    def paintEvent(self, _):
        p = QPainter(self)
        p.setCompositionMode(QPainter.CompositionMode_Source)
        p.fillRect(self.rect(), Qt.transparent)
        p.setCompositionMode(QPainter.CompositionMode_SourceOver)
        if not self.active or self.style_ == "none":
            return
        p.setRenderHint(QPainter.Antialiasing)
        cx, h = self.width() / 2, self.height()
        if self.style_ in ("vine", "bunting"):
            self._paint_fancy(p, cx, h)
            return
        pen = p.pen()
        pen.setCapStyle(Qt.RoundCap)
        dark = self.color.darker(190)
        pen.setColor(dark); pen.setWidthF(5.0); p.setPen(pen)
        p.drawLine(int(cx), 0, int(cx), h)
        pen.setColor(self.color); pen.setWidthF(3.0); p.setPen(pen)
        p.drawLine(int(cx), 0, int(cx), h)
        pen.setColor(dark); pen.setWidthF(1.2); p.setPen(pen)
        for y in range(2, h, 7):          # twist marks
            p.drawLine(int(cx - 2), y + 3, int(cx + 2), y)

    def _paint_fancy(self, p: QPainter, cx: float, h: int):
        """A jungle vine with leaves, or a string of fiesta flags."""
        vine = self.style_ == "vine"
        dark = self.color.darker(190)
        pen = QPen(dark, 5.0 if vine else 2.6, Qt.SolidLine, Qt.RoundCap)
        p.setPen(pen)
        p.drawLine(QPointF(cx, 0), QPointF(cx, h))
        pen.setColor(self.color)
        pen.setWidthF(3.0 if vine else 1.4)
        p.setPen(pen)
        p.drawLine(QPointF(cx, 0), QPointF(cx, h))
        step = 38 if vine else 30
        for i, y in enumerate(range(12, h - 14, step)):
            side = 1 if i % 2 else -1
            shape = QPainterPath(QPointF(cx, y))
            if vine:
                shape.quadTo(cx + side * 11, y - 9, cx + side * 13, y + 3)
                shape.quadTo(cx + side * 6, y + 8, cx, y)
                p.setPen(QPen(dark, 1.4))
                p.setBrush(self.color.lighter(125))
            else:
                shape.lineTo(cx + side * 12, y + 7)
                shape.lineTo(cx, y + 14)
                shape.closeSubpath()
                p.setPen(QPen(QColor("#3A2414"), 1.2))
                p.setBrush(QColor(self.FLAGS[i % len(self.FLAGS)]))
            p.drawPath(shape)
