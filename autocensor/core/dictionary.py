import json
import re
import uuid
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from autocensor.config import DEFAULT_DICTIONARY_PATH, USER_DICTIONARY_PATH
from autocensor.utils.helpers import normalize_arabic, strip_tashkeel

logger = logging.getLogger(__name__)

class CensorshipTerm:
    def __init__(
        self,
        term: str,
        language: str = "en",
        category: str = "Polytheism",
        match_type: str = "word",
        case_sensitive: bool = False,
        replacement: str = None,
        term_id: str = None
    ):
        self.id = term_id or str(uuid.uuid4())[:8]
        self.term = term.strip()
        self.language = language
        self.category = category
        self.match_type = match_type  # 'word', 'phrase', 'regex'
        self.case_sensitive = case_sensitive
        self.replacement = replacement or ("[BEEP]" if language == "en" else "(طوط)")

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "term": self.term,
            "language": self.language,
            "category": self.category,
            "match_type": self.match_type,
            "case_sensitive": self.case_sensitive,
            "replacement": self.replacement
        }

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "CensorshipTerm":
        return cls(
            term=d.get("term", ""),
            language=d.get("language", "en"),
            category=d.get("category", "General"),
            match_type=d.get("match_type", "word"),
            case_sensitive=d.get("case_sensitive", False),
            replacement=d.get("replacement"),
            term_id=d.get("id")
        )

class CensorshipDictionary:
    def __init__(self, dict_path: Path = None):
        self.dict_path = dict_path or (USER_DICTIONARY_PATH if USER_DICTIONARY_PATH.exists() else DEFAULT_DICTIONARY_PATH)
        self.terms: List[CensorshipTerm] = []
        self.load()

    def load(self):
        """Load dictionary terms from JSON file."""
        target_file = self.dict_path
        if not target_file.exists():
            target_file = DEFAULT_DICTIONARY_PATH

        if not target_file.exists():
            logger.warning("No dictionary file found. Initializing empty dictionary.")
            self.terms = []
            return

        try:
            with open(target_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                self.terms = [CensorshipTerm.from_dict(t) for t in data.get("terms", [])]
            logger.info(f"Loaded {len(self.terms)} censorship terms from {target_file.name}")
        except Exception as e:
            logger.error(f"Failed to load dictionary: {e}")
            self.terms = []

    def save(self, target_path: Path = None):
        """Save terms to JSON file."""
        save_path = target_path or USER_DICTIONARY_PATH
        save_path.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0",
            "default_replacement_ar": "(طوط)",
            "default_replacement_en": "[BEEP]",
            "terms": [t.to_dict() for t in self.terms]
        }
        try:
            with open(save_path, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
            self.dict_path = save_path
            logger.info(f"Saved {len(self.terms)} terms to {save_path}")
            return True
        except Exception as e:
            logger.error(f"Failed to save dictionary: {e}")
            return False

    def add_term(self, term: CensorshipTerm) -> bool:
        """Add a new censorship term."""
        if any(t.term.lower() == term.term.lower() and t.language == term.language for t in self.terms):
            logger.info(f"Term '{term.term}' already exists.")
            return False
        self.terms.append(term)
        return True

    def remove_term(self, term_id: str) -> bool:
        """Remove a term by ID."""
        initial_len = len(self.terms)
        self.terms = [t for t in self.terms if t.id != term_id]
        return len(self.terms) < initial_len

    def get_terms(self, category: str = None) -> List[CensorshipTerm]:
        """Get terms, optionally filtered by category."""
        if category and category != "All":
            return [t for t in self.terms if t.category == category]
        return list(self.terms)

    def find_matches(self, text: str) -> List[Dict[str, Any]]:
        """
        Scan input text for prohibited terms.
        Returns list of match dicts: { start, end, matched_text, term_obj, replacement }
        """
        if not text or not self.terms:
            return []

        matches = []
        normalized_text = normalize_arabic(text)

        for term_obj in self.terms:
            pattern_str = term_obj.term
            if not pattern_str:
                continue

            flags = 0 if term_obj.case_sensitive else re.IGNORECASE

            if term_obj.language == "ar":
                # Normalize target term for robust Arabic matching
                norm_pattern = normalize_arabic(pattern_str)
                # Match word boundaries or substring
                if term_obj.match_type == "word":
                    regex_pattern = r'(?:\b|\s|^)' + re.escape(norm_pattern) + r'(?:\b|\s|$)'
                else:
                    regex_pattern = re.escape(norm_pattern)

                # Search in normalized text
                for match in re.finditer(regex_pattern, normalized_text, flags):
                    start, end = match.span()
                    # Extract original text segment corresponding to match
                    matched_text = text[start:end]
                    matches.append({
                        "start": start,
                        "end": end,
                        "matched_text": matched_text,
                        "term": term_obj.term,
                        "category": term_obj.category,
                        "replacement": term_obj.replacement
                    })
            else:
                # English / Latin matching
                if term_obj.match_type == "word":
                    regex_pattern = r'\b' + re.escape(pattern_str) + r'\b'
                else:
                    regex_pattern = re.escape(pattern_str)

                for match in re.finditer(regex_pattern, text, flags):
                    start, end = match.span()
                    matches.append({
                        "start": start,
                        "end": end,
                        "matched_text": text[start:end],
                        "term": term_obj.term,
                        "category": term_obj.category,
                        "replacement": term_obj.replacement
                    })

        # Sort matches by start position
        matches.sort(key=lambda x: x["start"])
        return matches
