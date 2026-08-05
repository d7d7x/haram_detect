import subprocess
import shutil
import json
import logging
from pathlib import Path
from typing import Optional

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
) -> bool:
    """
    Re-mux video with new audio track without re-encoding video stream (-c:v copy).
    Optionally embed or attach subtitle.
    """
    output_video.parent.mkdir(parents=True, exist_ok=True)
    
    sub_codec = "mov_text" if output_video.suffix.lower() in [".mp4", ".m4v"] else "srt"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_video),
        "-i", str(input_audio),
    ]

    if subtitle_file and subtitle_file.exists():
        cmd.extend(["-i", str(subtitle_file)])
        cmd.extend([
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-c:s", sub_codec,
            "-map", "0:v:0",
            "-map", "1:a:0",
            "-map", "2:s:0?"
        ])
    else:
        cmd.extend([
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0"
        ])

    cmd.append(str(output_video))

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return output_video.exists() and output_video.stat().st_size > 0
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg primary remuxing failed: {e.stderr}")
        
        # Fallback 1: Simple video + audio swap without subtitle stream mapping
        fallback_cmd = [
            "ffmpeg", "-y",
            "-i", str(input_video),
            "-i", str(input_audio),
            "-c:v", "copy",
            "-c:a", "aac", "-b:a", "192k",
            "-map", "0:v:0",
            "-map", "1:a:0",
            str(output_video)
        ]
        try:
            subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            return output_video.exists() and output_video.stat().st_size > 0
        except subprocess.CalledProcessError as ex:
            logger.error(f"FFmpeg fallback remuxing failed: {ex.stderr}")

    return False
