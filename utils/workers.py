from PySide6.QtCore import QRunnable, QObject, Signal

import time

class Worker(QRunnable):
    def __init__(self, func, args):
        super().__init__()
        self.signals = WorkerSignals()
        self.func = func
        self.args = args

    def run(self):
        try:
            self.func(self.args)
            self.signals.finished.emit("done")
        except Exception as e:
            print(f"Error happened running {self.func}: {e}")
            self.signals.finished.emit("error")


class WorkerSignals(QObject):
    finished = Signal(str)


class DelayWorker(QRunnable):
    def __init__(self, delay_seconds: float = 3.0):
        super().__init__()
        self.delay = delay_seconds
        self.signals = WorkerSignals()

    def run(self):
        time.sleep(self.delay)
        self.signals.finished.emit()