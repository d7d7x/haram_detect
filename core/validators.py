import os
import shutil
import subprocess
from pathlib import Path
from typing import Tuple, List
from core.models import SanitizationSegment
from utils.logging import logger

SUPPORTED_EXTENSIONS = {".mp4", ".mkv", ".webm", ".mov", ".avi", ".ts", ".m4v"}

def check_ffmpeg_installed(ffmpeg_path: str = "ffmpeg", ffprobe_path: str = "ffprobe") -> Tuple[bool, str]:
    """Validates that ffmpeg and ffprobe are executable and available."""
    ffmpeg_bin = shutil.which(ffmpeg_path) or (ffmpeg_path if os.path.exists(ffmpeg_path) else None)
    ffprobe_bin = shutil.which(ffprobe_path) or (ffprobe_path if os.path.exists(ffprobe_path) else None)

    if not ffmpeg_bin:
        return False, f"FFmpeg binary not found at '{ffmpeg_path}'. Please install FFmpeg or set its path in Settings."
    if not ffprobe_bin:
        return False, f"FFprobe binary not found at '{ffprobe_path}'. Please install FFprobe or set its path in Settings."

    try:
        res = subprocess.run([ffmpeg_bin, "-version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=5)
        if res.returncode != 0:
            return False, "FFmpeg returned non-zero exit code on version check."
    except Exception as e:
        return False, f"Failed to execute FFmpeg: {e}"

    return True, "FFmpeg and FFprobe are properly configured and operational."

def is_supported_video_file(filepath: str) -> bool:
    """Verifies if the file extension is supported."""
    ext = Path(filepath).suffix.lower()
    return ext in SUPPORTED_EXTENSIONS

def validate_segments(segments: List[SanitizationSegment], duration: float) -> Tuple[bool, List[str]]:
    """Validates sanitization segments for negative durations, out-of-bounds start times, or overlaps."""
    errors = []
    sorted_segs = sorted(segments, key=lambda x: x.start)

    for i, seg in enumerate(sorted_segs):
        if seg.start < 0:
            errors.append(f"Segment {seg.id} has negative start time ({seg.start}s).")
        if seg.end <= seg.start:
            errors.append(f"Segment {seg.id} has invalid duration (start {seg.start}s >= end {seg.end}s).")
        if seg.start >= duration:
            errors.append(f"Segment {seg.id} start time ({seg.start}s) exceeds media duration ({duration}s).")
        if seg.end > duration:
            seg.end = duration  # Clamp to duration

        if i > 0:
            prev = sorted_segs[i - 1]
            if prev.enabled and seg.enabled and prev.end > seg.start:
                errors.append(f"Overlapping segments detected between '{prev.id}' ({prev.start}-{prev.end}) and '{seg.id}' ({seg.start}-{seg.end}).")

    return len(errors) == 0, errors
