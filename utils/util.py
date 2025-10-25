from pathlib import Path
from cairosvg import svg2png
from PySide6.QtWidgets import QMainWindow
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QPainter, QPixmap, QColor, QPalette
from shutil import which

from widgets.ap import AP

import io, sys, os, csv, re, subprocess

aps_file: str = "ap_locations.csv"
aps_headers = ["floor", "x", "y"]
measure_headers = [
    "timestamp",
    "iface",
    "ssid",
    "bssid",
    "freq_mhz",
    "channel",
    "signal_dbm",
    "tx_bitrate_mbps",
    "ping_target",
    "ping_avg_ms",
    "ping_min_ms",
    "ping_max_ms",
    "ping_jitter_ms",
    "ping_loss_pct",
    "ping_success",
    "download",
    "upload",
    "position_x",
    "position_y",
    "position_in_room",
    "pcap_file",
    "ntp_synced",
]


def get_dependencies():
    return {
        "iperf3": which("iperf3") is not None,
        "timedatectl": which("timedatectl") is not None,
        "ping": which("ping") is not None,
        "nmcli": which("nmcli") is not None,
        "tcpdump": which("tcpdump") is not None,
    }


def make_image(
    replace_map: dict[str, str] = {},
    template_path: str = "media/floor_template.svg",
):
    template = Path(resource_path(template_path)).read_text()

    for key, value in replace_map.items():
        template = template.replace(f"{{{key}}}", value)

    template = template.replace("Erdős Pál Kollégium", "")
    template = template.replace("{floor}", "")

    image = io.BytesIO()
    svg2png(bytestring=template.encode("utf-8"), write_to=image)
    image.seek(0)

    return image


def make_repmap(building: str = "A", floor: int = 1):
    replace_map = {}

    building = f"{building}{str(floor)}".upper()

    has_shared_br = floor in (3, 7)

    replace_map = {
        "fl1": f"{building}36",
        "fl2": f"{building}34",
        "fl3": f"{building}32",
        "fl4": f"{building}30",
        "fr1": f"{building}04",
        "fr2": f"{building}06",
        "fr3": f"{building}08",
        "fr4": f"{building}10",
        "sl1": f"{building}28",
        "sl2": f"{building}26",
        "sl3": f"{building}24",
        "sr1": f"{building}12",
        "sr2": f"{building}14",
        "sr3": f"{building}16",
        "sr4": f"{building}18" if not has_shared_br else "Fürdő",
    }

    return replace_map


def get_wireless_interfaces():
    sys_interfaces = []
    try:
        out = subprocess.check_output(["ip", "-o", "addr", "show"]).decode()
        for m in re.finditer(r"^\d+:\s+(\S+).+inet\s+([0-9.]+)", out, re.M):
            iface, _ = m.groups()
            sys_interfaces.append(iface)
    except FileNotFoundError:
        print("Command ip not found, cannot get wireless interfaces.")
    finally:
        return sys_interfaces


def save_ap_location(location: str = "A1", x: int = 0, y: int = 0):
    already_exists: bool = os.path.exists(aps_file)

    file = open(aps_file, "a", encoding="utf-8")
    writer = csv.DictWriter(file, fieldnames=aps_headers)
    if not already_exists:
        writer.writeheader()
        file.flush()

    writer.writerow({"floor": location, "x": x, "y": y})

    file.flush()

    file.close()


def load(window: QMainWindow, location: str = "A1") -> tuple[list[str], list[AP]]:
    done_zones: list[str] = []
    aps: list[AP] = []

    floor_measure = f"{location.lower()}_measure.csv"

    if os.path.exists(aps_file):
        file = open(aps_file, "r")
        reader = csv.DictReader(file, fieldnames=aps_headers)
        for row in reader:
            if row["floor"] == location:
                aps.append(
                    AP(
                        window,
                        QPoint(int(row["x"]), int(row["y"])),
                    )
                )
        file.close()

    if os.path.exists(floor_measure):
        file = open(floor_measure, "r")
        reader = csv.DictReader(file)
        for row in reader:
            x: int = int(row["position_x"])
            y: int = int(row["position_y"])
            pir: int = int(row["position_in_room"])

            f_or_s = "f" if x <= 4 else "s"
            l_or_r = "l" if y == 0 else "r"

            name: str = f"{f_or_s}{l_or_r}{x - 0 if f_or_s == "f" else 4}{pir}"

            if name not in done_zones:
                done_zones.append(name)

        file.close()

    return (done_zones, aps)


def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS  # type: ignore
    except Exception:
        base_path = os.path.abspath(".")

    return os.path.join(base_path, relative_path)


def get_is_dark(app):
    palette = app.palette()
    window_color = palette.color(QPalette.ColorRole.Window)
    dark_theme_enabled = window_color.lightness() < 128

    return dark_theme_enabled


def recolor_pixmap(pixmap: QPixmap, is_dark: bool):
    if is_dark:
        tint_color = QColor("white")
    else:
        tint_color = QColor("black")

    recolored_pixmap = QPixmap(pixmap.size())
    recolored_pixmap.fill(Qt.GlobalColor.transparent)

    painter = QPainter(recolored_pixmap)
    painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Source)
    painter.drawPixmap(0, 0, pixmap)

    painter.setCompositionMode(
        QPainter.CompositionMode.CompositionMode_SourceIn
    )
    painter.fillRect(recolored_pixmap.rect(), tint_color)
    painter.end()

    return recolored_pixmap