#!/usr/bin/env bash

set -euo pipefail

(
    apt update -y && apt upgrade -y && apt install -y iproute2 iputils-ping tcpdump network-manager

    pip install ipykernel pillow cairosvg matplotlib pandas numpy speedtest-cli

) >& "$(dirname "$(realpath "$0")")/on-create.log"

echo "Done"