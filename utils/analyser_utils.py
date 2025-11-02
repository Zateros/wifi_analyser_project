import statistics, re, subprocess, datetime, os, json


def currentTime():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")

def runCMD(cmd, timeout: float | None = 3):
    res = subprocess.run(
        cmd,  # type: ignore
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )  # type: ignore
    return (res.stdout.strip(), res.returncode)

def parseNmcli(iface):
    data = {
        "ssid": "",
        "bssid": "",
        "freq_mhz": "",
        "channel": "",
        "txrate": "",
        "signal_dbm": "",
    }

    print("Parsing nmcli...")

    out, rc = runCMD(
        f"nmcli -t -f IN-USE,SSID,BSSID,FREQ,CHAN,RATE,SIGNAL dev wifi list ifname {iface}",
        timeout=None,
    )
    if rc != 0 or not out:
        return data

    split_pattern = re.compile(r"(?<!\\):")

    for line in out.splitlines():
        if not line.strip():
            continue

        parts = [p.replace("\\:", ":") for p in split_pattern.split(line)]
        if len(parts) < 7:
            continue

        in_use, ssid, bssid, freq, chan, rate, signal = parts[:7]
        if in_use.strip() == "*":
            data["ssid"] = ssid.strip()
            data["bssid"] = bssid.strip()
            data["freq_mhz"] = freq.replace(" MHz", "").strip()
            data["channel"] = chan.strip()
            data["txrate"] = rate.replace(" Mbit/s", "").strip()
            data["signal_dbm"] = signal.strip()
            break

    return data

def getInetAndSubnet(iface):
    inet = ""
    subnet = 0
    try:
        out = subprocess.check_output(["ip", "addr", "show", iface]).decode()
        regex = re.compile(r"inet\s+([0-9.]+)\/([0-9]+)", re.M)
        match = regex.match(out)
        if match is not None: (inet, subnet) = match.groups()
    except FileNotFoundError:
        print("Command ip not found, cannot get wireless interfaces.")
    finally:
        return (inet, subnet)

def getArpDevicesCount(iface):
    print("Getting the number of connected devices...")
    (inet, subnet) = getInetAndSubnet(iface)
    inet = re.sub(r'^((?:\d{1,3}\.){3})\d{1,3}$', r'\g<1>0', inet)
    cmd = f"arp-scan -x {inet}/{subnet}"
    out, rc = runCMD(cmd=cmd, timeout=15)
    if rc != 0 or not out:
        print("Failed to get devices via arp-scan!")

        return -1
    count = len(out.split("\n"))
    return count

def measureLatency(target, count=10, timeout=1):
    print("Measuring latency, jitter, packet loss...")
    cmd = f"ping -c {count} -W {timeout} {target}"
    out, rc = runCMD(cmd, timeout=count + 5)
    if rc != 0 or not out:
        print(f"Latency measure failed: out={out}; rc={rc}")

        return {
            "avg_ms": None,
            "min_ms": None,
            "max_ms": None,
            "jitter_ms": None,
            "loss_pct": 100.0,
            "success": False,
        }

    latencies = []
    transmitted = received = 0

    for line in out.splitlines():
        if "time=" in line:
            try:
                lat = float(line.split("time=")[1].split()[0])
                latencies.append(lat)
                received += 1
            except Exception:
                pass
        elif "packets transmitted" in line and "received" in line:
            parts = line.split(",")
            if len(parts) >= 2:
                try:
                    transmitted = int(parts[0].split()[0])
                    received = int(parts[1].split()[0])
                except Exception:
                    pass

    loss_pct = 100.0
    if transmitted > 0:
        loss_pct = 100.0 * (transmitted - received) / transmitted

    if latencies:
        avg_ms = statistics.mean(latencies)
        min_ms = min(latencies)
        max_ms = max(latencies)
        if len(latencies) > 1:
            jitter_ms = statistics.stdev(latencies)
        else:
            jitter_ms = 0.0
        success = True
    else:
        avg_ms = min_ms = max_ms = jitter_ms = None
        success = False

    return {
        "avg_ms": avg_ms,
        "min_ms": min_ms,
        "max_ms": max_ms,
        "jitter_ms": jitter_ms,
        "loss_pct": loss_pct,
        "success": success,
    }

def testSpeed(server="speedtest.fra1.de.leaseweb.net", port="5201-5210", duration=10):

    print(f"Running iperf3 speed test to {server}...")

    def run_iperf3(reverse=False):
        cmd = [
            "iperf3",
            "-c",
            server,
            "-J",
            "-t",
            str(duration),
            "--connect-timeout",
            "3000",
        ]

        if not port == "":
            cmd += [
                "-p",
                port,
            ]

        if reverse:
            cmd.append("-R")

        res = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 5)
        if res.returncode != 0:
            raise RuntimeError(res.stderr.strip())
        data = json.loads(res.stdout)
        bps_field = "sum_received" if reverse else "sum_sent"
        bps = data["end"][bps_field]["bits_per_second"]
        return round(bps / 1_000_000, 2)

    download = run_iperf3(reverse=True)
    upload = run_iperf3(reverse=False)

    return (download, upload)

def checkNTPSync() -> bool:
    print("Is ntp synced?")

    out, _ = runCMD("timedatectl show -p NTPSynchronized --value 2>/dev/null")
    if out.strip().lower() == "yes":
        return True

    out, _ = runCMD("chronyc tracking | grep 'Leap status' || true")
    if "normal" in out.lower():
        return True

    out, _ = runCMD("ntpq -p 2>/dev/null | grep '^*' || true")
    if out.strip():
        return True

    if os.path.exists("/etc/adjtime"):
        return True

    print("No way to check ntp status, assuming it isn't synced...")

    return False

def measure(args, row, writer, csvfile):
    ntp_ok = checkNTPSync()
    ts = currentTime()
    wifi = parseNmcli(args.iface)
    device_count = getArpDevicesCount(args.iface)
    ping_stats = measureLatency(args.target)
    (download, upload) = testSpeed(server=args.iperf_addr, port=args.iperf_port)

    row.update(
        {  # pyright: ignore[reportArgumentType, reportCallIssue]
            "timestamp": ts,
            "iface": args.iface,
            "ssid": wifi.get("ssid", ""),
            "bssid": wifi.get("bssid", ""),
            "freq_mhz": wifi.get("freq_mhz", ""),
            "channel": wifi.get("channel", ""),
            "signal_dbm": wifi.get("signal_dbm", ""),
            "tx_bitrate_mbps": wifi.get("txrate", ""),
            "ping_target": args.target,
            "ping_avg_ms": ping_stats["avg_ms"],
            "ping_min_ms": ping_stats["min_ms"],
            "ping_max_ms": ping_stats["max_ms"],
            "ping_jitter_ms": ping_stats["jitter_ms"],
            "ping_loss_pct": ping_stats["loss_pct"],
            "ping_success": 1 if ping_stats["success"] else 0,
            "download": download,
            "upload": upload,
            "ntp_synced": "yes" if ntp_ok else "no",
            "num_of_connected_devices": device_count
        }
    )

    writer.writerow(row)
    csvfile.flush()

    print("Measurement done")
