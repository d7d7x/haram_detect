import sys
import subprocess
import logging
from pathlib import Path
from typing import Optional
from autocensor.core.dictionary import CensorshipDictionary
from autocensor.core.media_processor import MediaProcessor
from autocensor.utils.stremio_utils import find_external_player

logger = logging.getLogger(__name__)

def handle_stremio_stream(stream_input: str, player_path: Optional[str] = None):
    """
    Handle Stremio external player invocation.
    Processes stream/video file, applies censorship, and launches VLC/MPV.
    """
    logger.info(f"Stremio Proxy invoked with stream: {stream_input}")

    target_path = Path(stream_input)
    
    if not target_path.exists():
        logger.error(f"Stream input file not found: {stream_input}")
        sys.exit(1)

    dictionary = CensorshipDictionary()
    processor = MediaProcessor(dictionary)

    logger.info("Processing Stremio stream with AutoCensor AI...")
    try:
        result = processor.process(
            video_path=target_path,
            progress_callback=lambda pct, txt: logger.info(f"[Stremio Proxy {int(pct*100)}%] {txt}")
        )
        censored_video = result["output_video"]
        censored_sub = result.get("output_subtitle")

        # Find media player
        player = Path(player_path) if player_path else find_external_player()

        if player and player.exists():
            cmd = [str(player), censored_video]
            if censored_sub and Path(censored_sub).exists():
                cmd.extend(["--sub-file", str(censored_sub)])
            
            logger.info(f"Launching external player: {' '.join(cmd)}")
            subprocess.Popen(cmd)
        else:
            # Fallback to system default player
            logger.info(f"Opening censored video with system default player: {censored_video}")
            if sys.platform == "win32":
                os.startfile(censored_video)
            else:
                subprocess.Popen(["xdg-open", censored_video])

    except Exception as e:
        logger.error(f"Stremio proxy processing error: {e}")
        sys.exit(1)
