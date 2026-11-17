"""Floating desktop pet: a small always-on-top window you can drag anywhere."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QRect, Qt, QTimer, Signal
from PySide6.QtGui import QColor, QFont, QFontMetrics, QPainter, QPainterPath, QPixmap
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
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setWindowTitle("CapyRunner")
        self._pix: QPixmap | None = None
        self._bubble = ""
        self._hop = 0
        self._spin = 0.0
        self.top_layout = False       # True while running along the top edge: pet on top, bubble below
        self._bubble_timer = QTimer(self, singleShot=True, timeout=self._clear_bubble)
        self._save_timer = QTimer(self, singleShot=True, interval=600)
        self._save_timer.timeout.connect(lambda: self.moved.emit(self.x(), self.y()))
        self._press: QPoint | None = None
        self._down = QPoint()
        self._dragging = False
        self.set_pet_size(size)

    def set_passthrough(self, on: bool) -> None:
        """Click-through: the pet never takes focus, clicks or scroll, so whatever is under it keeps working.
        Changing window flags hides the window; the caller shows it again."""
        if on == bool(self.windowFlags() & Qt.WindowTransparentForInput):
            return
        self.setWindowFlag(Qt.WindowTransparentForInput, on)
        self.setAttribute(Qt.WA_TransparentForMouseEvents, on)
        self._press = None
        self._dragging = False

    def set_pet_size(self, size: int) -> None:
        self.pet_size = max(32, min(320, size))
        w = max(self.pet_size + 40, 240)
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
        if self._bubble:
            f = QFont()
            f.setPixelSize(13)
            p.setFont(f)
            fm = QFontMetrics(f)
            text = fm.elidedText(self._bubble, Qt.ElideRight, (self.width() - 24) * 2)
            path = QPainterPath()
            cx = (self.width()) // 2
            if self.top_layout:           # bubble under the pet, pointer up
                r = QRect(4, self.pet_size + 10, self.width() - 8, self.BUBBLE_H - 12)
                path.addRoundedRect(r, 10, 10)
                path.moveTo(cx - 8, r.top())
                path.lineTo(cx, r.top() - 9)
                path.lineTo(cx + 8, r.top())
            else:
                r = QRect(4, 2, self.width() - 8, self.BUBBLE_H - 12)
                path.addRoundedRect(r, 10, 10)
                path.moveTo(cx - 8, r.bottom())
                path.lineTo(cx, r.bottom() + 9)
                path.lineTo(cx + 8, r.bottom())
            p.setPen(QColor("#555"))
            p.setBrush(QColor(255, 255, 255, 240))
            p.drawPath(path.simplified())
            p.setPen(QColor("#222"))
            p.drawText(r.adjusted(8, 4, -8, -4), Qt.AlignCenter | Qt.TextWordWrap, text)
        if self._pix:
            s = self.pet_size
            x = (self.width() - s) // 2
            y = 0 if self.top_layout else self.BUBBLE_H - self._hop
            if self._spin:
                p.save()
                p.translate(x + s / 2, y + s / 2)
                p.rotate(self._spin)
                p.drawPixmap(QRect(-s // 2, -s // 2, s, s), self._pix)
                p.restore()
            else:
                p.drawPixmap(QRect(x, y, s, s), self._pix)

    # ---- mouse: click = say hi, drag = move, double-click = panel ----- #
    def _hit(self, pos: QPoint) -> bool:
        """True on the sprite or a visible speech bubble; the rest of the window is empty space."""
        s, m = self.pet_size, 8
        x = (self.width() - s) // 2
        y = 0 if self.top_layout else self.BUBBLE_H
        if QRect(x - m, y - m, s + 2 * m, s + 2 * m).contains(pos):
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
    WIDTH = 12

    def __init__(self):
        super().__init__(None, Qt.Tool | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint
                         | Qt.WindowTransparentForInput | Qt.WindowDoesNotAcceptFocus)
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setAttribute(Qt.WA_TransparentForMouseEvents)
        self.setWindowTitle("CapyRunner")
        self.active = False
        self.color = QColor("#C79A5B")
        self.resize(self.WIDTH, 100)

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
        if not self.active:
            return
        p.setRenderHint(QPainter.Antialiasing)
        cx, h = self.width() / 2, self.height()
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
