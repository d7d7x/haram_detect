from typing import List
from core.models import TranscriptSegment, WordTimestamp
from utils.logging import logger

class AlignmentService:
    """Service to refine and stabilize word-level timestamps when missing or imprecise."""

    def interpolate_word_timestamps(self, segments: List[TranscriptSegment]) -> List[TranscriptSegment]:
        """Interpolates linear word timestamps for segments missing explicit word-level times."""
        refined_segments = []

        for seg in segments:
            if seg.words:
                refined_segments.append(seg)
                continue

            words_str = seg.text.split()
            if not words_str:
                refined_segments.append(seg)
                continue

            seg_duration = seg.end - seg.start
            word_duration = seg_duration / len(words_str)

            interpolated_words = []
            for i, w_text in enumerate(words_str):
                w_start = seg.start + (i * word_duration)
                w_end = w_start + word_duration
                interpolated_words.append(WordTimestamp(
                    word=w_text,
                    start=round(w_start, 3),
                    end=round(w_end, 3),
                    probability=0.75  # Lower confidence indicator for fallback interpolation
                ))

            refined_segments.append(TranscriptSegment(
                start=seg.start,
                end=seg.end,
                text=seg.text,
                words=interpolated_words
            ))

        return refined_segments
