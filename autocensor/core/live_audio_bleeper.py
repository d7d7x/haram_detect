import sys
import time
import threading
import logging
from typing import List, Tuple

logger = logging.getLogger(__name__)

# Check for Windows winsound
if sys.platform == "win32":
    import winsound
    HAS_WINSOUND = True
else:
    HAS_WINSOUND = False

class LiveAudioBleeper:
    def __init__(self, frequency: int = 1000):
        self.frequency = frequency

    def play_beep(self, duration_ms: int = 500):
        """Play 1kHz (طوط) sound effect instantly over system audio."""
        def _beep():
            try:
                if HAS_WINSOUND:
                    winsound.Beep(self.frequency, duration_ms)
                else:
                    print('\a')  # Terminal bell fallback
                logger.info(f"🔊 Live Audio Bleep played (طوط): {duration_ms}ms")
            except Exception as e:
                logger.debug(f"Audio bleep notice: {e}")

        threading.Thread(target=_beep, daemon=True).start()

    def schedule_bleeps_for_timestamps(self, timestamps: List[Tuple[float, float]], start_time_offset: float = 0.0):
        """
        Schedule real-time (طوط) audio bleeps for detected forbidden word timestamps.
        """
        current_time = time.time()
        for start_sec, end_sec in timestamps:
            delay = start_sec - start_time_offset
            duration_ms = int(max(0.3, end_sec - start_sec) * 1000)

            if delay > 0:
                timer = threading.Timer(delay, self.play_beep, args=[duration_ms])
                timer.daemon = True
                timer.start()
            else:
                self.play_beep(duration_ms)
