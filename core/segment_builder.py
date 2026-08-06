from typing import List
from core.models import (
    SanitizationSegment,
    TranscriptSegment,
    SegmentExpansionMode,
    SanitizationAction,
    AppSettings
)
from utils.logging import logger

class SegmentBuilder:
    def __init__(self, settings: AppSettings):
        self.settings = settings

    def build_segments(
        self,
        raw_matches: List[SanitizationSegment],
        transcript_segments: List[TranscriptSegment],
        total_duration: float
    ) -> List[SanitizationSegment]:
        """Expands raw matched segments according to mode, applies padding, min duration, and merges overlaps."""
        if not raw_matches:
            return []

        expanded_segments: List[SanitizationSegment] = []

        for match in raw_matches:
            start = match.start
            end = match.end

            if self.settings.expansion_mode == SegmentExpansionMode.UTTERANCE:
                # Find encompassing transcript segment line
                for t_seg in transcript_segments:
                    if t_seg.start <= match.start and t_seg.end >= match.end:
                        start = t_seg.start
                        end = t_seg.end
                        break

            # Apply pre and post padding
            start -= self.settings.pre_padding_sec
            end += self.settings.post_padding_sec

            # Enforce minimum segment duration
            duration = end - start
            if duration < self.settings.min_segment_duration_sec:
                diff = self.settings.min_segment_duration_sec - duration
                start -= diff / 2.0
                end += diff / 2.0

            # Clamp boundaries to video length
            start = max(0.0, start)
            end = min(total_duration, end)

            new_seg = SanitizationSegment(
                id=match.id,
                start=round(start, 3),
                end=round(end, 3),
                action=match.action,
                matched_term=match.matched_term,
                matched_text=match.matched_text,
                term_list_id=match.term_list_id,
                enabled=match.enabled,
                manual_override=match.manual_override,
                confidence=match.confidence
            )
            expanded_segments.append(new_seg)

        # Merge overlapping or close adjacent segments
        merged_segments = self.merge_segments(expanded_segments)
        return merged_segments

    def merge_segments(self, segments: List[SanitizationSegment]) -> List[SanitizationSegment]:
        """Merges overlapping or adjacent segments within merge_threshold_sec."""
        if not segments:
            return []

        sorted_segs = sorted(segments, key=lambda x: x.start)
        merged: List[SanitizationSegment] = []

        current = sorted_segs[0]

        for next_seg in sorted_segs[1:]:
            # If segments overlap or gap is less than merge threshold
            if next_seg.start <= (current.end + self.settings.merge_threshold_sec):
                current.end = max(current.end, next_seg.end)
                current.matched_text += f"; {next_seg.matched_text}"
                current.matched_term += f"; {next_seg.matched_term}"
                # Elevate action priority if cut > black_mute > mute
                if next_seg.action == SanitizationAction.CUT:
                    current.action = SanitizationAction.CUT
            else:
                merged.append(current)
                current = next_seg

        merged.append(current)
        return merged
