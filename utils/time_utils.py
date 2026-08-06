def seconds_to_timestamp(seconds: float) -> str:
    """Converts seconds (float) to HH:MM:SS.mmm string representation."""
    if seconds < 0:
        seconds = 0.0
    hrs = int(seconds // 3600)
    mins = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    millis = int(round((seconds - int(seconds)) * 1000))
    if millis >= 1000:
        secs += 1
        millis -= 1000
    return f"{hrs:02d}:{mins:02d}:{secs:02d}.{millis:03d}"

def timestamp_to_seconds(ts: str) -> float:
    """Converts HH:MM:SS.mmm or MM:SS.mmm timestamp to seconds float."""
    ts = ts.strip().replace(',', '.')
    parts = ts.split(':')
    if len(parts) == 3:
        h, m, s = parts
        return float(h) * 3600 + float(m) * 60 + float(s)
    elif len(parts) == 2:
        m, s = parts
        return float(m) * 60 + float(s)
    elif len(parts) == 1:
        return float(parts[0])
    return 0.0

def seconds_to_srt_time(seconds: float) -> str:
    """Converts seconds to SRT time format HH:MM:SS,mmm."""
    ts = seconds_to_timestamp(seconds)
    return ts.replace('.', ',')
