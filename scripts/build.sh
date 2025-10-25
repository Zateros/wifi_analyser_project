#!/usr/bin/env bash

pyinstaller ../gui.py --add-data "../media/floor_template.svg:./media" --add-data "../media/mouse_right_click.png:./media" --onefile --windowed -n WifiAnalyser