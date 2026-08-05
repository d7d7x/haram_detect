import subprocess
import shutil
import json
import logging
from pathlib import Path
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

def is_ffmpeg_available() -> bool:
    """Check if ffmpeg executable is available in PATH."""
    return shutil.which("ffmpeg") is not None

def extract_audio(input_video: Path, output_wav: Path, sample_rate: int = 44100) -> bool:
    """Extract audio stream from video file into uncompressed PCM WAV."""
    output_wav.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_video),
        "-vn",                           # No video
        "-acodec", "pcm_s16le",          # PCM 16-bit
        "-ar", str(sample_rate),         # Sample rate
        "-ac", "2",                      # Stereo
        str(output_wav)
    ]
    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return output_wav.exists()
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg audio extraction failed: {e.stderr}")
        return False

def remux_video_and_audio(
    input_video: Path,
    input_audio: Path,
    output_video: Path,
    subtitle_file: Optional[Path] = None
) -> Tuple[bool, str]:
    """
    Re-mux video with new audio track using robust fallbacks for legacy/system FFmpeg binaries.
    Returns (success: bool, error_message: str).
    """
    output_video.parent.mkdir(parents=True, exist_ok=True)

    # Clean existing file if present
    if output_video.exists():
        try:
            output_video.unlink()
        except Exception:
            pass

    # Try Attempt 1: Fast stream copy + AAC with -strict -2 (Compatibility fix for older FFmpeg)
    cmd1 = [
        "ffmpeg", "-y",
        "-i", str(input_video),
        "-i", str(input_audio),
        "-c:v", "copy",
        "-c:a", "aac",
        "-strict", "-2",
        "-b:a", "192k",
        "-map", "0:v:0",
        "-map", "1:a:0"
    ]
    if subtitle_file and subtitle_file.exists():
        sub_codec = "mov_text" if output_video.suffix.lower() in [".mp4", ".m4v"] else "srt"
        cmd1.extend([
            "-i", str(subtitle_file),
            "-c:s", sub_codec,
            "-map", "2:s:0?"
        ])
    cmd1.append(str(output_video))

    try:
        res = subprocess.run(cmd1, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        if output_video.exists() and output_video.stat().st_size > 0:
            return True, "Success"
    except subprocess.CalledProcessError as e:
        logger.warning(f"FFmpeg Remux Attempt 1 failed: {e.stderr[:300]}")
        err1 = e.stderr

    # Try Attempt 2: Audio swap using libvo_aacenc or ac3 for legacy FFmpeg
    cmd2 = [
        "ffmpeg", "-y",
        "-i", str(input_video),
        "-i", str(input_audio),
        "-c:v", "copy",
        "-c:a", "ac3",
        "-b:a", "192k",
        "-map", "0:v:0",
        "-map", "1:a:0",
        str(output_video)
    ]
    try:
        res = subprocess.run(cmd2, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        if output_video.exists() and output_video.stat().st_size > 0:
            return True, "Success (Audio Re-muxed via AC3)"
    except subprocess.CalledProcessError as e:
        logger.warning(f"FFmpeg Remux Attempt 2 failed: {e.stderr[:300]}")
        err2 = e.stderr

    # Try Attempt 3: Change container format to .mkv if .mp4 failed
    if output_video.suffix.lower() == ".mp4":
        alt_output = output_video.with_suffix(".mkv")
        cmd3 = [
            "ffmpeg", "-y",
            "-i", str(input_video),
            "-i", str(input_audio),
            "-c:v", "copy",
            "-c:a", "aac",
            "-strict", "-2",
            "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            str(alt_output)
        ]
        try:
            res = subprocess.run(cmd3, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            if alt_output.exists() and alt_output.stat().st_size > 0:
                return True, f"Success (Saved as MKV: {alt_output.name})"
        except subprocess.CalledProcessError as e:
            logger.error(f"FFmpeg Remux Attempt 3 failed: {e.stderr[:300]}")
            err2 = e.stderr

    return False, f"FFmpeg failed: {err2 if 'err2' in locals() else err1}"
