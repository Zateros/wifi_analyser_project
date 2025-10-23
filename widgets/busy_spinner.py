from PySide6.QtCore import QTimer, Qt
from PySide6.QtGui import QPainter, QColor
from PySide6.QtWidgets import QWidget


class BusySpinner(QWidget):
    def __init__(self, parent=None, color=QColor("dodgerblue")):
        super().__init__(parent)
        self._angle = 0
        self._color = color
        self._timer = QTimer(self)
        self._timer.timeout.connect(self.rotate)
        self._timer.setInterval(50)
        self._running = False
        self.hide()

    def rotate(self):
        self._angle = (self._angle + 30) % 360
        self.update()

    def paintEvent(self, event):
        p = QPainter(self)
        p.setRenderHint(QPainter.Antialiasing)
        p.translate(self.width() / 2, self.height() / 2)
        p.rotate(self._angle)
        r = min(self.width(), self.height()) / 4
        for i in range(12):
            alpha = int(255 * (1 - i / 12))
            c = QColor(self._color)
            c.setAlpha(alpha)
            p.setBrush(c)
            p.setPen(Qt.NoPen)
            p.drawEllipse(r, -3, 6, 6)
            p.rotate(30)

    def start(self):
        if not self._running:
            self._running = True
            self.show()
            self._timer.start()

    def stop(self):
        if self._running:
            self._running = False
            self._timer.stop()
            self.hide()

    def isRunning(self):
        return self._running

    def setColor(self, color):
        self._color = QColor(color)
        self.update()

    def color(self):
        return self._color