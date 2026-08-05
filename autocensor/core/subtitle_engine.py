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


def clean_censored_text(text: str) -> str:
    """
    Clean text after forbidden word deletion:
    - Removes extra spaces
    - Fixes orphan/broken punctuation (e.g. hanging commas, periods)
    - Fixes orphan Arabic conjunctions (standalone 'و' or 'ف')
    - Strips empty lines and leading/trailing punctuation
    """
    if not text:
        return ""

    # Replace multiple spaces/tabs with a single space
    cleaned = re.sub(r'[ \t]+', ' ', text)

    # Remove spaces before punctuation
    cleaned = re.sub(r' +([,\.\!\?\;\:\،\؟])', r'\1', cleaned)

    # Deduplicate repeated punctuation caused by deletion (e.g. ",," -> ",", ".." -> ".")
    cleaned = re.sub(r'([,\.\!\?\;\:\،\؟])\1+', r'\1', cleaned)

    # Clean empty brackets/parentheses
    cleaned = re.sub(r'\(\s*\)', '', cleaned)
    cleaned = re.sub(r'\[\s*\]', '', cleaned)
    cleaned = re.sub(r'\{\s*\}', '', cleaned)

    # Clean orphan Arabic conjunctions ('و' or 'ف' left stranded at line start or before punctuation)
    cleaned = re.sub(r'(^|\n)\s*[وف]\s+([,\.\!\?\;\:\،\؟]|\s|$)', r'\1', cleaned)
    cleaned = re.sub(r'(^|\n)\s*[وف]\s+', r'\1', cleaned)
    cleaned = re.sub(r'\s+[وف]\s*([,\.\!\?\;\:\،\؟]|$)', r'\1', cleaned)

    # Clean isolated punctuation lines or trailing whitespace
    lines = []
    for line in cleaned.split('\n'):
        l_strip = line.strip()
        # If line contains only punctuation, clear it
        if re.match(r'^[,\.\:\;\!\?\،\؟\s\-]+$', l_strip):
            continue
        lines.append(l_strip)

    result = "\n".join([l for l in lines if l]).strip()
    return result


def is_cue_empty(text: str) -> bool:
    """
    Check if a subtitle cue is effectively empty after deletion.
    Strips subtitle markup tags (e.g. <i>, <b>, {\an8}) to see if visible text remains.
    """
    if not text or not text.strip():
        return True

    # Strip HTML-style formatting tags
    stripped = re.sub(r'<[^>]+>', '', text)
    # Strip ASS/SSA style override blocks {...}
    stripped = re.sub(r'\{[^}]+\}', '', stripped)
    # Strip punctuation and spaces
    stripped = re.sub(r'[\s\d\W_]+', '', stripped, flags=re.UNICODE)

    return len(stripped) == 0


def merge_overlapping_intervals(intervals: List[Tuple[float, float]]) -> List[Tuple[float, float]]:
    """
    Merge overlapping or adjacent timestamp intervals [(start, end), ...].
    """
    if not intervals:
        return []

    # Sort by start time
    sorted_intervals = sorted(intervals, key=lambda x: x[0])
    merged = [sorted_intervals[0]]

    for current in sorted_intervals[1:]:
        prev_start, prev_end = merged[-1]
        curr_start, curr_end = current

        if curr_start <= prev_end + 0.05:  # Overlapping or within 50ms
            merged[-1] = (prev_start, max(prev_end, curr_end))
        else:
            merged.append(current)

    return merged


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
            content = content.replace("\r\n", "\n")
            blocks = re.split(r'\n\n+', content)

            idx = 1
            for block in blocks:
                lines = [l.strip() for l in block.split('\n') if l.strip()]
                if not lines:
                    continue
                
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
        Censor subtitle file by DELETING forbidden terms (no placeholders).
        Drops empty subtitle cues.
        Returns:
          - Detections log list
          - Merged audio muting timestamp intervals [(start_sec, end_sec), ...]
        """
        items = self.parse_subtitle(input_sub)
        detections = []
        raw_mute_timestamps = []
        censored_items = []

        new_index = 1
        for item in items:
            matches = self.dictionary.find_matches(item.text)
            if matches:
                # Absolute deletion of forbidden word - no [BEEP] or (طوط)
                censored_text = item.text
                for m in sorted(matches, key=lambda x: x["start"], reverse=True):
                    start = m["start"]
                    end = m["end"]
                    censored_text = censored_text[:start] + censored_text[end:]

                # Post-deletion cleanup
                cleaned_text = clean_censored_text(censored_text)

                detections.append({
                    "start_sec": item.start_sec,
                    "end_sec": item.end_sec,
                    "start_str": seconds_to_srt_time(item.start_sec),
                    "end_str": seconds_to_srt_time(item.end_sec),
                    "original": item.text,
                    "censored": cleaned_text,
                    "matched_terms": [m["term"] for m in matches]
                })

                raw_mute_timestamps.append((item.start_sec, item.end_sec))

                # Drop cue if it becomes empty after deletion
                if not is_cue_empty(cleaned_text):
                    censored_items.append(SubtitleItem(new_index, item.start_sec, item.end_sec, cleaned_text))
                    new_index += 1
                else:
                    logger.info(f"Dropped empty subtitle cue #{item.index} ({seconds_to_srt_time(item.start_sec)}) after term deletion.")
            else:
                if not is_cue_empty(item.text):
                    censored_items.append(SubtitleItem(new_index, item.start_sec, item.end_sec, item.text))
                    new_index += 1

        # Write cleaned subtitle file
        self.write_subtitle(censored_items, output_sub)

        # Merge overlapping audio mute intervals
        merged_mute_intervals = merge_overlapping_intervals(raw_mute_timestamps)

        return detections, merged_mute_intervals

    def write_subtitle(self, items: List[SubtitleItem], output_path: Path):
        """Write SubtitleItem list to output subtitle file (SRT format)."""
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if HAS_PYSUBS2 and output_path.suffix.lower() in [".ass", ".vtt", ".ssa"]:
            try:
                subs = pysubs2.SSAFile()
                for item in items:
                    event = pysubs2.SSAEvent(
                        start=int(item.start_sec * 1000),
                        end=int(item.end_sec * 1000),
                        text=item.text
                    )
                    subs.append(event)
                subs.save(str(output_path), encoding="utf-8")
                logger.info(f"Cleaned subtitle saved ({output_path.suffix}) -> {output_path}")
                return
            except Exception as e:
                logger.warning(f"pysubs2 save failed ({e}), using default SRT format.")

        lines = []
        for i, item in enumerate(items, 1):
            start_str = seconds_to_srt_time(item.start_sec)
            end_str = seconds_to_srt_time(item.end_sec)
            lines.append(f"{i}\n{start_str} --> {end_str}\n{item.text}\n")

        output_path.write_text("\n".join(lines), encoding="utf-8")
        logger.info(f"Cleaned subtitle saved to {output_path}")
