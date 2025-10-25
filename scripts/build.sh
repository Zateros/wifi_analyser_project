#!/usr/bin/env bash

pyinstaller ../gui.py --add-data "floor_template.svg:." --onefile --windowed -n wifianalyser