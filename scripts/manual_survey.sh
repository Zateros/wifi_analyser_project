#!/usr/bin/env bash

if [ "$EUID" -ne 0 ]
    echo "The script isn't running as root!\nFor all measurements to succeed, make sure to run it as root."
fi

python3 ../wifi_analyser.py --iface wlp1s0 --target 1.1.1.1 --out "$1".csv --overwrite --debug --interval 1.0