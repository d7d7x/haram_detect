# ⚡ AutoCensor AI

**AutoCensor AI** is a fully automated desktop application and background service designed to ingest video files or stream downloads, detect polytheistic, shirk, or inappropriate terms in text subtitles and spoken audio, and automatically censor them.

---

## 🌟 Key Features

1. **File & Stream Ingestion**:
   - Supports local video files (`.mp4`, `.mkv`, `.avi`, `.mov`, `.webm`).
   - Supports subtitle tracks (`.srt`, `.vtt`, `.ass`) with automatic matching.
   - **Watcher Mode**: Continuously monitors a target folder (e.g. `Downloads`) to automatically process new files in the background.

2. **NLP & Dictionary Censorship Engine**:
   - Built-in customizable dictionary with pre-configured polytheism/shirk terms in **Arabic & English**.
   - Arabic normalization (automatic tashkeel/diacritics removal, alef unification, tatweel stripping).
   - Regex & word-boundary matching with customizable replacement terms (`(طوط)` or `[BEEP]`).

3. **Audio Censorship & AI Speech-to-Text**:
   - FFmpeg integration for lossless video re-muxing (`-c:v copy`).
   - Pure PCM audio signal synthesizer for soft 1kHz BEEP tone overlay or complete muting.
   - `faster-whisper` AI Speech-to-Text integration for word-timestamped transcription when subtitles are missing.

4. **Modern UI & Headless CLI**:
   - Sleek dark mode GUI with CustomTkinter.
   - Drag-and-drop file ingestion, visual progress tracking, and detection table viewer.
   - Full command-line interface for headless server deployment.

---

## ⚙️ Requirements & Installation

### Prerequisites
- **Python 3.10+**
- **FFmpeg** installed and accessible in PATH.

### Installation Steps

```bash
# Clone or navigate to the repository
git clone https://github.com/d7d7x/haram_detect.git
cd haram_detect

# Create virtual environment (optional)
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/macOS

# Install dependencies
pip install -r requirements.txt
```

---

## 🚀 Usage Guide

### 1. Launching Desktop GUI
To launch the modern desktop application:

```bash
python main.py
```

### 2. Command-Line Interface (CLI)

#### Censor a Video File:
```bash
python main.py --cli --input my_movie.mp4 --mode beep
```

#### Specify Custom Subtitle File & Output:
```bash
python main.py --cli --input video.mp4 --subtitle subs.srt --output clean_video.mp4 --mode mute
```

#### Run Background Watcher Mode:
```bash
python main.py --cli --watch "C:\Users\Username\Downloads" --mode beep
```

---

## 📁 Project Architecture

```
haram_detect/
├── autocensor/
│   ├── config.py                 # Application settings and styling tokens
│   ├── core/
│   │   ├── dictionary.py         # Terms database and Arabic/English NLP matcher
│   │   ├── subtitle_engine.py    # Subtitle parser, word matcher, and transformer
│   │   ├── audio_engine.py       # Audio extractor, 1kHz tone overlay & muting
│   │   ├── stt_engine.py         # Whisper / faster-whisper speech recognition
│   │   ├── media_processor.py    # Pipeline orchestrator
│   │   └── watcher.py            # Watchdog background folder watcher
│   ├── ui/
│   │   ├── main_window.py        # CustomTkinter GUI main window
│   │   ├── processing_tab.py     # Ingestion & progress tab
│   │   ├── dictionary_tab.py     # Terms management tab
│   │   └── watcher_tab.py        # Background watcher controls tab
│   ├── cli.py                    # Headless CLI service entry point
│   └── utils/
│       ├── ffmpeg_utils.py       # FFmpeg audio extraction & remuxing
│       └── helpers.py            # String & time conversion helpers
├── data/
│   └── default_dictionary.json   # Default prohibited terms JSON database
├── requirements.txt              # Project dependencies
├── main.py                       # Main application launcher
└── README.md                     # Documentation
```

