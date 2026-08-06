import json
import subprocess
from pathlib import Path
from typing import Optional
from core.models import MediaInfo, AudioStreamInfo, SubtitleStreamInfo
from utils.logging import logger

class FFprobeService:
    def __init__(self, ffprobe_path: str = "ffprobe"):
        self.ffprobe_path = ffprobe_path

    def inspect_file(self, filepath: str) -> MediaInfo:
        """Inspects local media file using ffprobe and returns MediaInfo object."""
        file_path = Path(filepath)
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {filepath}")

        cmd = [
            self.ffprobe_path,
            "-v", "quiet",
            "-print_format", "json",
            "-show_format",
            "-show_streams",
            str(file_path)
        ]

        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
            data = json.loads(res.stdout)
        except Exception as e:
            logger.error(f"FFprobe inspection failed for {filepath}: {e}")
            return MediaInfo(
                filepath=filepath,
                duration=0.0,
                video_codec="unknown",
                width=0,
                height=0,
                fps=0.0,
                bitrate=0,
                file_size_bytes=file_path.stat().st_size if file_path.exists() else 0,
                is_drm_protected=True
            )

        format_info = data.get("format", {})
        streams = data.get("streams", [])

        duration = float(format_info.get("duration", 0.0))
        bitrate = int(format_info.get("bit_rate", 0))
        file_size = int(format_info.get("size", file_path.stat().st_size))

        video_codec = "none"
        width = 0
        height = 0
        fps = 0.0
        is_drm = False

        audio_streams = []
        subtitle_streams = []

        for stream in streams:
            codec_type = stream.get("codec_type")
            codec_name = stream.get("codec_name", "unknown")
            tags = stream.get("tags", {})
            lang = tags.get("language", "und")
            title = tags.get("title", "")

            # DRM check indicators (e.g. encrypted codecs, cenc, drm tags)
            if stream.get("is_avc", False) is False and codec_name in ["cenc", "encv", "enca", "piff"]:
                is_drm = True

            if codec_type == "video" and video_codec == "none":
                video_codec = codec_name
                width = int(stream.get("width", 0))
                height = int(stream.get("height", 0))
                
                # Parse FPS
                r_fps = stream.get("r_frame_rate", "0/0")
                if "/" in r_fps:
                    num, den = r_fps.split("/")
                    if float(den) > 0:
                        fps = round(float(num) / float(den), 3)

            elif codec_type == "audio":
                audio_streams.append(AudioStreamInfo(
                    index=int(stream.get("index", 0)),
                    codec_name=codec_name,
                    channels=int(stream.get("channels", 2)),
                    language=lang,
                    title=title
                ))
            elif codec_type == "subtitle":
                subtitle_streams.append(SubtitleStreamInfo(
                    index=int(stream.get("index", 0)),
                    codec_name=codec_name,
                    language=lang,
                    title=title
                ))

        if video_codec in ["cenc", "encv"] or format_info.get("format_name") == "drm":
            is_drm = True

        return MediaInfo(
            filepath=str(file_path),
            duration=duration,
            video_codec=video_codec,
            width=width,
            height=height,
            fps=fps,
            bitrate=bitrate,
            file_size_bytes=file_size,
            audio_streams=audio_streams,
            subtitle_streams=subtitle_streams,
            is_drm_protected=is_drm
        )
