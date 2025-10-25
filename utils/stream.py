import sys
from PySide6.QtCore import QObject, Signal

class Stream(QObject):
    textWritten = Signal(str)

    def write(self, text):
        self.textWritten.emit(str(text))

    def flush(self):
        pass