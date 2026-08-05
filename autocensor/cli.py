import sys
import argparse
import time
import logging
from pathlib import Path
from autocensor.config import MODE_BEEP, MODE_MUTE, MODE_SUBTITLE_ONLY, USER_DICTIONARY_PATH
from autocensor.core.dictionary import CensorshipDictionary
from autocensor.core.media_processor import MediaProcessor
from autocensor.core.watcher import WatcherService

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("AutoCensorCLI")

def run_cli(args_list=None):
    parser = argparse.ArgumentParser(description="AutoCensor AI - Automated Subtitle & Audio Censorship CLI")
    parser.add_argument("--input", "-i", type=str, help="Path to input video file")
    parser.add_argument("--output", "-o", type=str, help="Path to output censored video file")
    parser.add_argument("--subtitle", "-s", type=str, help="Path to subtitle file (.srt, .ass, .vtt)")
    parser.add_argument("--mode", "-m", choices=[MODE_BEEP, MODE_MUTE, MODE_SUBTITLE_ONLY], default=MODE_BEEP, help="Censorship mode")
    parser.add_argument("--watch", "-w", type=str, help="Path to folder to monitor in background Watcher Mode")
    parser.add_argument("--stremio", type=str, help="Path or URL passed from Stremio external player invocation")
    parser.add_argument("--dictionary", "-d", type=str, help="Path to custom dictionary JSON file")

    args = parser.parse_args(args_list)

    if args.stremio:
        from autocensor.stremio_proxy import handle_stremio_stream
        handle_stremio_stream(args.stremio)
        sys.exit(0)


    # Load dictionary
    dict_path = Path(args.dictionary) if args.dictionary else None
    dictionary = CensorshipDictionary(dict_path)
    processor = MediaProcessor(dictionary)

    if args.watch:
        watch_path = Path(args.watch)
        if not watch_path.exists():
            logger.error(f"Watch directory not found: {watch_path}")
            sys.exit(1)

        def on_file(file_path: Path):
            logger.info(f"Watcher triggered for: {file_path}")
            try:
                res = processor.process(
                    video_path=file_path,
                    mode=args.mode,
                    progress_callback=lambda pct, txt: logger.info(f"[{int(pct*100)}%] {txt}")
                )
                logger.info(f"Finished auto-censoring {file_path.name} -> {Path(res['output_video']).name}")
            except Exception as e:
                logger.error(f"Failed processing {file_path}: {e}")

        service = WatcherService(watch_dir=watch_path, callback=on_file)
        service.start()

        logger.info(f"Background Watcher Service active on {watch_path}. Press Ctrl+C to exit.")
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            service.stop()
            logger.info("Exiting watcher mode.")

    elif args.input:
        video_path = Path(args.input)
        if not video_path.exists():
            logger.error(f"Input video file not found: {video_path}")
            sys.exit(1)

        out_path = Path(args.output) if args.output else None
        sub_path = Path(args.subtitle) if args.subtitle else None

        try:
            res = processor.process(
                video_path=video_path,
                output_video_path=out_path,
                subtitle_path=sub_path,
                mode=args.mode,
                progress_callback=lambda pct, txt: logger.info(f"[{int(pct*100)}%] {txt}")
            )
            logger.info("=" * 60)
            logger.info(f"SUCCESS! Output saved to: {res['output_video']}")
            logger.info(f"Censored detections count: {res['detections_count']}")
            logger.info("=" * 60)
        except Exception as e:
            logger.error(f"Processing error: {e}")
            sys.exit(1)
    else:
        parser.print_help()
