from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QLabel

class ClickableLabel(QLabel):
    right_clicked = Signal(int, int)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.RightButton:
            x = int(event.position().x())
            y = int(event.position().y())
            self.right_clicked.emit(x, y)
            event.accept()
        else:
            super().mousePressEvent(event)