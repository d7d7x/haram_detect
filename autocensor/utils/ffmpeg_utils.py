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
    cmd = [
        "ffmpeg", "-y",
        "-i", str(input_video),
        "-i", str(input_audio),
        "-c:v", "copy",                # Ultra fast video copy without quality loss
        "-c:a", "aac",                 # Fast AAC audio encoding
        "-b:a", "192k",
        "-map", "0:v:0",               # Map video from input 0
        "-map", "1:a:0"                # Map audio from input 1 (censored audio)
    ]
    
    if subtitle_file and subtitle_file.exists():
        cmd.extend([
            "-i", str(subtitle_file),
            "-map", "2:s:0?",
            "-c:s", "mov_text" if output_video.suffix.lower() == ".mp4" else "copy",
            "-metadata:s:s:0", "language=ara"
        ])
    
    cmd.append(str(output_video))

    try:
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
        return output_video.exists()
    except subprocess.CalledProcessError as e:
        logger.error(f"FFmpeg remuxing failed: {e.stderr}")
        # Fallback to simple audio swap without subtitle embedding if subtitle mapping failed
        if subtitle_file:
            fallback_cmd = [
                "ffmpeg", "-y",
                "-i", str(input_video),
                "-i", str(input_audio),
                "-c:v", "copy",
                "-c:a", "aac",
                "-map", "0:v:0",
                "-map", "1:a:0",
                str(output_video)
            ]
            try:
                subprocess.run(fallback_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
                return output_video.exists()
            except Exception as ex:
                logger.error(f"Fallback remuxing also failed: {ex}")
        return False
