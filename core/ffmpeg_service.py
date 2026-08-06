import subprocess
import os
import re
from pathlib import Path
from typing import List, Tuple, Callable, Optional
from core.models import AppSettings, SanitizationSegment, SanitizationAction
from utils.logging import logger
from utils.paths import get_temp_dir

class FFmpegService:
    def __init__(self, settings: AppSettings):
        self.settings = settings
        self.ffmpeg_path = settings.ffmpeg_path

    def extract_audio(self, video_path: str, output_wav_path: str, progress_callback: Optional[Callable[[float], None]] = None) -> str:
        """Extracts 16kHz mono WAV audio from video file for speech recognition."""
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", video_path,
            "-vn",
            "-acodec", "pcm_s16le",
            "-ar", "16000",
            "-ac", "1",
            output_wav_path
        ]
        logger.info(f"Extracting audio: {' '.join(cmd)}")
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Audio extraction failed: {res.stderr}")
        return output_wav_path

    def extract_embedded_subtitles(self, video_path: str, stream_index: int, output_srt_path: str) -> str:
        """Extracts embedded subtitle stream to SRT format."""
        cmd = [
            self.ffmpeg_path, "-y",
            "-i", video_path,
            "-map", f"0:{stream_index}",
            output_srt_path
        ]
        logger.info(f"Extracting subtitles: {' '.join(cmd)}")
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"Subtitle extraction failed: {res.stderr}")
        return output_srt_path

    def generate_thumbnail(self, video_path: str, timestamp_sec: float, output_image_path: str) -> bool:
        """Generates a JPEG thumbnail at a specific timestamp."""
        cmd = [
            self.ffmpeg_path, "-y",
            "-ss", str(timestamp_sec),
            "-i", video_path,
            "-vframes", "1",
            "-q:v", "2",
            output_image_path
        ]
        try:
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=10)
            return res.returncode == 0
        except Exception as e:
            logger.error(f"Failed to generate thumbnail at {timestamp_sec}s: {e}")
            return False

    def embed_subtitles_into_video(
        self,
        video_path: str,
        ar_sub_path: Optional[str],
        en_sub_path: Optional[str],
        output_path: str
    ) -> bool:
        """Embeds/muxes both Arabic and English redacted SRT subtitle tracks inside output container."""
        ext = Path(output_path).suffix.lower()
        sub_codec = "mov_text" if ext in [".mp4", ".m4v", ".mov"] else "subrip"

        temp_out = str(Path(output_path).with_name(f"{Path(output_path).stem}_subbed{ext}"))
        cmd = [self.ffmpeg_path, "-y", "-i", video_path]

        sub_idx = 1
        map_args = ["-map", "0:v", "-map", "0:a"]
        meta_args = []

        if ar_sub_path and Path(ar_sub_path).exists():
            cmd.extend(["-i", ar_sub_path])
            map_args.extend(["-map", f"{sub_idx}:0"])
            track_num = sub_idx - 1
            meta_args.extend([
                f"-metadata:s:s:{track_num}", "language=ara",
                f"-metadata:s:s:{track_num}", "title=ترجمة عربية مطهرة",
                f"-disposition:s:{track_num}", "default"
            ])
            sub_idx += 1

        if en_sub_path and Path(en_sub_path).exists():
            cmd.extend(["-i", en_sub_path])
            map_args.extend(["-map", f"{sub_idx}:0"])
            track_num = sub_idx - 1
            meta_args.extend([
                f"-metadata:s:s:{track_num}", "language=eng",
                f"-metadata:s:s:{track_num}", "title=Sanitized English Subtitles"
            ])
            sub_idx += 1

        cmd.extend(map_args)
        cmd.extend([
            "-c:v", "copy",
            "-c:a", "copy",
            "-c:s", sub_codec
        ])
        cmd.extend(meta_args)
        cmd.append(temp_out)

        logger.info(f"Muxing embedded subtitle tracks: {' '.join(cmd)}")
        res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        if res.returncode == 0 and Path(temp_out).exists():
            import time
            import shutil
            for attempt in range(5):
                try:
                    if Path(output_path).exists():
                        os.remove(output_path)
                    shutil.move(temp_out, output_path)
                    logger.info(f"Successfully embedded dual subtitle tracks into {output_path}")
                    return True
                except PermissionError:
                    time.sleep(0.5)

            logger.warning(f"Output file locked by Windows process. Saved embedded video as: {temp_out}")
            return True

        logger.error(f"Failed to mux subtitle tracks: {res.stderr}")
        return False

    def build_black_mute_filter_complex(self, segments: List[SanitizationSegment]) -> Tuple[str, str]:
        """Constructs FFmpeg filter_complex strings for black screen and volume mute enabling."""
        black_enables = []
        mute_enables = []

        for seg in segments:
            if not seg.enabled:
                continue
            enable_str = f"between(t,{seg.start:.3f},{seg.end:.3f})"
            if seg.action in [SanitizationAction.BLACK_MUTE, SanitizationAction.BLACK_ONLY]:
                black_enables.append(enable_str)
            if seg.action in [SanitizationAction.BLACK_MUTE, SanitizationAction.MUTE]:
                mute_enables.append(enable_str)

        v_filter = ""
        a_filter = ""

        if black_enables:
            expr = "+".join(black_enables)
            v_filter = f"drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='{expr}'"

        if mute_enables:
            expr = "+".join(mute_enables)
            a_filter = f"volume=0:enable='{expr}'"

        return v_filter, a_filter

    def render_black_mute(
        self,
        input_path: str,
        output_path: str,
        segments: List[SanitizationSegment],
        total_duration: float = 0.0,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> bool:
        """Renders media output applying black box and audio muting over specified segments."""
        v_filter, a_filter = self.build_black_mute_filter_complex(segments)

        cmd = [self.ffmpeg_path, "-y", "-i", input_path]

        filter_complex_parts = []
        if v_filter:
            filter_complex_parts.append(f"[0:v:0]{v_filter}[outv]")
        else:
            filter_complex_parts.append("[0:v:0]null[outv]")

        if a_filter:
            filter_complex_parts.append(f"[0:a:0]{a_filter}[outa]")
        else:
            filter_complex_parts.append("[0:a:0]anull[outa]")

        filter_complex_str = ";".join(filter_complex_parts)

        cmd.extend([
            "-filter_complex", filter_complex_str,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", self.settings.video_codec,
            "-crf", str(self.settings.crf),
            "-preset", self.settings.preset,
            "-c:a", self.settings.audio_codec,
            "-b:a", self.settings.audio_bitrate,
            output_path
        ])

        logger.info(f"Executing Black/Mute Render: {' '.join(cmd)}")
        return self._run_ffmpeg_cmd(cmd, progress_callback, total_duration)

    def calculate_keep_intervals(self, cut_segments: List[SanitizationSegment], total_duration: float) -> List[Tuple[float, float]]:
        """Calculates intervals to keep between cut segments."""
        sorted_cuts = sorted([s for s in cut_segments if s.enabled and s.action == SanitizationAction.CUT], key=lambda x: x.start)
        keep = []
        curr = 0.0

        for s in sorted_cuts:
            if s.start > curr:
                keep.append((curr, s.start))
            curr = max(curr, s.end)

        if curr < total_duration:
            keep.append((curr, total_duration))

        return keep

    def render_cut_mode(
        self,
        input_path: str,
        output_path: str,
        cut_segments: List[SanitizationSegment],
        total_duration: float,
        progress_callback: Optional[Callable[[str, float], None]] = None
    ) -> bool:
        """Renders media output by cleanly cutting specified segments using trim/concat filters."""
        keep_intervals = self.calculate_keep_intervals(cut_segments, total_duration)

        if not keep_intervals:
            logger.error("No intervals left to keep! Entire video is cut.")
            return False

        filter_parts = []
        concat_inputs = []

        for idx, (k_start, k_end) in enumerate(keep_intervals):
            filter_parts.append(f"[0:v:0]trim=start={k_start:.3f}:end={k_end:.3f},setpts=PTS-STARTPTS[v{idx}]")
            filter_parts.append(f"[0:a:0]atrim=start={k_start:.3f}:end={k_end:.3f},asetpts=PTS-STARTPTS[a{idx}]")
            concat_inputs.append(f"[v{idx}][a{idx}]")

        concat_filter = f"{''.join(concat_inputs)}concat=n={len(keep_intervals)}:v=1:a=1[outv][outa]"
        filter_parts.append(concat_filter)

        filter_complex_str = ";".join(filter_parts)

        cmd = [
            self.ffmpeg_path, "-y",
            "-i", input_path,
            "-filter_complex", filter_complex_str,
            "-map", "[outv]",
            "-map", "[outa]",
            "-c:v", self.settings.video_codec,
            "-crf", str(self.settings.crf),
            "-preset", self.settings.preset,
            "-c:a", self.settings.audio_codec,
            "-b:a", self.settings.audio_bitrate,
            output_path
        ]

        logger.info(f"Executing Cut Render: {' '.join(cmd)}")
        return self._run_ffmpeg_cmd(cmd, progress_callback, total_duration)

    def _run_ffmpeg_cmd(
        self,
        cmd: List[str],
        progress_callback: Optional[Callable[[str, float], None]] = None,
        total_duration: float = 0.0
    ) -> bool:
        """Executes FFmpeg process and reports encoding progress line-by-line."""
        try:
            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                errors="replace",
                bufsize=1
            )

            time_regex = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")
            stderr_lines = []

            for line in iter(process.stderr.readline, ''):
                if not line:
                    break
                stderr_lines.append(line)
                m = time_regex.search(line)
                if m and total_duration > 0 and progress_callback:
                    h, mins, s, ms = map(int, m.groups())
                    curr_sec = h * 3600 + mins * 60 + s + ms / 100.0
                    prog = 90.0 + min(9.9, (curr_sec / total_duration) * 10.0)
                    progress_callback(f"Rendering: {curr_sec:.1f}s / {total_duration:.1f}s", prog)

            process.wait()
            if process.returncode != 0:
                full_log = "".join(stderr_lines)
                logger.error(f"FFmpeg process error exit ({process.returncode}): {full_log}")
                return False
            return True
        except Exception as e:
            logger.error(f"FFmpeg execution failed: {e}")
            return False
