from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum

class SanitizationAction(str, Enum):
    CUT = "cut"
    MUTE = "mute"
    BLACK_MUTE = "black_mute"
    BLACK_ONLY = "black_only"
    SUBTITLE_REDACT_ONLY = "subtitle_redact_only"

class SegmentExpansionMode(str, Enum):
    WORD = "word"
    UTTERANCE = "utterance"
    SCENE = "scene"

@dataclass
class AudioStreamInfo:
    index: int
    codec_name: str
    channels: int
    language: str = "und"
    title: str = ""

@dataclass
class SubtitleStreamInfo:
    index: int
    codec_name: str
    language: str = "und"
    title: str = ""

@dataclass
class MediaInfo:
    filepath: str
    duration: float
    video_codec: str
    width: int
    height: int
    fps: float
    bitrate: int
    file_size_bytes: int
    audio_streams: List[AudioStreamInfo] = field(default_factory=list)
    subtitle_streams: List[SubtitleStreamInfo] = field(default_factory=list)
    is_drm_protected: bool = False

@dataclass
class WordTimestamp:
    word: str
    start: float
    end: float
    probability: float = 1.0

@dataclass
class TranscriptSegment:
    start: float
    end: float
    text: str
    words: List[WordTimestamp] = field(default_factory=list)

@dataclass
class SanitizationSegment:
    id: str
    start: float
    end: float
    action: SanitizationAction
    matched_term: str
    matched_text: str
    term_list_id: str
    enabled: bool = True
    manual_override: bool = False
    confidence: float = 1.0

@dataclass
class TermList:
    id: str
    name: str
    enabled: bool
    action: SanitizationAction
    patterns: List[str]
    is_regex: bool = False

@dataclass
class AppSettings:
    ffmpeg_path: str = "ffmpeg"
    ffprobe_path: str = "ffprobe"
    whisper_model: str = "medium"
    device: str = "auto"
    compute_type: str = "default"
    language: str = "ar"
    whisper_task: str = "transcribe"  # "transcribe" or "translate"
    target_subtitle_language: str = "ar"  # "none", "ar", "en", etc.
    pre_padding_sec: float = 0.15
    post_padding_sec: float = 0.35
    min_segment_duration_sec: float = 1.0
    merge_threshold_sec: float = 0.75
    default_action: SanitizationAction = SanitizationAction.BLACK_MUTE
    expansion_mode: SegmentExpansionMode = SegmentExpansionMode.WORD
    max_scene_duration_sec: float = 15.0
    subtitle_redaction_mode: str = "asterisks"
    video_codec: str = "libx264"
    audio_codec: str = "aac"
    crf: int = 18
    preset: str = "medium"
    audio_bitrate: str = "192k"
    crossfade_ms: int = 20
    fuzzy_match_enabled: bool = False
    fuzzy_match_threshold: float = 85.0
    diacritic_folding: bool = True
    debug_mode: bool = False
    output_directory: str = ""
