import re
import urllib.request
import urllib.parse
import json
from pathlib import Path
from typing import List, Optional
from core.models import TranscriptSegment, WordTimestamp, SanitizationSegment, SanitizationAction
from utils.logging import logger
from utils.time_utils import seconds_to_srt_time

class SubtitleService:
    def translate_text(self, text: str, target_lang: str = "ar") -> str:
        """Translates text to target language (e.g. Arabic 'ar') using free Google Translate API."""
        if not text.strip() or target_lang in ["none", ""]:
            return text
        try:
            url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=auto&tl=" + target_lang + "&dt=t&q=" + urllib.parse.quote(text)
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as res:
                data = json.loads(res.read().decode("utf-8"))
                if data and data[0]:
                    translated = "".join([part[0] for part in data[0] if part[0]])
                    return translated
        except Exception as e:
            logger.warning(f"Translation to '{target_lang}' failed: {e}")
        return text

    def parse_subtitle_file(self, filepath: str) -> List[TranscriptSegment]:
        """Parses SRT, VTT, ASS, or SSA files into TranscriptSegment structures."""
        path = Path(filepath)
        if not path.exists():
            raise FileNotFoundError(f"Subtitle file not found: {filepath}")

        segments: List[TranscriptSegment] = []

        try:
            import pysubs2
            subs = pysubs2.load(filepath)
            for event in subs:
                start_sec = event.start / 1000.0
                end_sec = event.end / 1000.0
                text = event.text.replace(r"\N", "\n").strip()
                if not text:
                    continue

                words_list = text.split()
                w_count = len(words_list)
                duration = max(0.1, end_sec - start_sec)
                w_dur = duration / max(1, w_count)

                word_timestamps = []
                for idx, w in enumerate(words_list):
                    ws = start_sec + idx * w_dur
                    we = ws + w_dur
                    word_timestamps.append(WordTimestamp(word=w, start=ws, end=we, probability=1.0))

                segments.append(TranscriptSegment(
                    start=start_sec,
                    end=end_sec,
                    text=text,
                    words=word_timestamps
                ))
            return segments
        except ImportError:
            logger.warning("pysubs2 not installed. Using internal SRT parser fallback.")
            return self._parse_srt_fallback(filepath)

    def _parse_srt_fallback(self, filepath: str) -> List[TranscriptSegment]:
        """Basic regex-based SRT parser fallback."""
        with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()

        blocks = re.split(r"\n\s*\n", content.strip())
        segments = []

        time_pattern = re.compile(r"(\d{2}):(\d{2}):(\d{2})[,.](\d{3})\s*-->\s*(\d{2}):(\d{2}):(\d{2})[,.](\d{3})")

        for block in blocks:
            lines = block.splitlines()
            if len(lines) < 2:
                continue
            time_match = None
            text_lines = []
            for line in lines:
                m = time_pattern.search(line)
                if m:
                    time_match = m
                elif not line.strip().isdigit():
                    text_lines.append(line.strip())

            if time_match and text_lines:
                h1, m1, s1, ms1, h2, m2, s2, ms2 = map(int, time_match.groups())
                start_sec = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000.0
                end_sec = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000.0
                text = " ".join(text_lines)

                words_list = text.split()
                w_dur = (end_sec - start_sec) / max(1, len(words_list))
                words = [
                    WordTimestamp(w, start_sec + i * w_dur, start_sec + (i + 1) * w_dur)
                    for i, w in enumerate(words_list)
                ]
                segments.append(TranscriptSegment(start=start_sec, end=end_sec, text=text, words=words))

        return segments

    def redact_subtitles(
        self,
        input_sub_path: str,
        output_sub_path: str,
        sanitization_segments: List[SanitizationSegment],
        mode: str = "asterisks",
        target_lang: str = "ar"
    ) -> bool:
        """Redacts or time-shifts subtitles according to active sanitization segments, with optional target translation."""
        try:
            import pysubs2
            subs = pysubs2.load(input_sub_path)
        except Exception as e:
            logger.error(f"Failed to load subtitle file for redaction: {e}")
            return False

        cut_segments = sorted([s for s in sanitization_segments if s.enabled and s.action == SanitizationAction.CUT], key=lambda x: x.start)

        new_events = []
        for event in subs:
            e_start = event.start / 1000.0
            e_end = event.end / 1000.0

            # Redact text if matching active segment
            for seg in sanitization_segments:
                if not seg.enabled:
                    continue
                if seg.start <= e_end and seg.end >= e_start:
                    if mode == "remove_line":
                        event.text = ""
                    elif mode == "asterisks":
                        pattern = re.escape(seg.matched_text or seg.matched_term)
                        event.text = re.sub(pattern, "*****", event.text, flags=re.IGNORECASE)
                    elif mode == "removed_tag":
                        pattern = re.escape(seg.matched_text or seg.matched_term)
                        event.text = re.sub(pattern, "[REMOVED]", event.text, flags=re.IGNORECASE)

            if not event.text.strip():
                continue

            # Translate to target language (e.g. Arabic 'ar')
            if target_lang and target_lang != "none":
                event.text = self.translate_text(event.text, target_lang)

            # Time-shift for CUT segments
            if cut_segments:
                shift = 0.0
                dropped = False
                for c in cut_segments:
                    if e_start >= c.end:
                        shift += (c.end - c.start)
                    elif e_start >= c.start and e_end <= c.end:
                        dropped = True
                        break
                if dropped:
                    continue
                event.start = int((e_start - shift) * 1000.0)
                event.end = int((e_end - shift) * 1000.0)

            new_events.append(event)

        subs.events = new_events
        subs.save(output_sub_path)
        logger.info(f"Saved redacted & translated subtitle file to {output_sub_path}")
        return True

    def export_transcript_to_srt(
        self,
        transcript_segments: List[TranscriptSegment],
        output_sub_path: str,
        sanitization_segments: List[SanitizationSegment],
        mode: str = "asterisks",
        target_lang: str = "ar"
    ) -> bool:
        """Exports transcript segments into a redacted and translated SRT subtitle file."""
        cut_segments = sorted([s for s in sanitization_segments if s.enabled and s.action == SanitizationAction.CUT], key=lambda x: x.start)

        srt_lines = []
        index = 1

        for t_seg in transcript_segments:
            t_start = t_seg.start
            t_end = t_seg.end
            text = t_seg.text

            # Redact matching terms
            for seg in sanitization_segments:
                if not seg.enabled:
                    continue
                if seg.start <= t_end and seg.end >= t_start:
                    pattern = re.escape(seg.matched_text or seg.matched_term)
                    if mode == "remove_line":
                        text = ""
                    elif mode == "asterisks":
                        text = re.sub(pattern, "*****", text, flags=re.IGNORECASE)
                    elif mode == "removed_tag":
                        text = re.sub(pattern, "[REMOVED]", text, flags=re.IGNORECASE)

            if not text.strip():
                continue

            # Translate line to target language (e.g. Arabic 'ar')
            if target_lang and target_lang != "none":
                text = self.translate_text(text, target_lang)

            # Time shift for cut mode
            if cut_segments:
                shift = 0.0
                dropped = False
                for c in cut_segments:
                    if t_start >= c.end:
                        shift += (c.end - c.start)
                    elif t_start >= c.start and t_end <= c.end:
                        dropped = True
                        break
                if dropped:
                    continue
                t_start -= shift
                t_end -= shift

            start_str = seconds_to_srt_time(t_start)
            end_str = seconds_to_srt_time(t_end)

            srt_lines.append(f"{index}\n{start_str} --> {end_str}\n{text.strip()}\n\n")
            index += 1

        with open(output_sub_path, "w", encoding="utf-8") as f:
            f.writelines(srt_lines)

        logger.info(f"Exported transcript to translated SRT file: {output_sub_path}")
        return True

    def export_transcript_to_txt(
        self,
        transcript_segments: List[TranscriptSegment],
        output_txt_path: str,
        sanitization_segments: List[SanitizationSegment],
        mode: str = "asterisks",
        target_lang: str = "ar"
    ) -> bool:
        """Exports transcript segments into a clean formatted text transcript (.txt)."""
        cut_segments = sorted([s for s in sanitization_segments if s.enabled and s.action == SanitizationAction.CUT], key=lambda x: x.start)

        txt_lines = []
        for t_seg in transcript_segments:
            t_start = t_seg.start
            t_end = t_seg.end
            text = t_seg.text

            # Redact matching terms
            for seg in sanitization_segments:
                if not seg.enabled:
                    continue
                if seg.start <= t_end and seg.end >= t_start:
                    pattern = re.escape(seg.matched_text or seg.matched_term)
                    if mode == "remove_line":
                        text = ""
                    elif mode == "asterisks":
                        text = re.sub(pattern, "*****", text, flags=re.IGNORECASE)
                    elif mode == "removed_tag":
                        text = re.sub(pattern, "[REMOVED]", text, flags=re.IGNORECASE)

            if not text.strip():
                continue

            # Translate line to target language (e.g. Arabic 'ar' or English 'en')
            if target_lang and target_lang != "none":
                text = self.translate_text(text, target_lang)

            # Time shift for cut mode
            if cut_segments:
                shift = 0.0
                dropped = False
                for c in cut_segments:
                    if t_start >= c.end:
                        shift += (c.end - c.start)
                    elif t_start >= c.start and t_end <= c.end:
                        dropped = True
                        break
                if dropped:
                    continue
                t_start -= shift
                t_end -= shift

            start_m, start_s = divmod(int(t_start), 60)
            start_h, start_m = divmod(start_m, 60)
            end_m, end_s = divmod(int(t_end), 60)
            end_h, end_m = divmod(end_m, 60)

            time_header = f"[{start_h:02d}:{start_m:02d}:{start_s:02d} -> {end_h:02d}:{end_m:02d}:{end_s:02d}]"
            txt_lines.append(f"{time_header} {text.strip()}\n")

        with open(output_txt_path, "w", encoding="utf-8") as f:
            f.writelines(txt_lines)

        logger.info(f"Exported transcript to TXT file: {output_txt_path}")
        return True

