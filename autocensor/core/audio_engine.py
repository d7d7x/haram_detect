import wave
import struct
import math
import logging
from pathlib import Path
from typing import List, Tuple
from autocensor.config import MODE_BEEP, MODE_MUTE, DEFAULT_BEEP_FREQ, DEFAULT_AUDIO_PADDING_MS

logger = logging.getLogger(__name__)

class AudioCensorEngine:
    def __init__(self, padding_ms: int = 50, fade_ms: int = 5):
        self.padding_sec = padding_ms / 1000.0
        self.fade_sec = fade_ms / 1000.0

    def apply_audio_censorship(
        self,
        input_wav: Path,
        output_wav: Path,
        timestamps: List[Tuple[float, float]],
        mode: str = MODE_MUTE
    ) -> bool:
        """
        Apply muting/silencing on WAV audio file at specified timestamp ranges.
        Does NOT alter total track duration or cut audio frames, maintaining perfect A/V sync.
        Mode defaults to MODE_MUTE (zero amplitude PCM).
        """
        if not input_wav.exists():
            logger.error(f"Audio file {input_wav} does not exist.")
            return False

        if not timestamps or mode == "none":
            output_wav.parent.mkdir(parents=True, exist_ok=True)
            output_wav.write_bytes(input_wav.read_bytes())
            return True

        try:
            with wave.open(str(input_wav), 'rb') as wav_in:
                n_channels = wav_in.getnchannels()
                sampwidth = wav_in.getsampwidth()
                framerate = wav_in.getframerate()
                n_frames = wav_in.getnframes()
                
                raw_bytes = wav_in.readframes(n_frames)

            # Support 16-bit PCM (2 bytes per sample)
            if sampwidth != 2:
                logger.warning(f"Sample width {sampwidth} is not 16-bit PCM. Copying original audio track.")
                output_wav.parent.mkdir(parents=True, exist_ok=True)
                output_wav.write_bytes(input_wav.read_bytes())
                return True

            total_samples = len(raw_bytes) // (2 * n_channels)
            format_str = f"<{total_samples * n_channels}h"
            samples = list(struct.unpack(format_str, raw_bytes))

            # Prepare padded timestamps
            padded_timestamps = []
            for start, end in timestamps:
                start_p = max(0.0, start - self.padding_sec)
                end_p = end + self.padding_sec
                padded_timestamps.append((start_p, end_p))

            fade_frames = int(self.fade_sec * framerate)

            for start_sec, end_sec in padded_timestamps:
                start_frame = int(start_sec * framerate)
                end_frame = int(end_sec * framerate)

                start_frame = max(0, min(start_frame, total_samples))
                end_frame = max(0, min(end_frame, total_samples))

                if mode == MODE_BEEP:
                    # Optional legacy beep mode if explicitly requested
                    for frame_idx in range(start_frame, end_frame):
                        sample_time = frame_idx / float(framerate)
                        sine_val = int(16000 * math.sin(2 * math.pi * DEFAULT_BEEP_FREQ * sample_time))
                        for ch in range(n_channels):
                            idx = frame_idx * n_channels + ch
                            if 0 <= idx < len(samples):
                                samples[idx] = sine_val
                else:
                    # DEFAULT PATH: Absolute zero amplitude PCM muting
                    for frame_idx in range(start_frame, end_frame):
                        # Micro-fade in/out to prevent hardware pop clicks
                        mult = 1.0
                        if fade_frames > 0:
                            if frame_idx - start_frame < fade_frames:
                                mult = 1.0 - ((frame_idx - start_frame) / float(fade_frames))
                            elif end_frame - frame_idx < fade_frames:
                                mult = 1.0 - ((end_frame - frame_idx) / float(fade_frames))
                            else:
                                mult = 0.0
                        else:
                            mult = 0.0

                        for ch in range(n_channels):
                            idx = frame_idx * n_channels + ch
                            if 0 <= idx < len(samples):
                                samples[idx] = int(samples[idx] * mult)

            # Pack PCM samples back into WAV binary format
            packed_bytes = struct.pack(format_str, *samples)

            output_wav.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(output_wav), 'wb') as wav_out:
                wav_out.setnchannels(n_channels)
                wav_out.setsampwidth(sampwidth)
                wav_out.setframerate(framerate)
                wav_out.writeframes(packed_bytes)

            logger.info(f"Audio muted successfully for {len(timestamps)} interval(s) -> {output_wav.name}")
            return True

        except Exception as e:
            logger.error(f"Error applying audio censorship: {e}")
            return False
