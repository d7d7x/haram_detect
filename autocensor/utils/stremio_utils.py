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
    r"""Find Stremio cache directory across all possible user drive configurations (prioritizing G:\stremio-cache)."""
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
