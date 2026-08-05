import wave
import struct
import math
import logging
from pathlib import Path
from typing import List, Tuple
from autocensor.config import MODE_BEEP, MODE_MUTE, DEFAULT_BEEP_FREQ, DEFAULT_AUDIO_PADDING_MS

logger = logging.getLogger(__name__)

class AudioCensorEngine:
    def __init__(self, beep_freq: int = DEFAULT_BEEP_FREQ, padding_ms: int = DEFAULT_AUDIO_PADDING_MS):
        self.beep_freq = beep_freq
        self.padding_sec = padding_ms / 1000.0

    def apply_audio_censorship(
        self,
        input_wav: Path,
        output_wav: Path,
        timestamps: List[Tuple[float, float]],
        mode: str = MODE_BEEP
    ) -> bool:
        """
        Apply BEEP tone overlay or muting on input WAV audio file at given timestamp ranges.
        """
        if not input_wav.exists():
            logger.error(f"Audio file {input_wav} does not exist.")
            return False

        if not timestamps or mode == "none":
            # Just copy file if no censorship required
            output_wav.write_bytes(input_wav.read_bytes())
            return True

        try:
            with wave.open(str(input_wav), 'rb') as wav_in:
                n_channels = wav_in.getnchannels()
                sampwidth = wav_in.getsampwidth()
                framerate = wav_in.getframerate()
                n_frames = wav_in.getnframes()
                
                raw_bytes = wav_in.readframes(n_frames)

            # Support 16-bit PCM (standard 2 bytes per sample)
            if sampwidth != 2:
                logger.warning(f"Unsupported sample width {sampwidth}. Copying original audio.")
                output_wav.write_bytes(input_wav.read_bytes())
                return True

            total_samples = len(raw_bytes) // (2 * n_channels)
            # Unpack 16-bit samples
            format_str = f"<{total_samples * n_channels}h"
            samples = list(struct.unpack(format_str, raw_bytes))

            # Apply padding to timestamps
            padded_timestamps = []
            for start, end in timestamps:
                start_p = max(0.0, start - self.padding_sec)
                end_p = end + self.padding_sec
                padded_timestamps.append((start_p, end_p))

            # Process samples for each timestamp range
            for start_sec, end_sec in padded_timestamps:
                start_frame = int(start_sec * framerate)
                end_frame = int(end_sec * framerate)

                start_frame = max(0, min(start_frame, total_samples))
                end_frame = max(0, min(end_frame, total_samples))

                for frame_idx in range(start_frame, end_frame):
                    sample_time = frame_idx / float(framerate)
                    
                    if mode == MODE_BEEP:
                        # Generate 1kHz sine wave sample (amplitude ~ 16000 for 16-bit PCM)
                        sine_val = int(16000 * math.sin(2 * math.pi * self.beep_freq * sample_time))
                    else:  # MODE_MUTE
                        sine_val = 0

                    for ch in range(n_channels):
                        idx = frame_idx * n_channels + ch
                        if 0 <= idx < len(samples):
                            samples[idx] = sine_val

            # Pack back into PCM 16-bit audio
            packed_bytes = struct.pack(format_str, *samples)

            output_wav.parent.mkdir(parents=True, exist_ok=True)
            with wave.open(str(output_wav), 'wb') as wav_out:
                wav_out.setnchannels(n_channels)
                wav_out.setsampwidth(sampwidth)
                wav_out.setframerate(framerate)
                wav_out.writeframes(packed_bytes)

            logger.info(f"Successfully censored audio ({len(timestamps)} segments) -> {output_wav.name}")
            return True

        except Exception as e:
            logger.error(f"Error applying audio censorship: {e}")
            return False
