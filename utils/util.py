from pathlib import Path
import re
from cairosvg import svg2png

import subprocess
import io


def make_image(
    replace_map: dict[str, str] = {},
    template_path: str = "floor_template.svg",
):
    template = Path(template_path).read_text()

    for key, value in replace_map.items():
        template = template.replace(f"{{{key}}}", value)

    template = template.replace("{floor}", "")

    image = io.BytesIO()
    svg2png(bytestring=template.encode("utf-8"), write_to=image)
    image.seek(0)

    return image


def make_repmap(building: str = "A", floor: int = 1, has_shared_br: bool = False):
    replace_map = {}

    building = f"{building}{str(floor)}".upper()

    if not has_shared_br:
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
            "sr4": f"{building}18",
        }
    else:
        replace_map = {
            "fl1": f"{building}34",
            "fl2": f"{building}32",
            "fl3": f"{building}30",
            "fl4": f"{building}28",
            "fr1": f"{building}04",
            "fr2": f"{building}06",
            "fr3": f"{building}08",
            "fr4": f"{building}10",
            "sl1": f"{building}24",
            "sl2": f"{building}22",
            "sl3": f"{building}20",
            "sr1": f"{building}12",
            "sr2": f"{building}14",
            "sr3": f"{building}16",
            "sr4": "Fürdő",
        }

    return replace_map

def get_wireless_interfaces():
    sys_interfaces = []
    out = subprocess.check_output(["ip", "-o", "addr", "show"]).decode()
    for m in re.finditer(r"^\d+:\s+(\S+).+inet\s+([0-9.]+)", out, re.M):
        iface, _ = m.groups()
        sys_interfaces.append(iface)
    
    return sys_interfaces