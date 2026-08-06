from typing import List, Optional, Callable
from core.models import AppSettings, TranscriptSegment, WordTimestamp
from utils.logging import logger

class TranscriptionService:
    def __init__(self, settings: AppSettings):
        self.settings = settings

    def transcribe(self, audio_wav_path: str, progress_callback: Optional[Callable[[str, float], None]] = None) -> List[TranscriptSegment]:
        """Transcribes 16kHz mono audio using faster-whisper with word-level timestamps."""
        logger.info(f"Starting transcription with model '{self.settings.whisper_model}', device '{self.settings.device}'.")
        if progress_callback:
            progress_callback("Loading Whisper Model...", 10.0)

        try:
            from faster_whisper import WhisperModel
        except ImportError:
            logger.error("faster-whisper is not installed. Please install faster-whisper.")
            raise RuntimeError("faster-whisper module not found. Install requirements.")

        device = self.settings.device
        if device == "auto":
            try:
                import torch
                device = "cuda" if torch.cuda.is_available() else "cpu"
            except Exception:
                device = "cpu"

        compute_type = "float16" if device == "cuda" else "int8"
        if self.settings.compute_type != "default":
            compute_type = self.settings.compute_type

        import os
        cpu_threads = os.cpu_count() or 4
        logger.info(f"Initializing WhisperModel on {device} ({compute_type}) using {cpu_threads} CPU threads...")
        model = WhisperModel(
            self.settings.whisper_model,
            device=device,
            compute_type=compute_type,
            cpu_threads=cpu_threads
        )

        lang = None if self.settings.language == "auto" else self.settings.language

        if progress_callback:
            progress_callback("Transcribing Audio...", 30.0)

        task = getattr(self.settings, "whisper_task", "transcribe")
        logger.info(f"Running Whisper task '{task}' with language '{lang}'")

        transcribe_kwargs = {
            "language": lang,
            "task": task,
            "word_timestamps": True,
            "beam_size": 5,
            "condition_on_previous_text": False,
            "no_speech_threshold": 0.6,
            "hallucination_silence_threshold": 2.0,
        }

        if lang == "ar":
            transcribe_kwargs["initial_prompt"] = "التفريغ الصوتي الفصيح باللغة العربية بدقة عالية بدون تكرار."

        segments_raw, info = model.transcribe(
            audio_wav_path,
            **transcribe_kwargs
        )

        logger.info(f"Detected language: {info.language} (probability: {info.language_probability:.2f})")

        transcript_segments: List[TranscriptSegment] = []
        total_duration = info.duration if info.duration > 0 else 1.0

        for segment in segments_raw:
            words: List[WordTimestamp] = []
            if segment.words:
                for w in segment.words:
                    words.append(WordTimestamp(
                        word=w.word,
                        start=w.start,
                        end=w.end,
                        probability=w.probability
                    ))
            
            t_seg = TranscriptSegment(
                start=segment.start,
                end=segment.end,
                text=segment.text.strip(),
                words=words
            )
            transcript_segments.append(t_seg)

            if progress_callback and total_duration > 0:
                prog = 30.0 + (segment.end / total_duration) * 60.0
                progress_callback(f"Transcribing: {segment.end:.1f}s / {total_duration:.1f}s", min(prog, 90.0))

        if progress_callback:
            progress_callback("Transcription completed.", 100.0)

        return transcript_segments
