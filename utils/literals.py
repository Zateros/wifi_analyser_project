import os

SOCKET_PATH = "/tmp/wifi_analyser.sock"
PWD = os.getcwd()

MEASURE_HEADERS = [
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
    "ntp_synced",
    "num_of_connected_devices"
]

APS_FILE: str = os.path.join(PWD, "ap_locations.csv")
APS_HEADERS = ["floor", "x", "y"]

DEFAULT_IPERF_ADDRESS = "a205.speedtest.wobcom.de"
DEFAULT_IPERF_PORT = ""
DEFAULT_TARGET = "1.1.1.1"