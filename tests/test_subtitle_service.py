import os
from pathlib import Path
from core.models import TranscriptSegment, WordTimestamp, SanitizationSegment, SanitizationAction
from core.subtitle_service import SubtitleService
from utils.paths import get_temp_dir

def test_export_transcript_txt():
    service = SubtitleService()
    temp_dir = get_temp_dir()
    txt_path_ar = str(temp_dir / "test_out_ar.txt")

    segments = [
        TranscriptSegment(
            start=1.5, end=4.2, text="هذا مقطع تجريبي للترانزكريبت العربي",
            words=[WordTimestamp("هذا", 1.5, 2.0), WordTimestamp("مقطع", 2.0, 4.2)]
        )
    ]
    san_segs = []

    success = service.export_transcript_to_txt(
        transcript_segments=segments,
        output_txt_path=txt_path_ar,
        sanitization_segments=san_segs,
        mode="asterisks",
        target_lang="none"
    )

    assert success is True
    assert Path(txt_path_ar).exists()

    with open(txt_path_ar, "r", encoding="utf-8") as f:
        content = f.read()

    assert "[00:00:01 -> 00:00:04]" in content
    assert "هذا مقطع تجريبي" in content
