import os
import sys
import shutil
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

def get_stremio_cache_dir() -> Optional[Path]:
    """Find Stremio cache directory on Windows, macOS, or Linux."""
    if sys.platform == "win32":
        appdata = os.getenv("APPDATA")
        if appdata:
            path = Path(appdata) / "stremio" / "stremio-cache"
            if path.exists():
                return path
            # Alternative path
            alt_path = Path(appdata) / "stremio-desktop" / "stremio-cache"
            if alt_path.exists():
                return alt_path
    elif sys.platform == "darwin":
        path = Path.home() / "Library" / "Application Support" / "stremio" / "stremio-cache"
        if path.exists():
            return path
    else:  # Linux
        path = Path.home() / ".stremio-server" / "stremio-cache"
        if path.exists():
            return path
    return None

def find_external_player() -> Optional[Path]:
    """Find VLC or MPV player executable on system."""
    # Check PATH first
    vlc = shutil.which("vlc") or shutil.which("vlc.exe")
    if vlc:
        return Path(vlc)

    mpv = shutil.which("mpv") or shutil.which("mpv.exe")
    if mpv:
        return Path(mpv)

    # Windows standard installation paths for VLC
    if sys.platform == "win32":
        vlc_paths = [
            Path("C:/Program Files/VideoLAN/VLC/vlc.exe"),
            Path("C:/Program Files (x86)/VideoLAN/VLC/vlc.exe")
        ]
        for p in vlc_paths:
            if p.exists():
                return p

    return None
