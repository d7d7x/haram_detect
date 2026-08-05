import re
import time
import logging
from pathlib import Path
from typing import Set
from autocensor.core.dictionary import CensorshipDictionary
from autocensor.core.subtitle_engine import SubtitleEngine

logger = logging.getLogger(__name__)

class LiveSubtitleModifier:
    def __init__(self, dictionary: CensorshipDictionary):
        self.dictionary = dictionary
        self.sub_engine = SubtitleEngine(dictionary)
        self.modified_files: Set[Path] = set()

    def process_subtitle_in_place(self, sub_path: Path) -> bool:
        """
        Directly modify a subtitle file in-place in Stremio's cache folder.
        Overwrites prohibited terms ('God', 'إله', etc.) so Stremio displays clean subtitles instantly.
        """
        if not sub_path.exists() or sub_path.stat().st_size == 0:
            return False

        try:
            # Read content
            content = sub_path.read_text(encoding="utf-8", errors="replace")
            matches = self.dictionary.find_matches(content)

            if not matches:
                return False

            logger.info(f"In-Place Subtitle Modifier: Found {len(matches)} prohibited terms in {sub_path.name}")

            # Apply replacements in-place
            modified_content = content
            for m in sorted(matches, key=lambda x: x["start"], reverse=True):
                start = m["start"]
                end = m["end"]
                rep = m["replacement"]
                if rep in ["", "[REMOVE]"]:
                    modified_content = modified_content[:start] + modified_content[end:]
                    modified_content = re.sub(r'[ \t]+', ' ', modified_content)
                else:
                    modified_content = modified_content[:start] + rep + modified_content[end:]

            # Write back in-place
            sub_path.write_text(modified_content, encoding="utf-8")
            self.modified_files.add(sub_path)
            logger.info(f"In-place subtitle updated successfully: {sub_path.name}")
            return True

        except Exception as e:
            logger.error(f"Error modifying subtitle in-place ({sub_path.name}): {e}")
            return False
