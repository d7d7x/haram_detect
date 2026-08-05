import os
import logging
from pathlib import Path
from typing import Callable, Optional, Dict, Any, List, Tuple
from autocensor.config import TEMP_DIR, MODE_BEEP, MODE_MUTE, SUBTITLE_EXTENSIONS
from autocensor.core.dictionary import CensorshipDictionary
from autocensor.core.subtitle_engine import SubtitleEngine
from autocensor.core.audio_engine import AudioCensorEngine
from autocensor.core.stt_engine import SpeechToTextEngine
from autocensor.utils.ffmpeg_utils import extract_audio, remux_video_and_audio, is_ffmpeg_available
from autocensor.utils.stremio_utils import extract_embedded_subtitles, locate_subtitle_candidates_in_cache

logger = logging.getLogger(__name__)

class MediaProcessor:
    def __init__(self, dictionary: CensorshipDictionary):
        self.dictionary = dictionary
        self.sub_engine = SubtitleEngine(dictionary)
        self.audio_engine = AudioCensorEngine()
        self.stt_engine = SpeechToTextEngine()

    def process(
        self,
        video_path: Path,
        output_video_path: Optional[Path] = None,
        subtitle_path: Optional[Path] = None,
        mode: str = MODE_MUTE,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Full end-to-end censorship pipeline:
        1. Subtitle & STT Detection (Deletion of forbidden terms)
        2. Audio Extraction
        3. Audio Censorship (Zero PCM muting)
        4. FFmpeg Video Re-muxing (-c:v copy)
        """
        def update_progress(pct: float, text: str):
            logger.info(f"[{int(pct * 100)}%] {text}")
            if progress_callback:
                progress_callback(pct, text)

        update_progress(0.05, "Validating environment and input files...")

        if not video_path.exists():
            raise FileNotFoundError(f"Video file not found: {video_path}")

        if not is_ffmpeg_available():
            raise RuntimeError("FFmpeg is not installed or not in PATH. Please install FFmpeg.")

        if output_video_path is None:
            clean_stem = "".join([c if c.isalnum() or c in " ._-" else "_" for c in video_path.stem])
            ext = video_path.suffix.lower() if video_path.suffix else ".mp4"
            if "stremio-cache" in str(video_path).lower():
                out_dir = Path.home() / "Downloads"
            else:
                out_dir = video_path.parent
            out_dir.mkdir(parents=True, exist_ok=True)
            output_video_path = out_dir / f"{clean_stem}_Censored{ext}"

        output_sub_path = output_video_path.with_suffix(".srt")

        # Step 1: Subtitle resolution
        update_progress(0.15, "Searching for subtitles...")
        found_sub_path = subtitle_path

        # Check sidecar files next to video
        if not found_sub_path:
            for ext in SUBTITLE_EXTENSIONS:
                candidate = video_path.with_suffix(ext)
                if candidate.exists():
                    found_sub_path = candidate
                    break

        # Check Stremio cache for subtitle candidates
        if not found_sub_path:
            cache_subs = locate_subtitle_candidates_in_cache()
            if cache_subs:
                found_sub_path = cache_subs[0]
                update_progress(0.20, f"Found subtitle candidate in Stremio cache: {found_sub_path.name}")

        # Attempt extracting embedded subtitles from video container
        if not found_sub_path:
            update_progress(0.22, "Extracting embedded subtitle track via FFmpeg...")
            extracted_sub = extract_embedded_subtitles(video_path, output_dir=TEMP_DIR)
            if extracted_sub and extracted_sub.exists():
                found_sub_path = extracted_sub
                update_progress(0.25, f"Extracted embedded subtitle track: {found_sub_path.name}")

        detections = []
        mute_timestamps: List[Tuple[float, float]] = []

        if found_sub_path and found_sub_path.exists():
            update_progress(0.30, f"Processing subtitle file: {found_sub_path.name}")
            detections, mute_timestamps = self.sub_engine.process_subtitles(
                input_sub=found_sub_path,
                output_sub=output_sub_path
            )
        else:
            update_progress(0.25, "No subtitle file found. Attempting AI transcription...")
            if self.stt_engine.is_available():
                temp_audio_stt = TEMP_DIR / f"temp_stt_{video_path.stem}.wav"
                extract_audio(video_path, temp_audio_stt)
                
                stt_segments = self.stt_engine.transcribe(temp_audio_stt)
                
                for seg in stt_segments:
                    matches = self.dictionary.find_matches(seg["text"])
                    if matches:
                        mute_timestamps.append((seg["start"], seg["end"]))
                        detections.append({
                            "start_sec": seg["start"],
                            "end_sec": seg["end"],
                            "original": seg["text"],
                            "censored": "[MUTED AUDIO]",
                            "matched_terms": [m["term"] for m in matches]
                        })
                
                if temp_audio_stt.exists():
                    try:
                        os.remove(temp_audio_stt)
                    except Exception:
                        pass
            else:
                update_progress(0.35, "Note: No subtitle file found and STT engine not active.")

        update_progress(0.50, f"Detected {len(detections)} censorship trigger event(s).")

        # Step 2: Extract audio stream using FFmpeg
        update_progress(0.60, "Extracting audio track via FFmpeg...")
        temp_audio_in = TEMP_DIR / f"raw_{video_path.stem}.wav"
        temp_audio_out = TEMP_DIR / f"censored_{video_path.stem}.wav"

        success = extract_audio(video_path, temp_audio_in)
        if not success:
            raise RuntimeError("Failed to extract audio stream from video.")

        # Step 3: Apply Audio Muting
        update_progress(0.75, f"Applying audio muting (Mode: {mode.upper()})...")
        self.audio_engine.apply_audio_censorship(
            input_wav=temp_audio_in,
            output_wav=temp_audio_out,
            timestamps=mute_timestamps,
            mode=mode
        )

        # Step 4: Re-mux video and audio into output video
        update_progress(0.90, "Re-muxing video and audio tracks (Fast stream copy)...")
        remux_success, err_msg = remux_video_and_audio(
            input_video=video_path,
            input_audio=temp_audio_out,
            output_video=output_video_path,
            subtitle_file=output_sub_path if output_sub_path.exists() else None
        )

        if not remux_success:
            # Check if alternative MKV file was created
            alt_mkv = output_video_path.with_suffix(".mkv")
            if alt_mkv.exists() and alt_mkv.stat().st_size > 0:
                output_video_path = alt_mkv
                remux_success = True
            else:
                raise RuntimeError(f"Failed to re-mux output video: {err_msg}")

        in_place_sub = video_path.with_suffix(".srt")
        if output_sub_path.exists() and output_sub_path != in_place_sub:
            try:
                in_place_sub.write_text(output_sub_path.read_text(encoding="utf-8"), encoding="utf-8")
                logger.info(f"In-place subtitle created for auto-loading: {in_place_sub}")
            except Exception as e:
                logger.debug(f"In-place subtitle write notice: {e}")

        # Cleanup temporary WAV files
        for tmp in [temp_audio_in, temp_audio_out]:
            if tmp.exists():
                try:
                    os.remove(tmp)
                except Exception:
                    pass

        if not remux_success:
            raise RuntimeError("Failed to re-mux output video.")

        update_progress(1.0, f"Processing complete! Saved to {output_video_path.name}")

        return {
            "input_video": str(video_path),
            "output_video": str(output_video_path),
            "output_subtitle": str(output_sub_path) if output_sub_path.exists() else None,
            "in_place_subtitle": str(in_place_sub) if in_place_sub.exists() else None,
            "detections_count": len(detections),
            "detections": detections
        }
