from PySide6.QtGui import QPaintEvent, QPainter, QColor, QBrush, QPen
from PySide6.QtWidgets import QWidget
from PySide6.QtCore import Qt, QPoint


class AP(QWidget):
    def __init__(
        self,
        parent: QWidget,
        pos: QPoint,
        radius: int = 6,
        fill_color: str = "green",
        outline_color: str = "black",
        outline_width: int = 2
    ):
        super().__init__(parent)
        self.radius = radius
        self.fill_color = QColor(fill_color)
        self.outline_color = QColor(outline_color)
        self.outline_width = outline_width

        size = (radius * 2) + (outline_width * 2)
        self.resize(size, size)

        self.move(pos.x() - size // 2, pos.y() - size // 2)
        
        self.show()

    def paintEvent(self, event: QPaintEvent) -> None:
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)

        pen = QPen(self.outline_color)
        pen.setWidth(self.outline_width)
        painter.setPen(pen)

        painter.setBrush(QBrush(self.fill_color))

        offset = int(self.outline_width / 2)
        diameter = (self.radius * 2)
        painter.drawEllipse(offset, offset, diameter, diameter)
