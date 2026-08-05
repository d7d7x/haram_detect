@echo off
title AutoCensor AI Stremio Player
cd /d "%~dp0"
python main.py --cli --stremio "%~1"
