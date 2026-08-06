# Media Sanitizer Pro

**Media Sanitizer Pro** is a high-performance, fully local, private desktop media processing application designed to detect and redact unwanted or forbidden terms/phrases from local video episodes and movies.

## Key Features
- **Local Speech Recognition**: Automatic transcription and word-level timestamp alignment using `faster-whisper`.
- **Configurable Term Detection**: Built-in regex, plain-word boundaries, Unicode normalization, diacritic folding, and fuzzy matching options.
- **Multiple Output Actions**:
  - `black_mute`: Replace video frames with black screen and silence audio (duration preserved).
  - `cut`: Frame-accurate re-encoding trim and concat mode.
  - `mute`: Mute audio only.
  - `black_only`: Black video screen only.
  - `subtitle_redact_only`: Redact subtitle text.
- **PySide6 Desktop Interface**: Modern dark theme with drag-and-drop batch queue, term list editor, segment review screen with thumbnail previews, and progress/log views.
- **DRM & Compliance Protection**: Automatic detection of encrypted media with safe halt error messages. Zero third-party stream scraping or DRM circumvention.

## Installation
```bash
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

## Running the Application
```bash
python main.py
```
