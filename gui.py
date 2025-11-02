from PySide6.QtCore import Qt, QThreadPool, Slot, QPoint, QSize
from PySide6.QtGui import QPixmap, QIcon
from PySide6.QtWidgets import QApplication, QMainWindow, QPushButton, QStyle
from typing import cast

from ui.ui_main import Ui_MainWindow
from widgets.ap import AP
from utils.workers import Worker
from utils.stream import Stream
from utils.literals import (
    PWD,
    DEFAULT_IPERF_PORT,
    DEFAULT_IPERF_ADDRESS,
    DEFAULT_TARGET
)
from utils.util import (
    makeBackgroundImage,
    makeRepmap,
    rethemePixmap,
    getIsDark,
    getWirelessInterfaces,
    saveAPLocation,
    load,
    getResourcePath,
    getDependencies,
)

import sys, json


class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()

        self.is_running = False

        self.setupUi(self)
        self.setFixedSize(1400, 650)

        self.interface_combo.addItems(getWirelessInterfaces())

        self._floor_layout_pixmap = QPixmap()

        mouse_graphic_pixmap = QPixmap()
        if not mouse_graphic_pixmap.load(
            getResourcePath("media/mouse_right_click.png")
        ):
            self.mouse_click_graphic.setText("Icon not found")
            print("Warning: Could not load mouse graphic.")
        else:
            mouse_graphic_pixmap = rethemePixmap(mouse_graphic_pixmap, getIsDark(app))

            mouse_graphic_size = QSize(20, 36)
            self.mouse_click_graphic.setPixmap(
                mouse_graphic_pixmap.scaled(
                    mouse_graphic_size,
                    mode=Qt.TransformationMode.SmoothTransformation,
                )
            )
            self.mouse_click_graphic.setFixedSize(mouse_graphic_size)

        self.floor_layout.right_clicked.connect(self.placeNewAP)

        self.last_clicked_button: QPushButton

        self.repmap = {}

        self.building_value = "A"
        self.floor_value = "1"

        self.ping_target.setText(DEFAULT_TARGET)
        self.iperf_addr.setText(DEFAULT_IPERF_ADDRESS)
        self.iperf_port.setText(DEFAULT_IPERF_PORT)

        self.building_combo.setCurrentText(self.building_value)
        self.floor_combo.setCurrentText(self.floor_value)

        self.building_combo.currentTextChanged.connect(self.floorOrBuildingChanged)
        self.floor_combo.currentTextChanged.connect(self.floorOrBuildingChanged)

        self.generateBackground()

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
            button.clicked.connect(self.roomPartitionClicked)
            button.setStyleSheet(self.default_button_style)

        self.found_text = "{0} is available!"
        self.not_found_text = "{0} is not available!"
        self.not_found_optional_text = "{0} is not available, but is optional!"

        icon_size = QSize(25, 25)
        self.iperf_icon.setFixedSize(icon_size)
        self.timedatectl_icon.setFixedSize(icon_size)
        self.ping_icon.setFixedSize(icon_size)
        self.nmcli_icon.setFixedSize(icon_size)
        self.arp_icon.setFixedSize(icon_size)

        self.available_icon = (
            self.style()
            .standardIcon(QStyle.StandardPixmap.SP_DialogApplyButton)
            .pixmap(icon_size)
        )
        self.not_available_icon = (
            self.style()
            .standardIcon(QStyle.StandardPixmap.SP_DialogCancelButton)
            .pixmap(icon_size)
        )
        self.optional_icon = (
            self.style()
            .standardIcon(QStyle.StandardPixmap.SP_MessageBoxWarning)
            .pixmap(icon_size)
        )

        self.refreshDependencies()
        self.refresh_deps_button.setIcon(QIcon.fromTheme("view-refresh"))
        self.refresh_deps_button.clicked.connect(self.refreshDependencies)

        self.aps: list[AP] = []

        self.stream = Stream()

        self.stream.textWritten.connect(self.updateStatus)

        sys.stdout = self.stream

        self.populateFromFile()

        self.worker = Worker()

        self.worker.signals.connected.connect(self.updateWorkerArgs)

        self.iperf_addr.textChanged.connect(self.updateWorkerArgs)
        self.iperf_port.textChanged.connect(self.updateWorkerArgs)
        self.ping_target.textChanged.connect(self.updateWorkerArgs)
        self.interface_combo.currentTextChanged.connect(self.updateWorkerArgs)

        self.worker.signals.finished.connect(self.onMeasurementFinish)
        self.worker.signals.command_error.connect(self.onError)

        print("Ready")

    def updateStatus(self, text):
        stripped = text.strip()
        if stripped and not stripped == "\n":
            self.statusBar.showMessage(f"Status: {stripped}")  # type: ignore

    def closeEvent(self, event):
        self.worker.stop()

        self.onStop()

        sys.stdout = sys.__stdout__

        event.accept()

    def updateWorkerArgs(self):
        options = {
            "iperf_addr": self.iperf_addr.text(),
            "iperf_port": self.iperf_port.text(),
            "iface": self.interface_combo.currentText(),
            "target": self.ping_target.text(),
            "out": f"{self.building_value.lower()}{self.floor_value}_measure.csv",
            "pwd": PWD,
        }

        self.worker.send_command(f"CHANGE {json.dumps(options)}")

    def refreshDependencies(self):
        deps = getDependencies()

        self.iperf_found.setText(
            (self.found_text if deps["iperf3"] else self.not_found_text).format(
                "iperf3"
            )
        )
        self.iperf_icon.setPixmap(
            self.available_icon if deps["iperf3"] else self.not_available_icon
        )

        self.timedatectl_found.setText(
            (
                self.found_text if deps["timedatectl"] else self.not_found_optional_text
            ).format("timedatectl")
        )
        self.timedatectl_icon.setPixmap(
            self.available_icon if deps["timedatectl"] else self.optional_icon
        )

        self.ping_found.setText(
            (self.found_text if deps["ping"] else self.not_found_text).format("ping")
        )
        self.ping_icon.setPixmap(
            self.available_icon if deps["ping"] else self.not_available_icon
        )

        self.nmcli_found.setText(
            (self.found_text if deps["nmcli"] else self.not_found_text).format("nmcli")
        )
        self.nmcli_icon.setPixmap(
            self.available_icon if deps["nmcli"] else self.not_available_icon
        )

        self.arp_found.setText(
            (self.found_text if deps["arp-scan"] else self.not_found_text).format("arp-scan")
        )
        self.arp_icon.setPixmap(
            self.available_icon if deps["arp-scan"] else self.not_available_icon
        )

    @Slot()
    def onMeasurementFinish(self):
        self.last_clicked_button.setStyleSheet(self.completed_button_style)
        self.buttons[self.last_clicked_button] = True
        self.onStop()

        print("Measurement finished succesfully!")

    @Slot()
    def onError(self, error):
        if error["command"] == "START_MEASUREMENT":
            self.onMeasurementError()
        self.onStop()

        print(f"Error running command {error["command"]}: {error["error"]}")

    def onMeasurementError(self):
        self.last_clicked_button.setStyleSheet(self.errored_button_style)
        self.buttons[self.last_clicked_button] = False

    def onStop(self):
        self.busy_spinner.stop()
        self.is_running = False

    def generateBackground(self):
        self.repmap = makeRepmap(
            building=self.building_value, floor=int(self.floor_value)
        )
        self.floor_image = makeBackgroundImage(replace_map=self.repmap)
        self._floor_layout_pixmap.loadFromData(self.floor_image.getvalue())

        self.floor_layout.setPixmap(self._floor_layout_pixmap)

    def setButtonsStyle(self, stylesheet):
        for button in self.buttons.keys():
            button.setStyleSheet(stylesheet)

    def resetParitionState(self):
        for button in self.buttons.keys():
            self.buttons[button] = False

    def populateFromFile(self):
        (done, self.aps) = load(self, self.building_value + self.floor_value)

        for button in self.buttons.keys():
            if button.objectName() in done:
                button.setStyleSheet(self.completed_button_style)
                self.buttons[button] = True

    def floorOrBuildingChanged(self, text):
        self.building_value = self.building_combo.currentText()
        self.floor_value = self.floor_combo.currentText()

        self.generateBackground()
        self.setButtonsStyle(self.default_button_style)

        for ap in self.aps:
            ap.deleteLater()

        self.populateFromFile()
        self.updateWorkerArgs()

    def roomPartitionClicked(self):
        if self.is_running:
            return

        deps = getDependencies()
        if not deps["iperf3"] or not deps["ping"] or not deps["nmcli"]:
            not_available = list(
                filter(
                    lambda x: not (x == "" or x == "timedatectl"),
                    [key if not value else "" for key, value in deps.items()],
                )
            )
            print(
                f"Required {"dependency" if len(not_available) == 1 else "dependencies"} not met: {', '.join(not_available)}"
            )
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

            self.worker.send_command(f"START_MEASUREMENT {x},{y},{pir}")
            self.is_running = True
            print(f"Started measurements for {self.repmap[name[0:-1]]} ({pir})")

    def placeNewAP(self, x, y):
        point = self.floor_layout.mapToGlobal(QPoint(x, y))
        ap = AP(self, point)

        self.aps.append(ap)

        saveAPLocation(f"{self.building_value}{self.floor_value}", point.x(), point.y())


if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    app.exec()
