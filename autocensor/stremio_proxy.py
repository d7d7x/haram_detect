import os
import sys
import time
import uuid
import logging
import subprocess
from pathlib import Path
from typing import Optional, List, Tuple
from autocensor.config import TEMP_DIR
from autocensor.core.dictionary import CensorshipDictionary
from autocensor.core.subtitle_engine import SubtitleEngine
from autocensor.core.mpv_ipc_controller import MPVIPCController
from autocensor.utils.stremio_utils import (
    find_mpv_executable,
    find_external_player,
    locate_subtitle_candidates_in_cache,
    extract_embedded_subtitles
)

logger = logging.getLogger(__name__)

def handle_stremio_stream(
    stream_input: str,
    player_path: Optional[str] = None,
    borderless: bool = True,
    fullscreen: bool = False
):
    """
    Stremio External Player Proxy handler.
    Launches MPV with JSON IPC, extracts/cleans subtitles (deleting forbidden terms),
    injects cleaned subtitles, and mutes audio via IPC at forbidden timestamp intervals.
    """
    logger.info(f"AutoCensor MPV IPC Proxy invoked with stream: {stream_input}")

    # Locate MPV executable
    mpv_exe = Path(player_path) if player_path else find_mpv_executable()
    if not mpv_exe or not mpv_exe.exists():
        # Fallback to general external player lookup
        mpv_exe = find_external_player()

    if not mpv_exe or not mpv_exe.exists():
        logger.error("MPV player executable not found. Please install MPV or configure its path in settings.")
        sys.exit(1)

    # Initialize dictionary & subtitle engine
    dictionary = CensorshipDictionary()
    sub_engine = SubtitleEngine(dictionary)

    # Resolve subtitle candidates
    target_path = Path(stream_input) if os.path.exists(stream_input) else None
    found_sub: Optional[Path] = None

    if target_path:
        # Check if external subtitle file exists alongside video
        for ext in [".srt", ".vtt", ".ass"]:
            candidate = target_path.with_suffix(ext)
            if candidate.exists():
                found_sub = candidate
                break

        # Check for embedded subtitle track
        if not found_sub and target_path.suffix.lower() in [".mp4", ".mkv", ".avi", ".mov"]:
            found_sub = extract_embedded_subtitles(target_path, TEMP_DIR)

    # If still not found, search Stremio cache folder
    if not found_sub:
        cache_subs = locate_subtitle_candidates_in_cache()
        if cache_subs:
            found_sub = cache_subs[0]
            logger.info(f"Found subtitle candidate in Stremio cache: {found_sub.name}")

    mute_intervals: List[Tuple[float, float]] = []
    cleaned_sub_path: Optional[Path] = None

    if found_sub and found_sub.exists():
        logger.info(f"Processing subtitle for censorship: {found_sub.name}")
        cleaned_sub_path = TEMP_DIR / f"cleaned_{uuid.uuid4().hex[:8]}_{found_sub.name}"
        detections, mute_intervals = sub_engine.process_subtitles(found_sub, cleaned_sub_path)
        logger.info(f"Subtitle cleaned: {len(detections)} forbidden term event(s) removed. Cleaned sub -> {cleaned_sub_path.name}")
    else:
        logger.warning("No subtitle candidate found for stream. Playing without subtitle modification.")

    # Unique IPC Pipe Name
    pipe_name = f"autocensor_mpv_{uuid.uuid4().hex[:8]}"

    cmd = [
        str(mpv_exe),
        stream_input,
        f"--input-ipc-server=\\\\.\\pipe\\{pipe_name}",
        "--no-terminal",
        "--keep-open=no"
    ]

    if borderless:
        cmd.append("--no-border")
    if fullscreen:
        cmd.append("--fullscreen")

    logger.info(f"Launching MPV process: {' '.join(cmd)}")
    proc = subprocess.Popen(cmd)

    # Connect MPV IPC Controller
    ipc = MPVIPCController(pipe_name=pipe_name)
    connected = ipc.connect(timeout=12.0)

    if not connected:
        logger.error("Could not establish IPC connection with MPV process.")
        if proc.poll() is None:
            proc.wait()
        return

    # Load cleaned subtitle if available
    if cleaned_sub_path and cleaned_sub_path.exists():
        time.sleep(0.3)  # Brief wait for MPV engine init
        ipc.load_subtitle(str(cleaned_sub_path))

    # Monitor playback time and manage audio muting
    logger.info(f"Playback monitor active. {len(mute_intervals)} mute interval(s) scheduled.")
    is_currently_muted = False

    try:
        while proc.poll() is None and ipc.is_connected():
            # Query playback position
            time_pos = ipc.get_time_pos()

            if time_pos is not None:
                # Check if time_pos falls within any forbidden mute interval
                in_forbidden_zone = any(start <= time_pos <= end for start, end in mute_intervals)

                if in_forbidden_zone and not is_currently_muted:
                    ipc.mute(True)
                    is_currently_muted = True
                    logger.debug(f"🔇 [IPC MUTE ON] at {time_pos:.2f}s")

                elif not in_forbidden_zone and is_currently_muted:
                    ipc.mute(False)
                    is_currently_muted = False
                    logger.debug(f"🔊 [IPC MUTE OFF] at {time_pos:.2f}s")

            time.sleep(0.04)  # 25Hz poll frequency

    except Exception as e:
        logger.error(f"Playback monitor exception: {e}")

    finally:
        # Cleanup
        ipc.close()
        if proc.poll() is None:
            try:
                proc.terminate()
            except Exception:
                pass

        if cleaned_sub_path and cleaned_sub_path.exists():
            try:
                os.remove(cleaned_sub_path)
            except Exception:
                pass

        logger.info("AutoCensor MPV Proxy session ended cleanly.")

if __name__ == "__main__":
    if len(sys.argv) > 1:
        handle_stremio_stream(sys.argv[1])
