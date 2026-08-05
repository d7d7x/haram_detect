import time
import threading
import logging
from pathlib import Path
from typing import Callable, Optional, Set
from autocensor.config import VIDEO_EXTENSIONS, SUBTITLE_EXTENSIONS

logger = logging.getLogger(__name__)

# Check if watchdog is installed
try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
    HAS_WATCHDOG = True
except ImportError:
    HAS_WATCHDOG = False

class WatcherService:
    def __init__(self, watch_dir: Path, callback: Callable[[Path], None]):
        self.watch_dir = Path(watch_dir)
        self.callback = callback
        self.is_running = False
        self._observer = None
        self._thread = None
        self.processed_files: Set[Path] = set()

    def start(self):
        """Start watching folder."""
        if self.is_running:
            return

        if not self.watch_dir.exists():
            logger.error(f"Watch directory {self.watch_dir} does not exist.")
            return

        self.is_running = True
        logger.info(f"Watcher Service started on: {self.watch_dir}")

        if HAS_WATCHDOG:
            self._start_watchdog()
        else:
            self._start_polling()

    def stop(self):
        """Stop watching folder."""
        if not self.is_running:
            return
        self.is_running = False

        if self._observer:
            try:
                self._observer.stop()
                self._observer.join()
            except Exception:
                pass
            self._observer = None

        logger.info("Watcher Service stopped.")

    def _start_watchdog(self):
        service_self = self

        class MediaEventHandler(FileSystemEventHandler):
            def on_created(self, event):
                if event.is_directory:
                    return
                p = Path(event.src_path)
                if p.suffix.lower() in VIDEO_EXTENSIONS or p.suffix.lower() in SUBTITLE_EXTENSIONS:
                    service_self._on_new_media(p)

            def on_modified(self, event):
                if event.is_directory:
                    return
                p = Path(event.src_path)
                if p.suffix.lower() in SUBTITLE_EXTENSIONS:
                    service_self._on_new_media(p)

        self._observer = Observer()
        handler = MediaEventHandler()
        self._observer.schedule(handler, str(self.watch_dir), recursive=True)
        self._observer.start()

    def _start_polling(self):
        def poll_loop():
            logger.info("Watchdog not installed. Running background polling loop.")
            while self.is_running:
                try:
                    for item in self.watch_dir.rglob("*"):
                        if item.is_file() and (item.suffix.lower() in VIDEO_EXTENSIONS or item.suffix.lower() in SUBTITLE_EXTENSIONS):
                            if item not in self.processed_files:
                                self._on_new_media(item)
                except Exception as e:
                    logger.error(f"Polling loop error: {e}")
                time.sleep(2)

        self._thread = threading.Thread(target=poll_loop, daemon=True)
        self._thread.start()

    def _on_new_media(self, file_path: Path):
        """Handle new media file detection with debouncing for copy completion."""
        if file_path in self.processed_files or "_censored" in file_path.name.lower():
            return

        self.processed_files.add(file_path)
        logger.info(f"New video detected: {file_path.name}. Waiting for file write to complete...")

        # Wait for file size stabilization (debounce)
        def wait_and_trigger():
            last_size = -1
            stable_count = 0
            while stable_count < 3 and self.is_running:
                time.sleep(1.5)
                try:
                    current_size = file_path.stat().st_size
                    if current_size > 0 and current_size == last_size:
                        stable_count += 1
                    else:
                        last_size = current_size
                        stable_count = 0
                except Exception:
                    break

            if self.is_running and file_path.exists():
                logger.info(f"File write completed. Triggering censorship pipeline for {file_path.name}")
                self.callback(file_path)

        threading.Thread(target=wait_and_trigger, daemon=True).start()
