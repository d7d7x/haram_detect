import os
import sys
import shutil
import json
import logging
import subprocess
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Any, List

logger = logging.getLogger(__name__)

STREMIO_SERVER_URL = "http://127.0.0.1:11470"

def get_stremio_cache_dir() -> Optional[Path]:
    r"""Find Stremio cache directory across all possible user drive configurations."""
    candidates = [
        Path("G:/stremio-cache"),
        Path("G:/stremio-server/stremio-cache")
    ]

    workspace_dir = Path(__file__).resolve().parent.parent.parent
    candidates.append(workspace_dir / "stremio-cache")

    if sys.platform == "win32":
        user_profile = os.getenv("USERPROFILE")
        appdata = os.getenv("APPDATA")
        localappdata = os.getenv("LOCALAPPDATA")
        
        if user_profile:
            candidates.append(Path(user_profile) / "stremio-cache")
            candidates.append(Path(user_profile) / "stremio-server" / "stremio-cache")

        if appdata:
            candidates.append(Path(appdata) / "stremio" / "stremio-cache")
            candidates.append(Path(appdata) / "stremio-server" / "stremio-cache")
            candidates.append(Path(appdata) / "stremio-desktop" / "stremio-cache")

        if localappdata:
            candidates.append(Path(localappdata) / "Programs" / "Ldirect" / "stremio-cache")

    elif sys.platform == "darwin":
        candidates.append(Path.home() / "Library" / "Application Support" / "stremio" / "stremio-cache")
    else:  # Linux
        candidates.append(Path.home() / ".stremio-server" / "stremio-cache")

    for p in candidates:
        if p.exists():
            return p

    g_cache = Path("G:/stremio-cache")
    try:
        g_cache.mkdir(parents=True, exist_ok=True)
        return g_cache
    except Exception:
        pass

    return candidates[0] if candidates else None

def get_active_stremio_stream_info() -> Optional[Dict[str, Any]]:
    """
    Query Stremio local streaming server API (http://127.0.0.1:11470/stats.json)
    to get active streaming episode details.
    """
    try:
        req = urllib.request.Request(f"{STREMIO_SERVER_URL}/stats.json", headers={"User-Agent": "AutoCensorAI"})
        with urllib.request.urlopen(req, timeout=1.5) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            if data and isinstance(data, dict):
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

def find_mpv_executable() -> Optional[Path]:
    """Find MPV executable on system across project data, PATH, and Windows install paths."""
    # Check internal portable MPV location first
    project_root = Path(__file__).resolve().parent.parent.parent
    internal_mpv = project_root / "data" / "mpv" / "mpv.exe"
    if internal_mpv.exists():
        return internal_mpv

    # Check PATH environment variable
    mpv = shutil.which("mpv") or shutil.which("mpv.exe")
    if mpv:
        return Path(mpv)

    if sys.platform == "win32":
        user_profile = os.getenv("USERPROFILE", "")
        local_app_data = os.getenv("LOCALAPPDATA", "")
        app_data = os.getenv("APPDATA", "")

        candidates = [
            Path("C:/Program Files/mpv/mpv.exe"),
            Path("C:/Program Files (x86)/mpv/mpv.exe"),
            Path("C:/Program Files/mpv.net/mpvnet.exe"),
            Path("C:/Program Files/mpv.net/mpv.exe"),
            Path("C:/mpv/mpv.exe"),
            Path("C:/mpv-x86_64/mpv.exe"),
            Path(local_app_data) / "Programs" / "mpv" / "mpv.exe",
            Path(local_app_data) / "Programs" / "shinchiro.mpv" / "mpv.exe",
            Path(user_profile) / "scoop" / "apps" / "mpv" / "current" / "mpv.exe",
            Path("C:/ProgramData/chocolatey/bin/mpv.exe"),
            Path(app_data) / "stremio" / "mpv.exe",
        ]

        for p in candidates:
            if str(p) and p.exists():
                return p

        # Search drive C:\Program Files recursively for mpv.exe if not found above
        try:
            pf = Path("C:/Program Files")
            if pf.exists():
                for found in pf.glob("**/mpv.exe"):
                    return found
        except Exception:
            pass

    return None

def find_external_player() -> Optional[Path]:
    """Find external player executable (prefer MPV for IPC support, fallback VLC)."""
    mpv = find_mpv_executable()
    if mpv:
        return mpv

    vlc = shutil.which("vlc") or shutil.which("vlc.exe")
    if vlc:
        return Path(vlc)

    if sys.platform == "win32":
        vlc_paths = [
            Path("C:/Program Files/VideoLAN/VLC/vlc.exe"),
            Path("C:/Program Files (x86)/VideoLAN/VLC/vlc.exe")
        ]
        for p in vlc_paths:
            if p.exists():
                return p

    return None

def locate_subtitle_candidates_in_cache(cache_dir: Optional[Path] = None) -> List[Path]:
    """Search for subtitle files (.srt, .vtt, .ass) in Stremio cache directory."""
    if not cache_dir:
        cache_dir = get_stremio_cache_dir()
    if not cache_dir or not cache_dir.exists():
        return []

    sub_files = []
    for ext in [".srt", ".vtt", ".ass"]:
        sub_files.extend(cache_dir.rglob(f"*{ext}"))

    sub_files.sort(key=lambda p: p.stat().st_mtime, reverse=True)
    return sub_files

def extract_embedded_subtitles(video_path: Path, output_dir: Optional[Path] = None) -> Optional[Path]:
    """Extract embedded subtitle track from video file using FFmpeg into an SRT file."""
    if not video_path.exists():
        return None

    out_dir = output_dir or video_path.parent
    out_dir.mkdir(parents=True, exist_ok=True)
    out_srt = out_dir / f"{video_path.stem}_embedded.srt"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-map", "0:s:0?",
        "-c:s", "srt",
        str(out_srt)
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        if out_srt.exists() and out_srt.stat().st_size > 0:
            logger.info(f"Extracted embedded subtitle -> {out_srt.name}")
            return out_srt
    except Exception as e:
        logger.debug(f"Embedded subtitle extraction notice for {video_path.name}: {e}")

    return None
