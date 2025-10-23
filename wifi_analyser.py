#!/usr/bin/env python3

import statistics, re, argparse, subprocess, csv, datetime, time, os, json, sys

debug = False


def current_time():
    return datetime.datetime.now().astimezone().strftime("%Y-%m-%d %H:%M:%S")


def run_cmd(cmd, timeout=3):
    res = subprocess.run(
        cmd,
        shell=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        timeout=timeout,
    )
    return res.stdout.strip(), res.returncode


def parse_nmcli(iface):
    data = {
        "ssid": "",
        "bssid": "",
        "freq_mhz": "",
        "channel": "",
        "txrate": "",
        "signal_dbm": "",
    }

    print("Parsing nmcli...")

    out, rc = run_cmd(
        f"nmcli -t -f IN-USE,SSID,BSSID,FREQ,CHAN,RATE,SIGNAL dev wifi list ifname {iface}",
        timeout=10,
    )
    if rc != 0 or not out:
        if debug:
            print(f"Returned null; out={out}; rc={rc}")
        return data

    split_pattern = re.compile(r"(?<!\\):")

    for line in out.splitlines():
        if not line.strip():
            continue

        parts = [p.replace("\\:", ":") for p in split_pattern.split(line)]
        if len(parts) < 7:
            continue

        in_use, ssid, bssid, freq, chan, rate, signal = parts[:7]
        if debug:
            print(
                f"in_use={in_use}; ssid={ssid}; bssid={bssid}; freq={freq}; chan={chan}; rate={rate}; signal={signal}"
            )
        if in_use.strip() == "*":
            if debug:
                print("is in_use")
            data["ssid"] = ssid.strip()
            data["bssid"] = bssid.strip()
            data["freq_mhz"] = freq.replace(" MHz", "").strip()
            data["channel"] = chan.strip()
            data["txrate"] = rate.replace(" Mbit/s", "").strip()
            data["signal_dbm"] = signal.strip()
            break

    return data


def measure_latency(target, count=10, timeout=1):
    """
    Pings a target multiple times and returns detailed latency metrics.
    Returns a dict:
      {
        'avg_ms': float,
        'min_ms': float,
        'max_ms': float,
        'jitter_ms': float,
        'loss_pct': float,
        'success': bool
      }
    """
    print("Measuring latency, jitter, packet loss...")
    cmd = f"ping -c {count} -W {timeout} {target}"
    out, rc = run_cmd(cmd, timeout=count + 5)
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


def test_speed(server="speedtest.fra1.de.leaseweb.net", port="5201-5210", duration=10):

    print(f"Running iperf3 speed test to {server}...")

    def run_iperf3(reverse=False):
        cmd = [
            "iperf3",
            "-c",
            server,
            "-J",
            "-t",
            str(duration),
            "-p",
            port,
            "--connect-timeout",
            "3000",
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

    if debug:
        print(f"→ Download: {download} Mbps | Upload: {upload} Mbps")

    return download, upload


def check_ntp_sync() -> bool:
    print("Is ntp synced?")

    out, _ = run_cmd("timedatectl show -p NTPSynchronized --value 2>/dev/null")
    if out.strip().lower() == "yes":
        return True

    out, _ = run_cmd("chronyc tracking | grep 'Leap status' || true")
    if "normal" in out.lower():
        return True

    out, _ = run_cmd("ntpq -p 2>/dev/null | grep '^*' || true")
    if out.strip():
        return True

    if os.path.exists("/etc/adjtime"):
        return True

    print("No way to check ntp status, assuming it isn't synced...")

    return False


def measure(args, row, writer, csvfile):
    ntp_ok = check_ntp_sync()
    ts = current_time()
    wifi = parse_nmcli(args.iface)
    ping_stats = measure_latency(args.target)
    (download, upload) = test_speed(server=args.iperf_addr, port=args.iperf_port)

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
            "pcap_file": args.pcap if args.pcap else "",
            "ntp_synced": "yes" if ntp_ok else "no",
        }
    )

    writer.writerow(row)
    csvfile.flush()


def entry(args):
    global debug

    p = argparse.ArgumentParser()
    p.add_argument("--iface", required=True)
    p.add_argument("--target", default="0.0.0.0")
    p.add_argument("--iperf_addr", default="speedtest.fra1.de.leaseweb.net")
    p.add_argument("--iperf_port", default="5201-5210")
    p.add_argument("--out", default="survey.csv")
    p.add_argument("--pcap", default=None)
    p.add_argument(
        "--interval", type=float, default=1.0, help="seconds between samples"
    )
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--debug", action="store_true")
    p.add_argument("--x", default=None)
    p.add_argument("--y", default=None)
    p.add_argument("--pir", default=None)
    args = p.parse_args(args)

    debug = args.debug

    headers = [
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

    tcpdump_proc = None
    if args.pcap:
        print("Starting tcpdump...")
        tcpdump_proc = subprocess.Popen(
            ["tcpdump", "-i", args.iface, "-w", args.pcap],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    first_write = not os.path.exists(args.out) or args.overwrite
    csvfile = open(args.out, "w" if args.overwrite else "a", newline="")
    writer = csv.DictWriter(csvfile, fieldnames=headers)
    if first_write:
        writer.writeheader()
        csvfile.flush()

    seq = 0

    if not args.x or not args.y or not args.pir:
        print("Press Ctrl+C to stop")
        try:
            while True:
                seq += 1

                row = {h: "" for h in headers}

                try:
                    inp = input(
                        f"[{seq}] enter position x,y and the position in the room (1 - closest to the window, 2 - middle of the room, 3 - at the door) (or blank to skip): "
                    )
                except EOFError:
                    inp = ""
                
                if inp.strip():
                    try:
                        x, y, pir = inp.split(",")
                        row["position_x"] = x.strip()
                        row["position_y"] = y.strip()
                        row["position_in_room"] = pir.strip()
                    except Exception as e:
                        print(f"ERROR: {e}")

                measure(args, row, writer, csvfile)

                time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopping survey...")
        finally:
            csvfile.close()
            if tcpdump_proc:
                print("Stopping tcpdump...")
                tcpdump_proc.terminate()
                tcpdump_proc.wait(timeout=5)

            print("Done.")
    else:
        row = {h: "" for h in headers}

        row["position_x"] = args.x
        row["position_y"] = args.y
        row["position_in_room"] = args.pir

        measure(args, row, writer, csvfile)

        csvfile.close()

        if tcpdump_proc:
            print("Stopping tcpdump...")
            tcpdump_proc.terminate()
            tcpdump_proc.wait(timeout=5)


if __name__ == "__main__":
    entry(sys.argv[1:])
