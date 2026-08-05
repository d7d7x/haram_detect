# Technical Summary Report: AutoCensor AI (`haram_detect`)

**Prepared for**: Code Review & AI Technical Discussion  
**GitHub Repository**: [https://github.com/d7d7x/haram_detect.git](https://github.com/d7d7x/haram_detect.git)  
**Primary Stack**: Python 3.12+, CustomTkinter, FFmpeg, PySubS2, Watchdog, Faster-Whisper

---

## 1. Project Overview & Objective

**AutoCensor AI** is a desktop application and background automation engine designed to:
1. Ingest video files (`.mp4`, `.mkv`, `.avi`) and subtitle tracks (`.srt`, `.vtt`, `.ass`).
2. Detect polytheistic, shirk, blasphemy, and inappropriate terms in Arabic and English text subtitles and spoken audio.
3. Automatically censor detected occurrences by:
   - Overwriting or completely deleting prohibited words from subtitle tracks.
   - Synthesizing a 1kHz sine wave **`(طوط)`** BEEP tone or muting the audio track at exact timestamp intervals.
   - Re-muxing media streams using FFmpeg lossless video stream copy (`-c:v copy`).
4. Provide a background **Watcher Service** for directory monitoring (e.g. `Downloads` or Stremio cache folders).
5. Integrate with **Stremio** for automated episode processing.

---

## 2. Repository Architecture & Module Overview

```text
haram_detect/
├── autocensor/
│   ├── config.py                 # App settings, paths, defaults, styling tokens
│   ├── stremio_proxy.py          # Stremio external player proxy interceptor
│   ├── core/
│   │   ├── dictionary.py         # Terms database manager & Arabic/English NLP matcher
│   │   ├── subtitle_engine.py    # Subtitle parser, word replacer, & timestamp extractor
│   │   ├── audio_engine.py       # Audio extractor, 1kHz tone overlay & muting
│   │   ├── stt_engine.py         # AI Speech-To-Text (faster-whisper / whisper)
│   │   ├── media_processor.py    # Master end-to-end processing pipeline
│   │   ├── live_subtitle_modifier.py # Direct in-place subtitle file editor & embedded extractor
│   │   ├── live_audio_bleeper.py # Real-time (طوط) audio bleep tone player (winsound)
│   │   └── watcher.py            # Watchdog background directory watcher
│   ├── ui/
│   │   ├── main_window.py        # 1-Click CustomTkinter desktop GUI
│   │   ├── processing_tab.py     # Ingestion & progress tab
│   │   ├── dictionary_tab.py     # Terms management tab
│   │   ├── watcher_tab.py        # Background watcher controls tab
│   │   └── stremio_tab.py        # Stremio integration tab with solution selector
│   ├── utils/
│   │   ├── ffmpeg_utils.py       # FFmpeg audio extraction & remuxing helpers
│   │   ├── stremio_utils.py      # Stremio cache finder & API poller (http://127.0.0.1:11470)
│   │   └── helpers.py            # Arabic diacritics stripper, Alef normalizer, time converters
├── data/
│   ├── default_dictionary.json   # 102+ Arabic & English shirk/polytheism terms JSON database
│   ├── app_icon.png              # High-resolution 3D app icon
│   └── app_icon.ico              # Windows ICO icon file
├── main.py                       # Main application entry point (GUI / CLI)
├── Run_AutoCensor_AI.bat         # Desktop batch launcher
├── AutoCensor_Stremio_Player.bat # Stremio external player CLI wrapper
├── requirements.txt              # Dependency specification
└── README.md                     # Documentation & user guide
```

---

## 3. Core Technical Implementations

### A. NLP & Arabic Text Normalization Engine (`autocensor/core/dictionary.py`)
- **Tashkeel & Diacritics Stripping**: Strips Arabic vocalization marks (`َ`, `ً`, `ُ`, `ٌ`, `ِ`, `ٍ`, `ْ`, `ّ`, `ـ`).
- **Alef Unification**: Unifies `أ`, `إ`, `آ`, `ٱ` -> `ا`, `ة` -> `ه`, `ى` -> `ي`.
- **Arabic Prefix & Suffix Regex Matching**:
  - Handles Arabic prefixes (`و`, `ف`, `ب`, `ك`, `ل`, `وال`, `فال`, `بال`, `لل`, `ولا`, `فلا`).
  - Handles Arabic suffixes (`ها`, `هم`, `كم`, `نا`, `ين`, `ان`, `ية`, `اً`, `ه`, `ي`).
  - Handles punctuation boundaries (e.g., matching `ولا إله.` correctly).
- **Dictionary Database**: 102 pre-loaded terms in `data/default_dictionary.json` (covers deities, idols, mythology names, and oaths in Arabic and English).

### B. Subtitle Transformation & Word Deletion (`autocensor/core/subtitle_engine.py`)
- Supports `.srt`, `.vtt`, `.ass` formats.
- Supports replacement strings (e.g. `(طوط)` or `[BEEP]`).
- Supports complete word deletion when replacement is `""` or `[REMOVE]`, cleaning up surrounding whitespace.

### C. Audio Censorship & Signal Overlay (`autocensor/core/audio_engine.py`)
- Extracts 16-bit PCM WAV audio using FFmpeg (`-acodec pcm_s16le`).
- Synthesizes 1kHz sine-wave audio signal tone at forbidden word timestamp ranges.
- Supports complete muting or 1kHz tone overlay with soft edge padding (50ms).

### D. Lossless Video Re-Muxing (`autocensor/utils/ffmpeg_utils.py`)
- Re-muxes processed audio track and clean subtitle file with original video using lossless video copy (`ffmpeg -i input.mp4 -i clean_audio.wav -c:v copy -c:a aac output_Censored.mp4`).

### E. AI Speech-to-Text Fallback (`autocensor/core/stt_engine.py`)
- Integrates `faster-whisper` / `whisper` to output word-level timestamps when subtitle files are missing.

---

## 4. Stremio Integration Mechanisms Implemented

1. **Stremio Local Server API Monitor (`http://127.0.0.1:11470`)**:
   - Polls Stremio's local HTTP server to detect active streaming episode titles and hashes.
2. **In-Place Subtitle File Modifier (`live_subtitle_modifier.py`)**:
   - Monitors `G:\stremio-cache` for `.srt` / `.vtt` files and modifies text in-place.
3. **Embedded Subtitle Extractor**:
   - Uses `ffmpeg -i stream_file -map 0:s:0 -c:s srt output.srt` to extract embedded MKV/MP4 subtitle tracks in ~0.5s when no external `.srt` file exists on disk.
4. **Real-Time Audio Bleeper (`live_audio_bleeper.py`)**:
   - Triggers `winsound.Beep(1000, duration)` over system audio when forbidden word timestamps occur.
5. **Stremio External Player Interceptor (`stremio_proxy.py` & `AutoCensor_Stremio_Player.bat`)**:
   - Accepts stream URLs/files passed from Stremio's "Play in external player" setting (`python main.py --cli --stremio "%1"`), censors media, and launches VLC/MPV.

---

## 5. Key Discussion Points for Technical Next Steps

When discussing with another AI or developer, here are the key technical constraints and potential next architectural steps to consider:

### Point 1: Stremio Native Player Subtitle Rendering
- *Context*: When Stremio streams an episode inside its native Electron player without external player enabled, Stremio renders subtitles from internal web requests or embedded MKV tracks directly in memory rather than saving a `.srt` file on disk.
- *Discussion Topic*: 
  - Option A: Use Stremio's **External Player** setting pointing to `AutoCensor_Stremio_Player.bat` (VLC/MPV launcher).
  - Option B: Build a local **HTTP Subtitle Proxy Server** (e.g. `http://127.0.0.1:8080/subtitle?url=...`) that intercepts Stremio's subtitle requests and returns clean VTT/SRT subtitles on the fly.

### Point 2: Real-Time Audio Muting vs Sound Bleeping
- *Context*: `winsound.Beep()` overlays a 1kHz tone over system audio. To mute Stremio's internal audio track in real time during native playback, Windows Core Audio API (`pycaw` / WASAPI) can be used to temporarily mute Stremio's process volume for the duration of forbidden words.
