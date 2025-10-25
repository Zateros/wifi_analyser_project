#!/usr/bin/env bash

pyinstaller ../gui.py --add-data "../media/floor_template.svg:." --add-data "../media/mouse_right_click.png:." --onefile --windowed -n wifianalyser