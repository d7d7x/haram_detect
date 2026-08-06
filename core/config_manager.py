import json
from pathlib import Path
from typing import List
from core.models import AppSettings, TermList, SanitizationAction, SegmentExpansionMode
from utils.paths import get_config_dir
from utils.logging import logger

class ConfigManager:
    def __init__(self):
        self.config_dir = get_config_dir()
        self.settings_file = self.config_dir / "default_settings.json"
        self.terms_file = self.config_dir / "default_terms.json"
        self.settings = self.load_settings()
        self.term_lists = self.load_terms()

    def load_settings(self) -> AppSettings:
        if not self.settings_file.exists():
            logger.warning(f"Settings file {self.settings_file} not found. Using defaults.")
            return AppSettings()
        try:
            with open(self.settings_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            data["default_action"] = SanitizationAction(data.get("default_action", "black_mute"))
            data["expansion_mode"] = SegmentExpansionMode(data.get("expansion_mode", "word"))
            return AppSettings(**data)
        except Exception as e:
            logger.error(f"Error loading settings: {e}. Falling back to default settings.")
            return AppSettings()

    def save_settings(self, settings: AppSettings) -> bool:
        self.settings = settings
        try:
            data = settings.__dict__.copy()
            data["default_action"] = data["default_action"].value
            data["expansion_mode"] = data["expansion_mode"].value
            with open(self.settings_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            logger.info("Settings saved successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to save settings: {e}")
            return False

    def load_terms(self) -> List[TermList]:
        if not self.terms_file.exists():
            logger.warning(f"Terms file {self.terms_file} not found. Returning empty term lists.")
            return []
        try:
            with open(self.terms_file, "r", encoding="utf-8") as f:
                data = json.load(f)
            terms = []
            for item in data.get("term_lists", []):
                item["action"] = SanitizationAction(item.get("action", "black_mute"))
                terms.append(TermList(**item))
            return terms
        except Exception as e:
            logger.error(f"Error loading terms: {e}")
            return []

    def save_terms(self, term_lists: List[TermList]) -> bool:
        self.term_lists = term_lists
        try:
            serialized = []
            for t in term_lists:
                item = t.__dict__.copy()
                item["action"] = item["action"].value
                serialized.append(item)
            with open(self.terms_file, "w", encoding="utf-8") as f:
                json.dump({"term_lists": serialized}, f, indent=2)
            logger.info("Terms saved successfully.")
            return True
        except Exception as e:
            logger.error(f"Failed to save terms: {e}")
            return False
