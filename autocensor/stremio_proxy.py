import os
import sys
import logging
from pathlib import Path
from typing import Optional
from autocensor.core.dictionary import CensorshipDictionary
from autocensor.core.media_processor import MediaProcessor
from autocensor.core.live_subtitle_modifier import LiveSubtitleModifier

logger = logging.getLogger(__name__)

def handle_stremio_stream(stream_input: str):
    """
    Handle Stremio stream or subtitle file processing directly in-place within Stremio's cache folder.
    Deletes forbidden terms from subtitles so Stremio's built-in player displays clean subtitles.
    """
    logger.info(f"Stremio Proxy invoked with input: {stream_input}")

    dictionary = CensorshipDictionary()
    sub_modifier = LiveSubtitleModifier(dictionary)

    target_path = Path(stream_input) if os.path.exists(stream_input) else None

    if target_path and target_path.exists():
        if target_path.suffix.lower() in [".srt", ".vtt", ".ass"]:
            success = sub_modifier.process_subtitle_in_place(target_path)
            if success:
                logger.info(f"Cleaned subtitle in-place for Stremio: {target_path.name}")
        elif target_path.suffix.lower() in [".mp4", ".mkv", ".avi", ".mov"]:
            sub_modifier.extract_and_clean_embedded_subtitle(target_path)
            processor = MediaProcessor(dictionary)
            processor.process(video_path=target_path)
    else:
        logger.info(f"Stremio Proxy active for stream: {stream_input}")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        handle_stremio_stream(sys.argv[1])
