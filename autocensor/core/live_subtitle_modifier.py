import re
import time
import logging
from pathlib import Path
from typing import Set, Optional
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

    def extract_and_clean_embedded_subtitle(self, video_path: Path) -> Optional[Path]:
        """
        Extract embedded subtitle track from Stremio video file using FFmpeg,
        clean prohibited terms ('God', 'إله', etc.), and save alongside video as .srt.
        """
        if not video_path.exists():
            return None

        out_srt = video_path.with_suffix(".srt")
        import subprocess
        cmd = [
            "ffmpeg", "-y",
            "-i", str(video_path),
            "-map", "0:s:0?",
            "-c:s", "srt",
            str(out_srt)
        ]
        try:
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            if out_srt.exists() and out_srt.stat().st_size > 0:
                logger.info(f"Extracted embedded subtitle for {video_path.name} -> {out_srt.name}")
                self.process_subtitle_in_place(out_srt)
                return out_srt
        except Exception as e:
            logger.debug(f"Subtitle extraction notice: {e}")
        return None
