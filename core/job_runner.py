import os
from pathlib import Path
from typing import List, Optional, Callable
from core.models import (
    AppSettings,
    TermList,
    MediaInfo,
    SanitizationSegment,
    TranscriptSegment,
    SanitizationAction,
    SegmentExpansionMode
)
from core.ffprobe_service import FFprobeService
from core.ffmpeg_service import FFmpegService
from core.transcription_service import TranscriptionService
from core.subtitle_service import SubtitleService
from core.term_matcher import TermMatcher
from core.segment_builder import SegmentBuilder
from core.scene_detector import SceneDetector
from core.validators import validate_segments, is_supported_video_file
from utils.logging import logger
from utils.paths import get_temp_dir

class JobRunner:
    def __init__(self, settings: AppSettings, term_lists: List[TermList]):
        self.settings = settings
        self.term_lists = term_lists
        self.ffprobe = FFprobeService(settings.ffprobe_path)
        self.ffmpeg = FFmpegService(settings)
        self.transcriber = TranscriptionService(settings)
        self.sub_service = SubtitleService()
        self.matcher = TermMatcher(
            term_lists=term_lists,
            diacritic_folding=settings.diacritic_folding,
            fuzzy_enabled=settings.fuzzy_match_enabled,
            fuzzy_threshold=settings.fuzzy_match_threshold
        )
        self.segment_builder = SegmentBuilder(settings)
        self.scene_detector = SceneDetector(settings)
        self.cancelled = False
        self.last_job_results: dict = {}

    def cancel(self):
        """Cancels active processing job."""
        self.cancelled = True

    def process_file(
        self,
        video_path: str,
        external_sub_path: Optional[str] = None,
        embedded_sub_index: Optional[int] = None,
        progress_callback: Optional[Callable[[str, float], None]] = None,
        review_callback: Optional[Callable[[List[SanitizationSegment]], List[SanitizationSegment]]] = None
    ) -> bool:
        """Runs the complete end-to-end sanitization job for a single file."""
        self.cancelled = False
        logger.info(f"Starting sanitization job for: {video_path}")

        if not is_supported_video_file(video_path):
            raise ValueError(f"Unsupported file format: {video_path}")

        if progress_callback:
            progress_callback("Probing media info...", 5.0)

        # Step 1: Probe Media
        media_info = self.ffprobe.inspect_file(video_path)
        if media_info.is_drm_protected:
            raise PermissionError("Media file is DRM protected or encrypted. Processing stopped for compliance.")

        if media_info.duration <= 0:
            raise ValueError("Unable to read valid duration from media file.")

        # Step 2: Extract Transcript / Subtitles
        transcript_segments: List[TranscriptSegment] = []

        if external_sub_path and Path(external_sub_path).exists():
            if progress_callback:
                progress_callback("Parsing external subtitles...", 15.0)
            transcript_segments = self.sub_service.parse_subtitle_file(external_sub_path)
        elif embedded_sub_index is not None and embedded_sub_index >= 0:
            if progress_callback:
                progress_callback("Extracting embedded subtitles...", 15.0)
            temp_sub = str(get_temp_dir() / "embedded_sub.srt")
            self.ffmpeg.extract_embedded_subtitles(video_path, embedded_sub_index, temp_sub)
            transcript_segments = self.sub_service.parse_subtitle_file(temp_sub)
        else:
            if progress_callback:
                progress_callback("Extracting audio...", 15.0)
            temp_wav = str(get_temp_dir() / "extracted_audio.wav")
            self.ffmpeg.extract_audio(video_path, temp_wav)

            if self.cancelled:
                return False

            def sub_prog(msg, p):
                if progress_callback:
                    progress_callback(msg, 20.0 + p * 0.4)

            transcript_segments = self.transcriber.transcribe(temp_wav, progress_callback=sub_prog)

        if self.cancelled:
            return False

        # Step 3: Match Terms
        if progress_callback:
            progress_callback("Scanning for forbidden terms...", 65.0)
        raw_matches = self.matcher.find_matches(transcript_segments)

        # Step 4: Build & Expand Segments
        if progress_callback:
            progress_callback("Building sanitization segments...", 75.0)

        segments = self.segment_builder.build_segments(raw_matches, transcript_segments, media_info.duration)

        if self.settings.expansion_mode == SegmentExpansionMode.SCENE:
            if progress_callback:
                progress_callback("Running scene boundary detection...", 80.0)
            segments = self.scene_detector.expand_segments_to_scenes(video_path, segments, media_info.duration)

        # Step 5: User Review Callback (if provided)
        if review_callback:
            if progress_callback:
                progress_callback("Awaiting user review confirmation...", 85.0)
            segments = review_callback(segments)

        # Step 6: Validate Segments
        valid, errors = validate_segments(segments, media_info.duration)
        if not valid:
            logger.error(f"Segment validation errors: {errors}")
            raise ValueError(f"Invalid segments: {'; '.join(errors)}")

        if self.cancelled:
            return False

        # Step 7: Render Media Output
        if progress_callback:
            progress_callback("Rendering sanitized media output...", 90.0)

        out_dir = Path(self.settings.output_directory) if self.settings.output_directory else Path(video_path).parent
        out_dir.mkdir(parents=True, exist_ok=True)
        output_filename = f"{Path(video_path).stem}_sanitized{Path(video_path).suffix}"
        output_path = str(out_dir / output_filename)

        has_cut = any(s.enabled and s.action == SanitizationAction.CUT for s in segments)

        if has_cut:
            success = self.ffmpeg.render_cut_mode(video_path, output_path, segments, media_info.duration, progress_callback)
        else:
            success = self.ffmpeg.render_black_mute(video_path, output_path, segments, media_info.duration, progress_callback)

        if not success:
            raise RuntimeError("FFmpeg rendering failed.")

        # Step 8: Generate Both Arabic & English Redacted Subtitle and Text Transcripts
        out_sub_ar = str(out_dir / f"{Path(video_path).stem}_sanitized_ar.srt")
        out_sub_en = str(out_dir / f"{Path(video_path).stem}_sanitized_en.srt")
        out_txt_ar = str(out_dir / f"{Path(video_path).stem}_transcript_ar.txt")
        out_txt_en = str(out_dir / f"{Path(video_path).stem}_transcript_en.txt")

        # Determine target languages for transcript export
        src_lang = self.settings.language if self.settings.language != "auto" else "ar"

        if external_sub_path and Path(external_sub_path).exists():
            self.sub_service.redact_subtitles(
                external_sub_path, out_sub_ar, segments,
                mode=self.settings.subtitle_redaction_mode, target_lang="ar"
            )
            self.sub_service.redact_subtitles(
                external_sub_path, out_sub_en, segments,
                mode=self.settings.subtitle_redaction_mode, target_lang="en"
            )
        elif transcript_segments:
            ar_target = "none" if src_lang == "ar" else "ar"
            en_target = "none" if src_lang == "en" else "en"

            # Export SRT Subtitle Files
            self.sub_service.export_transcript_to_srt(
                transcript_segments, out_sub_ar, segments,
                mode=self.settings.subtitle_redaction_mode, target_lang=ar_target
            )
            self.sub_service.export_transcript_to_srt(
                transcript_segments, out_sub_en, segments,
                mode=self.settings.subtitle_redaction_mode, target_lang=en_target
            )

            # Export Human-Readable TXT Transcript Files
            self.sub_service.export_transcript_to_txt(
                transcript_segments, out_txt_ar, segments,
                mode=self.settings.subtitle_redaction_mode, target_lang=ar_target
            )
            self.sub_service.export_transcript_to_txt(
                transcript_segments, out_txt_en, segments,
                mode=self.settings.subtitle_redaction_mode, target_lang=en_target
            )

        # Mux BOTH Arabic and English subtitle tracks directly inside output video container
        if progress_callback:
            progress_callback("Muxing embedded Arabic & English subtitle tracks into video...", 98.0)
        self.ffmpeg.embed_subtitles_into_video(video_path=output_path, ar_sub_path=out_sub_ar, en_sub_path=out_sub_en, output_path=output_path)

        self.last_job_results = {
            "output_video": output_path,
            "transcript_ar_txt": out_txt_ar,
            "transcript_en_txt": out_txt_en,
            "sub_ar_srt": out_sub_ar,
            "sub_en_srt": out_sub_en
        }

        if progress_callback:
            progress_callback(f"Sanitization complete! Saved to {output_path}", 100.0)

        return True
