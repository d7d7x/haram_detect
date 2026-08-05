import re
from pathlib import Path

# Arabic Tashkeel Regex Pattern
TASHKEEL_PATTERN = re.compile(r'[\u0617-\u061A\u064B-\u0652]')
TATWEEL_PATTERN = re.compile(r'\u0640')

def strip_tashkeel(text: str) -> str:
    """Strip Arabic vocalization diacritics (tashkeel)."""
    if not text:
        return ""
    text = TASHKEEL_PATTERN.sub('', text)
    text = TATWEEL_PATTERN.sub('', text)
    return text

def normalize_arabic(text: str) -> str:
    """Normalize Arabic text (unify Alefs, Teh Marbuta, Yeh, and strip diacritics)."""
    if not text:
        return ""
    text = strip_tashkeel(text)
    # Unify Alef
    text = re.sub(r'[أإآA-Za-z0-9]', lambda m: 'ا' if m.group(0) in 'أإآ' else m.group(0), text)
    # Unify Teh Marbuta -> Heh
    text = text.replace('ة', 'ه')
    # Unify Alef Maksura -> Yeh
    text = text.replace('ى', 'ي')
    return text

def seconds_to_srt_time(seconds: float) -> str:
    """Convert float seconds to SRT time format (HH:MM:SS,mmm)."""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        secs += 1
        millis -= 1000
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{millis:03d}"

def srt_time_to_seconds(time_str: str) -> float:
    """Convert SRT time string (HH:MM:SS,mmm or HH:MM:SS.mmm) to float seconds."""
    time_str = time_str.strip().replace('.', ',')
    parts = time_str.split(':')
    if len(parts) == 3:
        hours = int(parts[0])
        minutes = int(parts[1])
        sec_milli = parts[2].split(',')
        seconds = int(sec_milli[0])
        millis = int(sec_milli[1]) if len(sec_milli) > 1 else 0
        return hours * 3600 + minutes * 60 + seconds + millis / 1000.0
    elif len(parts) == 2:
        minutes = int(parts[0])
        sec_milli = parts[1].split(',')
        seconds = int(sec_milli[0])
        millis = int(sec_milli[1]) if len(sec_milli) > 1 else 0
        return minutes * 60 + seconds + millis / 1000.0
    return 0.0

def sanitize_filename(name: str) -> str:
    """Sanitize filename to prevent invalid OS characters."""
    return re.sub(r'[\\/*?:"<>|]', '_', name)
