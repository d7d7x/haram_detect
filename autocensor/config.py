import os
import sys
from pathlib import Path

# Base Paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

DEFAULT_DICTIONARY_PATH = DATA_DIR / "default_dictionary.json"
USER_DICTIONARY_PATH = DATA_DIR / "user_dictionary.json"
TEMP_DIR = BASE_DIR / "temp"
TEMP_DIR.mkdir(exist_ok=True)

# Censorship Modes
MODE_BEEP = "beep"
MODE_MUTE = "mute"
MODE_SUBTITLE_ONLY = "subtitle_only"

# App Defaults
DEFAULT_BEEP_FREQ = 1000  # 1kHz sine wave BEEP tone
DEFAULT_AUDIO_PADDING_MS = 50  # Additional 50ms audio padding around detected word
DEFAULT_STT_MODEL = "base"     # tiny, base, small, medium, large-v2

# Supported Extensions
VIDEO_EXTENSIONS = {".mp4", ".mkv", ".avi", ".mov", ".webm", ".flv"}
SUBTITLE_EXTENSIONS = {".srt", ".vtt", ".ass"}

# App UI Color Palette
THEME = {
    "primary": "#6366f1",         # Indigo
    "primary_hover": "#4f46e5",
    "background": "#0f172a",      # Slate 900
    "surface": "#1e293b",         # Slate 800
    "surface_light": "#334155",   # Slate 700
    "accent": "#10b981",          # Emerald
    "danger": "#ef4444",          # Red
    "text_primary": "#f8fafc",    # Slate 50
    "text_secondary": "#94a3b8"   # Slate 400
}
