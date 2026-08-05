import re
import logging
from pathlib import Path
from typing import List, Dict, Any, Tuple
from autocensor.core.dictionary import CensorshipDictionary
from autocensor.utils.helpers import srt_time_to_seconds, seconds_to_srt_time

logger = logging.getLogger(__name__)

# Check if pysubs2 is installed
try:
    import pysubs2
    HAS_PYSUBS2 = True
except ImportError:
    HAS_PYSUBS2 = False

class SubtitleItem:
    def __init__(self, index: int, start_sec: float, end_sec: float, text: str):
        self.index = index
        self.start_sec = start_sec
        self.end_sec = end_sec
        self.text = text

class SubtitleEngine:
    def __init__(self, dictionary: CensorshipDictionary):
        self.dictionary = dictionary

    def parse_subtitle(self, subtitle_path: Path) -> List[SubtitleItem]:
        """Parse subtitle file into list of SubtitleItem objects."""
        items: List[SubtitleItem] = []
        if not subtitle_path.exists():
            return items

        if HAS_PYSUBS2:
            try:
                subs = pysubs2.load(str(subtitle_path), encoding="utf-8")
                for idx, event in enumerate(subs):
                    if event.is_comment:
                        continue
                    items.append(SubtitleItem(
                        index=idx + 1,
                        start_sec=event.start / 1000.0,
                        end_sec=event.end / 1000.0,
                        text=event.text
                    ))
                return items
            except Exception as e:
                logger.warning(f"pysubs2 parsing failed ({e}), falling back to built-in parser.")

        # Built-in fallback SRT/VTT parser
        try:
            content = subtitle_path.read_text(encoding="utf-8", errors="replace")
            # Normalize newlines
            content = content.replace("\r\n", "\n")
            blocks = re.split(r'\n\n+', content)

            idx = 1
            for block in blocks:
                lines = [l.strip() for l in block.split('\n') if l.strip()]
                if not lines:
                    continue
                
                # Check for timestamp line
                time_line_idx = -1
                for i, line in enumerate(lines):
                    if "-->" in line:
                        time_line_idx = i
                        break
                
                if time_line_idx != -1:
                    times = lines[time_line_idx].split("-->")
                    start_sec = srt_time_to_seconds(times[0].strip())
                    end_sec = srt_time_to_seconds(times[1].strip().split()[0])
                    text = "\n".join(lines[time_line_idx + 1:])
                    items.append(SubtitleItem(index=idx, start_sec=start_sec, end_sec=end_sec, text=text))
                    idx += 1
        except Exception as e:
            logger.error(f"Failed to parse subtitle with built-in parser: {e}")

        return items

    def process_subtitles(
        self,
        input_sub: Path,
        output_sub: Path
    ) -> Tuple[List[Dict[str, Any]], List[Tuple[float, float]]]:
        """
        Censor subtitle file.
        Returns:
          - Detections log: [{ start_time, end_time, original, censored, term, replacement }, ...]
          - Audio Bleep Timestamps: [(start_sec, end_sec), ...]
        """
        items = self.parse_subtitle(input_sub)
        detections = []
        bleep_timestamps = []
        censored_items = []

        for item in items:
            matches = self.dictionary.find_matches(item.text)
            if matches:
                censored_text = item.text
                # Sort matches in reverse to replace without index shifting
                for m in sorted(matches, key=lambda x: x["start"], reverse=True):
                    start = m["start"]
                    end = m["end"]
                    replacement = m["replacement"]
                    censored_text = censored_text[:start] + replacement + censored_text[end:]

                detections.append({
                    "start_sec": item.start_sec,
                    "end_sec": item.end_sec,
                    "start_str": seconds_to_srt_time(item.start_sec),
                    "end_str": seconds_to_srt_time(item.end_sec),
                    "original": item.text,
                    "censored": censored_text,
                    "matched_terms": [m["term"] for m in matches]
                })

                # Calculate word-level estimate or full event timestamp for audio bleeping
                bleep_timestamps.append((item.start_sec, item.end_sec))
                censored_items.append(SubtitleItem(item.index, item.start_sec, item.end_sec, censored_text))
            else:
                censored_items.append(item)

        # Write output subtitle file
        self.write_subtitle(censored_items, output_sub)

        return detections, bleep_timestamps

    def write_subtitle(self, items: List[SubtitleItem], output_path: Path):
        """Write SubtitleItem list to output SRT file."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        lines = []
        for i, item in enumerate(items, 1):
            start_str = seconds_to_srt_time(item.start_sec)
            end_str = seconds_to_srt_time(item.end_sec)
            lines.append(f"{i}\n{start_str} --> {end_str}\n{item.text}\n")

        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Cleaned subtitle saved to {output_path}")
