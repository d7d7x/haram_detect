import pytest
from core.models import AppSettings, SanitizationSegment, SanitizationAction
from core.ffmpeg_service import FFmpegService

def test_black_mute_filter_complex_generation():
    settings = AppSettings()
    service = FFmpegService(settings)

    segments = [
        SanitizationSegment("1", start=5.0, end=7.5, action=SanitizationAction.BLACK_MUTE, matched_term="test", matched_text="test", term_list_id="1"),
        SanitizationSegment("2", start=20.0, end=22.0, action=SanitizationAction.MUTE, matched_term="mute_only", matched_text="mute_only", term_list_id="1")
    ]

    v_filter, a_filter = service.build_black_mute_filter_complex(segments)

    assert "drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,5.000,7.500)'" in v_filter
    assert "volume=0:enable='between(t,5.000,7.500)+between(t,20.000,22.000)'" in a_filter

def test_calculate_keep_intervals():
    settings = AppSettings()
    service = FFmpegService(settings)

    cut_segments = [
        SanitizationSegment("1", start=10.0, end=15.0, action=SanitizationAction.CUT, matched_term="cut1", matched_text="cut1", term_list_id="1"),
        SanitizationSegment("2", start=30.0, end=35.0, action=SanitizationAction.CUT, matched_term="cut2", matched_text="cut2", term_list_id="1")
    ]

    keeps = service.calculate_keep_intervals(cut_segments, total_duration=50.0)
    assert keeps == [(0.0, 10.0), (15.0, 30.0), (35.0, 50.0)]
