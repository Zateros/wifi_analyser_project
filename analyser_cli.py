#!/usr/bin/env python3

from utils.analyser_utils import measure
from utils.literals import (
    MEASURE_HEADERS,
    DEFAULT_IPERF_ADDRESS,
    DEFAULT_IPERF_PORT,
    DEFAULT_TARGET,
)
import argparse, csv, time, os, sys


def parseArgs():
    p = argparse.ArgumentParser()
    p.add_argument("--iface")
    p.add_argument("--target", default=DEFAULT_TARGET)
    p.add_argument("--iperf_addr", default=DEFAULT_IPERF_ADDRESS)
    p.add_argument("--iperf_port", default=DEFAULT_IPERF_PORT)
    p.add_argument("--out", default="survey.csv")
    p.add_argument(
        "--interval", type=float, default=1.0, help="seconds between samples"
    )
    p.add_argument("--overwrite", action="store_true")
    p.add_argument("--x", default=None)
    p.add_argument("--y", default=None)
    p.add_argument("--pir", default=None)

    return p.parse_args(sys.argv[1:])


def repeating(args):
    print("Press Ctrl+C to stop")
    seq = 0
    try:
        while True:
            seq += 1

            row = {h: "" for h in MEASURE_HEADERS}

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

        print("Done.")


def single(args):
    row = {h: "" for h in MEASURE_HEADERS}

    row["position_x"] = args.x
    row["position_y"] = args.y
    row["position_in_room"] = args.pir

    measure(args, row, writer, csvfile)

    csvfile.close()


if __name__ == "__main__":
    args = parseArgs()

    first_write = not os.path.exists(args.out) or args.overwrite
    csvfile = open(args.out, "w" if args.overwrite else "a", newline="")
    writer = csv.DictWriter(csvfile, fieldnames=MEASURE_HEADERS)
    if first_write:
        writer.writeheader()
        csvfile.flush()

    if not args.x or not args.y or not args.pir:
        repeating(args)
    else:
        single(args)
