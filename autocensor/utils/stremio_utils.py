import os
import sys
import shutil
import json
import logging
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

STREMIO_SERVER_URL = "http://127.0.0.1:11470"

def get_stremio_cache_dir() -> Optional[Path]:
    """Find Stremio cache directory across all possible user drive configurations."""
    candidates = []

    if sys.platform == "win32":
        user_profile = os.getenv("USERPROFILE")
        appdata = os.getenv("APPDATA")
        
        if user_profile:
            candidates.append(Path(user_profile) / "stremio-cache")
            candidates.append(Path(user_profile) / "stremio-server" / "stremio-cache")

        if appdata:
            candidates.append(Path(appdata) / "stremio" / "stremio-cache")
            candidates.append(Path(appdata) / "stremio-server" / "stremio-cache")
            candidates.append(Path(appdata) / "stremio-desktop" / "stremio-cache")

    elif sys.platform == "darwin":
        candidates.append(Path.home() / "Library" / "Application Support" / "stremio" / "stremio-cache")
    else:  # Linux
        candidates.append(Path.home() / ".stremio-server" / "stremio-cache")

    # Return first candidate that exists or create default user profile cache path
    for p in candidates:
        if p.exists():
            return p

    # Fallback to creating/returning standard user profile cache directory
    if sys.platform == "win32" and os.getenv("USERPROFILE"):
        default_p = Path(os.getenv("USERPROFILE")) / "stremio-cache"
        default_p.mkdir(parents=True, exist_ok=True)
        return default_p

    return candidates[0] if candidates else None

def get_active_stremio_stream_info() -> Optional[Dict[str, Any]]:
    """
    Query Stremio local streaming server API (http://127.0.0.1:11470/stats.json)
    to get active streaming episode details (torrent name, file name, download stats).
    """
    try:
        req = urllib.request.Request(f"{STREMIO_SERVER_URL}/stats.json", headers={"User-Agent": "AutoCensorAI"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and isinstance(data, dict):
                # Extract stream stats if torrent is actively downloading/buffering
                for key, val in data.items():
                    if isinstance(val, dict) and ("name" in val or "filename" in val or "stream" in val):
                        return {
                            "infohash": key,
                            "name": val.get("name") or val.get("filename") or "Unknown Episode",
                            "peers": val.get("peers", 0),
                            "downloadSpeed": val.get("downloadSpeed", 0),
                            "path": val.get("path")
                        }
    except Exception as e:
        logger.debug(f"Stremio server query: {e}")
    return None

def find_external_player() -> Optional[Path]:
    """Find VLC or MPV player executable on system."""
    vlc = shutil.which("vlc") or shutil.which("vlc.exe")
    if vlc:
        return Path(vlc)

    mpv = shutil.which("mpv") or shutil.which("mpv.exe")
    if mpv:
        return Path(mpv)

    if sys.platform == "win32":
        vlc_paths = [
            Path("C:/Program Files/VideoLAN/VLC/vlc.exe"),
            Path("C:/Program Files (x86)/VideoLAN/VLC/vlc.exe")
        ]
        for p in vlc_paths:
            if p.exists():
                return p

    return None
