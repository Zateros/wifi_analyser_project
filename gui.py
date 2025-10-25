from PySide6.QtCore import Qt, QThreadPool, Slot, QPoint, QSize
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton
from typing import cast

from ui.ui_main import Ui_MainWindow
from widgets.ap import AP
from wifi_analyser import entry
from utils.workers import Worker
from utils.stream import Stream
from utils.util import (
    make_image,
    make_repmap,
    recolor_pixmap,
    get_is_dark,
    get_wireless_interfaces,
    save_ap_location,
    load,
    resource_path,
)

import sys


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.pool = QThreadPool.globalInstance()

        self.is_running = False

        self.setupUi(self)
        self.setFixedSize(1400, 650)

        self.interface_combo.addItems(get_wireless_interfaces())

        self._floor_layout_pixmap = QPixmap()

        mouse_graphic_pixmap = QPixmap()
        if not mouse_graphic_pixmap.load(resource_path("media/mouse_right_click.png")):
            self.mouse_click_graphic.setText("Icon not found")
            print("Warning: Could not load mouse graphic.")
        else:
            mouse_graphic_pixmap = recolor_pixmap(
                mouse_graphic_pixmap, get_is_dark(app)
            )

            mouse_graphic_size = QSize(20, 36)
            self.mouse_click_graphic.setPixmap(
                mouse_graphic_pixmap.scaled(
                    mouse_graphic_size,
                    mode=Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.mouse_click_graphic.setFixedSize(mouse_graphic_size)

        self.floor_layout.right_clicked.connect(self.place_new_ap)

        self.last_clicked_button: QPushButton

        self.building_value = "A"
        self.floor_value = "1"

        self.building_combo.setCurrentText(self.building_value)
        self.floor_combo.setCurrentText(self.floor_value)

        self.building_combo.currentTextChanged.connect(self.floor_or_building_changed)
        self.floor_combo.currentTextChanged.connect(self.floor_or_building_changed)

        self.set_background_values()

        self.ping_target.setText("1.1.1.1")
        self.iperf_addr.setText("speedtest.fra1.de.leaseweb.net")
        self.iperf_port.setText("5201-5210")

        self.buttons = {
            self.fl11: False,
            self.fl12: False,
            self.fl13: False,
            self.fl21: False,
            self.fl22: False,
            self.fl23: False,
            self.fl31: False,
            self.fl32: False,
            self.fl33: False,
            self.fl41: False,
            self.fl42: False,
            self.fl43: False,
            self.fr11: False,
            self.fr12: False,
            self.fr13: False,
            self.fr21: False,
            self.fr22: False,
            self.fr23: False,
            self.fr31: False,
            self.fr32: False,
            self.fr33: False,
            self.fr41: False,
            self.fr42: False,
            self.fr43: False,
            self.sl11: False,
            self.sl12: False,
            self.sl13: False,
            self.sl21: False,
            self.sl22: False,
            self.sl23: False,
            self.sl31: False,
            self.sl32: False,
            self.sl33: False,
            self.sl41: False,
            self.sl42: False,
            self.sl43: False,
            self.sr11: False,
            self.sr12: False,
            self.sr13: False,
            self.sr21: False,
            self.sr22: False,
            self.sr23: False,
            self.sr31: False,
            self.sr32: False,
            self.sr33: False,
            self.sr41: False,
            self.sr42: False,
            self.sr43: False,
        }

        self.default_button_style = """
                    QPushButton          { border: 0; background: rgba(41,128,185,55); }
                    QPushButton:hover    { background-color: rgba(41,128,185,135); }
                    QPushButton:pressed  { background-color: #21618c; }
                """

        self.errored_button_style = """
                    QPushButton          { border: 0; background: rgba(255, 0, 0, 100); }
                    QPushButton:hover    { background-color: rgba(255, 0, 0, 100); }
                    QPushButton:pressed  { background-color: rgba(255, 0, 0, 100); }
                """

        self.inprogress_button_style = """
                    QPushButton          { border: 0; background: rgba(255, 255, 0, 100); }
                    QPushButton:hover    { background-color: rgba(255, 255, 0, 100); }
                    QPushButton:pressed  { background-color: rgba(255, 255, 0, 100); }
                """

        self.completed_button_style = """
                    QPushButton          { border: 0; background: rgba(0, 255, 0, 100); }
                    QPushButton:hover    { background-color: rgba(0, 255, 0, 100); }
                    QPushButton:pressed  { background-color: rgba(0, 255, 0, 100);; }
                """

        for button in self.buttons:
            button.clicked.connect(self.room_button_clicked)
            button.setStyleSheet(self.default_button_style)

        self.aps: list[AP] = []

        self.stream = Stream()

        self.stream.textWritten.connect(self.updateStatus)

        sys.stdout = self.stream

        self.populate_from_file()

        print("Ready")

    def updateStatus(self, text):
        stripped = text.strip()
        if stripped and not stripped == "\n":
            self.statusBar.showMessage(f"Status: {stripped}")  # type: ignore

    def closeEvent(self, event):
        self.pool.clear()

        sys.stdout = sys.__stdout__

        event.accept()

    @Slot(str)
    def on_done(self, msg):
        if msg == "done":
            self.last_clicked_button.setStyleSheet(self.completed_button_style)
            self.buttons[self.last_clicked_button] = True
        else:
            self.last_clicked_button.setStyleSheet(self.errored_button_style)
            self.buttons[self.last_clicked_button] = False
        self.busy_spinner.stop()
        self.is_running = False

    def set_background_values(self):
        self.floor_image = make_image(
            replace_map=make_repmap(
                building=self.building_value, floor=int(self.floor_value)
            )
        )
        self._floor_layout_pixmap.loadFromData(self.floor_image.getvalue())

        self.floor_layout.setPixmap(self._floor_layout_pixmap)

    def set_buttons_style(self, stylesheet):
        for button in self.buttons.keys():
            button.setStyleSheet(stylesheet)

    def reset_buttons(self):
        for button in self.buttons.keys():
            self.buttons[button] = False

    def populate_from_file(self):
        (done, self.aps) = load(self, self.building_value + self.floor_value)

        for button in self.buttons.keys():
            if button.objectName() in done:
                button.setStyleSheet(self.completed_button_style)
                self.buttons[button] = True

    def floor_or_building_changed(self, text):
        self.building_value = self.building_combo.currentText()
        self.floor_value = self.floor_combo.currentText()

        self.set_background_values()
        self.set_buttons_style(self.default_button_style)

        for ap in self.aps:
            ap.deleteLater()

        self.populate_from_file()

    def room_button_clicked(self):
        if self.is_running:
            return

        sender_button = cast(QPushButton, self.sender())

        if sender_button:
            if self.buttons[sender_button]:
                return

            self.last_clicked_button = sender_button
            sender_button.setStyleSheet(self.inprogress_button_style)

            self.busy_spinner.start()

            name = sender_button.objectName()
            x = int(name[2]) + (0 if name[0] == "f" else 4)
            y = 0 if name[1] == "l" else 1
            pir = int(name[3])
            args = [
                "--iface",
                self.interface_combo.currentText(),
                "--target",
                self.ping_target.text(),
                "--iperf_addr",
                self.iperf_addr.text(),
                "--iperf_port",
                self.iperf_port.text(),
                "--out",
                f"{self.building_value.lower()}{self.floor_value}_measure.csv",
                "--x",
                f"{x}",
                "--y",
                f"{y}",
                "--pir",
                f"{pir}",
            ]

            worker = Worker(func=entry, args=args)
            worker.signals.finished.connect(self.on_done)
            self.pool.start(worker)
            self.is_running = True

    def place_new_ap(self, x, y):
        point = self.floor_layout.mapToGlobal(QPoint(x, y))
        ap = AP(self, point)

        self.aps.append(ap)

        save_ap_location(
            f"{self.building_value}{self.floor_value}", point.x(), point.y()
        )


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
