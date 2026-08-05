import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
from autocensor.config import DEFAULT_STT_MODEL

logger = logging.getLogger(__name__)

# Check for faster-whisper
try:
    from faster_whisper import WhisperModel
    HAS_FASTER_WHISPER = True
except ImportError:
    HAS_FASTER_WHISPER = False

# Check for openai-whisper fallback
try:
    import whisper
    HAS_OPENAI_WHISPER = True
except ImportError:
    HAS_OPENAI_WHISPER = False

class SpeechToTextEngine:
    def __init__(self, model_name: str = DEFAULT_STT_MODEL, device: str = "auto"):
        self.model_name = model_name
        self.device = device
        self._model = None

    def is_available(self) -> bool:
        """Check if any STT engine (faster-whisper or openai-whisper) is installed."""
        return HAS_FASTER_WHISPER or HAS_OPENAI_WHISPER

    def load_model(self):
        """Lazy load the Whisper model."""
        if self._model is not None:
            return

        if HAS_FASTER_WHISPER:
            logger.info(f"Loading faster-whisper model '{self.model_name}'...")
            device_choice = "cuda" if self.device == "cuda" else "cpu"
            try:
                self._model = WhisperModel(self.model_name, device=device_choice, compute_type="int8")
                return
            except Exception as e:
                logger.warning(f"Failed to load faster-whisper on {device_choice}, falling back to CPU: {e}")
                self._model = WhisperModel(self.model_name, device="cpu", compute_type="int8")
                return

        if HAS_OPENAI_WHISPER:
            logger.info(f"Loading openai-whisper model '{self.model_name}'...")
            self._model = whisper.load_model(self.model_name)
            return

        logger.warning("No Speech-to-Text library (faster-whisper / openai-whisper) installed.")

    def transcribe(self, audio_path: Path) -> List[Dict[str, Any]]:
        """
        Transcribe audio file and extract word-level timestamps.
        Returns list of segment items:
        [
           {
               "start": float,
               "end": float,
               "text": str,
               "words": [ {"word": str, "start": float, "end": float}, ... ]
           }
        ]
        """
        if not audio_path.exists():
            logger.error(f"Audio file {audio_path} not found.")
            return []

        if not self.is_available():
            logger.warning("STT Engine not available. Please install faster-whisper (`pip install faster-whisper`).")
            return []

        self.load_model()
        results = []

        try:
            if HAS_FASTER_WHISPER and isinstance(self._model, WhisperModel):
                segments, info = self._model.transcribe(str(audio_path), word_timestamps=True)
                for segment in segments:
                    seg_dict = {
                        "start": segment.start,
                        "end": segment.end,
                        "text": segment.text,
                        "words": []
                    }
                    if segment.words:
                        for w in segment.words:
                            seg_dict["words"].append({
                                "word": w.word,
                                "start": w.start,
                                "end": w.end
                            })
                    results.append(seg_dict)
                return results

            elif HAS_OPENAI_WHISPER:
                res = self._model.transcribe(str(audio_path), word_timestamps=True)
                for seg in res.get("segments", []):
                    seg_dict = {
                        "start": seg["start"],
                        "end": seg["end"],
                        "text": seg["text"],
                        "words": []
                    }
                    for w in seg.get("words", []):
                        seg_dict["words"].append({
                            "word": w["word"],
                            "start": w["start"],
                            "end": w["end"]
                        })
                    results.append(seg_dict)
                return results

        except Exception as e:
            logger.error(f"Error during AI transcription: {e}")

        return []
