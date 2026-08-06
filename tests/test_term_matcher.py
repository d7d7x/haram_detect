import pytest
from core.models import TermList, SanitizationAction, TranscriptSegment, WordTimestamp
from core.term_matcher import TermMatcher

def test_regex_term_matching():
    term_list = TermList(
        id="deity",
        name="Deity Terms",
        enabled=True,
        action=SanitizationAction.BLACK_MUTE,
        patterns=[r"\bgod\b", r"\bgods\b"],
        is_regex=True
    )
    matcher = TermMatcher([term_list])

    segment = TranscriptSegment(
        start=1.0, end=4.0, text="Oh god, goodbye godzilla!",
        words=[
            WordTimestamp("Oh", 1.0, 1.2),
            WordTimestamp("god", 1.3, 1.8),
            WordTimestamp("goodbye", 2.0, 2.5),
            WordTimestamp("godzilla", 2.6, 3.2)
        ]
    )

    matches = matcher.find_matches([segment])
    assert len(matches) == 1
    assert matches[0].matched_text == "god"
    assert matches[0].start == 1.3
    assert matches[0].end == 1.8

def test_diacritic_folding():
    term_list = TermList(
        id="deity",
        name="Deity Terms",
        enabled=True,
        action=SanitizationAction.BLACK_MUTE,
        patterns=["god"],
        is_regex=False
    )
    matcher = TermMatcher([term_list], diacritic_folding=True)

    segment = TranscriptSegment(
        start=0.0, end=2.0, text="gód",
        words=[WordTimestamp("gód", 0.5, 1.0)]
    )

    matches = matcher.find_matches([segment])
    assert len(matches) == 1
    assert matches[0].matched_text == "gód"

def test_arabic_term_matching_precision():
    term_list = TermList(
        id="deity_ar",
        name="Arabic Deity Terms",
        enabled=True,
        action=SanitizationAction.BLACK_MUTE,
        patterns=["إله", "رب"],
        is_regex=False
    )
    matcher = TermMatcher([term_list], diacritic_folding=True, fuzzy_enabled=True, fuzzy_threshold=85.0)

    # Segment with valid forbidden term 'إله' and common safe words 'الله', 'إلى', 'ربما', 'عربي'
    segment = TranscriptSegment(
        start=0.0, end=10.0, text="سبحان الله ذهبت إلى المكان وقال كلمة إله وكلمة ربما واللغة العربية",
        words=[
            WordTimestamp("سبحان", 0.0, 1.0),
            WordTimestamp("الله", 1.0, 2.0),     # PROTECTED: Must NOT match 'إله'
            WordTimestamp("ذهبت", 2.0, 3.0),
            WordTimestamp("إلى", 3.0, 4.0),      # PROTECTED: Must NOT match 'إله'
            WordTimestamp("المكان", 4.0, 5.0),
            WordTimestamp("وقال", 5.0, 6.0),
            WordTimestamp("كلمة", 6.0, 7.0),
            WordTimestamp("إله", 7.0, 8.0),      # FORBIDDEN: MUST MATCH
            WordTimestamp("وكلمة", 8.0, 8.5),
            WordTimestamp("ربما", 8.5, 9.0),     # PROTECTED: Must NOT match 'رب'
            WordTimestamp("العربية", 9.0, 10.0)  # SAFE: Must NOT match 'رب'
        ]
    )

    matches = matcher.find_matches([segment])
    assert len(matches) == 1
    assert matches[0].matched_text == "إله"
    assert matches[0].matched_term == "إله"

