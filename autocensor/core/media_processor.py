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
        mode: str = MODE_BEEP,
        progress_callback: Optional[Callable[[float, str], None]] = None
    ) -> Dict[str, Any]:
        """
        Full end-to-end censorship pipeline:
        1. Subtitle & STT Detection
        2. Audio Extraction
        3. Audio Censorship
        4. FFmpeg Video Re-muxing
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
            stem = video_path.stem
            ext = video_path.suffix
            output_video_path = video_path.parent / f"{stem}_Censored{ext}"

        output_sub_path = output_video_path.with_suffix(".srt")

        # Step 1: Subtitle resolution
        update_progress(0.15, "Searching for subtitles...")
        found_sub_path = subtitle_path

        if not found_sub_path:
            # Look for matching subtitle file in same directory
            for ext in SUBTITLE_EXTENSIONS:
                candidate = video_path.with_suffix(ext)
                if candidate.exists():
                    found_sub_path = candidate
                    break

        detections = []
        bleep_timestamps: List[Tuple[float, float]] = []

        if found_sub_path and found_sub_path.exists():
            update_progress(0.30, f"Processing subtitle file: {found_sub_path.name}")
            detections, bleep_timestamps = self.sub_engine.process_subtitles(
                input_sub=found_sub_path,
                output_sub=output_sub_path
            )
        else:
            # Run STT engine if available
            update_progress(0.25, "No subtitle file found. Attempting AI transcription...")
            if self.stt_engine.is_available():
                # First extract temp audio for STT
                temp_audio_stt = TEMP_DIR / f"temp_stt_{video_path.stem}.wav"
                extract_audio(video_path, temp_audio_stt)
                
                stt_segments = self.stt_engine.transcribe(temp_audio_stt)
                
                # Check STT word timestamps against dictionary
                for seg in stt_segments:
                    matches = self.dictionary.find_matches(seg["text"])
                    if matches:
                        bleep_timestamps.append((seg["start"], seg["end"]))
                        detections.append({
                            "start_sec": seg["start"],
                            "end_sec": seg["end"],
                            "original": seg["text"],
                            "censored": "[CENSORED AUDIO]",
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

        # Step 3: Apply Audio Bleeping / Muting
        update_progress(0.75, f"Applying audio censorship (Mode: {mode.upper()})...")
        self.audio_engine.apply_audio_censorship(
            input_wav=temp_audio_in,
            output_wav=temp_audio_out,
            timestamps=bleep_timestamps,
            mode=mode
        )

        # Step 4: Re-mux video and audio into output video
        update_progress(0.90, "Re-muxing video and audio tracks (Fast stream copy)...")
        remux_success = remux_video_and_audio(
            input_video=video_path,
            input_audio=temp_audio_out,
            output_video=output_video_path,
            subtitle_file=output_sub_path if output_sub_path.exists() else None
        )

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
            "detections_count": len(detections),
            "detections": detections
        }
