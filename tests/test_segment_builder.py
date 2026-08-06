import pytest
from core.models import AppSettings, SanitizationSegment, SanitizationAction, SegmentExpansionMode
from core.segment_builder import SegmentBuilder

def test_segment_padding_and_merging():
    settings = AppSettings(
        pre_padding_sec=0.15,
        post_padding_sec=0.35,
        min_segment_duration_sec=1.0,
        merge_threshold_sec=0.75,
        expansion_mode=SegmentExpansionMode.WORD
    )
    builder = SegmentBuilder(settings)

    raw_matches = [
        SanitizationSegment("1", start=10.0, end=10.5, action=SanitizationAction.BLACK_MUTE, matched_term="god", matched_text="god", term_list_id="deity"),
        SanitizationSegment("2", start=10.9, end=11.2, action=SanitizationAction.BLACK_MUTE, matched_term="idol", matched_text="idol", term_list_id="poly")
    ]

    segments = builder.build_segments(raw_matches, [], total_duration=100.0)
    
    # Matches should be merged because 10.5 + 0.35 = 10.85, and 10.9 - 0.15 = 10.75 (overlap)
    assert len(segments) == 1
    assert segments[0].start == pytest.approx(9.85, abs=0.05)
    assert segments[0].end == pytest.approx(11.65, abs=0.05)
