@echo off
title Media Sanitizer Pro
cd /d "%~dp0"
call venv\Scripts\activate.bat
python main.py
pause
