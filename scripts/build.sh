#!/usr/bin/env bash

set -euo pipefail

bash convert_ui.sh

pyinstaller ../gui.py --add-data "../analyser_server.py:." --add-data "../utils/analyser_utils.py:./utils" --add-data "../utils/literals.py:./utils" --add-data "../media/floor_template.svg:./media" --add-data "../media/mouse_right_click.png:./media" --onefile --windowed -n WifiAnalyser