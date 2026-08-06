import re
import unicodedata
import uuid
from typing import List, Optional
from core.models import (
    TermList,
    TranscriptSegment,
    SanitizationSegment,
    SanitizationAction,
    WordTimestamp
)
from utils.logging import logger

try:
    from rapidfuzz import fuzz
    HAS_RAPIDFUZZ = True
except ImportError:
    HAS_RAPIDFUZZ = False

class TermMatcher:
    def __init__(
        self,
        term_lists: List[TermList],
        diacritic_folding: bool = True,
        fuzzy_enabled: bool = False,
        fuzzy_threshold: float = 85.0
    ):
        self.term_lists = term_lists
        self.diacritic_folding = diacritic_folding
        self.fuzzy_enabled = fuzzy_enabled and HAS_RAPIDFUZZ
        self.fuzzy_threshold = fuzzy_threshold

# Protected Arabic/English common words that must never trigger false positive matches on short terms like 'إله' or 'رب'
PROTECTED_WORDS = {
    "الله", "إلى", "له", "ربما", "عربي", "عرب", "حرب", "قريب", "شرب", "إلهام", "إليها", "إلهي"
}

class TermMatcher:
    def __init__(
        self,
        term_lists: List[TermList],
        diacritic_folding: bool = True,
        fuzzy_enabled: bool = False,
        fuzzy_threshold: float = 85.0
    ):
        self.term_lists = term_lists
        self.diacritic_folding = diacritic_folding
        self.fuzzy_enabled = fuzzy_enabled and HAS_RAPIDFUZZ
        self.fuzzy_threshold = fuzzy_threshold

    def remove_diacritics(self, text: str) -> str:
        """Strips accents and Arabic Tashkeel diacritics while preserving core Arabic letters (Hamzas)."""
        if not self.diacritic_folding:
            return text

        # Strip Arabic Tashkeel (Harakat), Tatweel, and Dagger Alef
        text = re.sub(r'[\u064B-\u0652\u0653-\u065F\u0670\u0640]', '', text)

        # For non-Arabic accents (e.g. French/Spanish diacritics), normalize safely without decomposing Arabic Hamzas
        res = []
        for c in text:
            if 0x0600 <= ord(c) <= 0x06FF:
                res.append(c)
            else:
                norm = unicodedata.normalize('NFD', c)
                res.append("".join([ch for ch in norm if unicodedata.category(ch) != 'Mn']))
        return "".join(res)

    def _is_word_boundary_match(self, pattern: str, text: str) -> bool:
        """Robust Unicode & Arabic word boundary match check."""
        regex_pattern = rf"(?:^|[^\w\u0600-\u06FF]){re.escape(pattern)}(?:$|[^\w\u0600-\u06FF])"
        return bool(re.search(regex_pattern, text, re.IGNORECASE))

    def find_matches(self, transcript_segments: List[TranscriptSegment]) -> List[SanitizationSegment]:
        """Scans transcript segments against enabled term lists and yields sanitization segments."""
        raw_matches: List[SanitizationSegment] = []

        for seg in transcript_segments:
            # Check word-level timestamps first if available
            words_to_check = seg.words if seg.words else [
                WordTimestamp(word=w, start=seg.start, end=seg.end)
                for w in seg.text.split()
            ]

            for w_obj in words_to_check:
                word_raw = w_obj.word.strip(" .,!?:;\"'()[]{}«»\u060C\u061B\u061F")
                if not word_raw:
                    continue

                word_clean = self.remove_diacritics(word_raw.lower())

                for t_list in self.term_lists:
                    if not t_list.enabled:
                        continue

                    for pattern in t_list.patterns:
                        matched = False
                        confidence = 1.0

                        pattern_clean = self.remove_diacritics(pattern.lower().strip())
                        if not pattern_clean:
                            continue

                        # Check protected word safety (e.g. 'الله' or 'إلى' must not match 'إله')
                        if word_clean in PROTECTED_WORDS and pattern_clean != word_clean:
                            continue

                        if t_list.is_regex:
                            try:
                                if re.search(pattern_clean, word_clean, re.IGNORECASE):
                                    matched = True
                            except re.error as e:
                                logger.error(f"Invalid regex pattern '{pattern}': {e}")
                        else:
                            is_short = len(pattern_clean) <= 4

                            if word_clean == pattern_clean or self._is_word_boundary_match(pattern_clean, word_clean):
                                matched = True
                            elif self.fuzzy_enabled and not is_short:
                                # ONLY apply fuzzy matching to terms longer than 4 characters
                                ratio = fuzz.ratio(pattern_clean, word_clean)
                                if ratio >= self.fuzzy_threshold:
                                    matched = True
                                    confidence = ratio / 100.0

                        if matched:
                            san_seg = SanitizationSegment(
                                id=str(uuid.uuid4())[:8],
                                start=w_obj.start,
                                end=w_obj.end,
                                action=t_list.action,
                                matched_term=pattern,
                                matched_text=w_obj.word,
                                term_list_id=t_list.id,
                                enabled=True,
                                confidence=confidence
                            )
                            raw_matches.append(san_seg)

        return raw_matches

