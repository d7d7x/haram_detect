from typing import List, Tuple
from core.models import SanitizationSegment, AppSettings
from utils.logging import logger

class SceneDetector:
    def __init__(self, settings: AppSettings):
        self.settings = settings

    def expand_segments_to_scenes(
        self,
        filepath: str,
        segments: List[SanitizationSegment],
        total_duration: float
    ) -> List[SanitizationSegment]:
        """Detects scene boundaries using PySceneDetect and expands segments accordingly."""
        scene_cuts = self._detect_scenes(filepath)

        if not scene_cuts:
            logger.warning("Scene detection unavailable or yielded no cuts. Falling back to Utterance mode.")
            return segments

        expanded = []
        for seg in segments:
            scene_start = 0.0
            scene_end = total_duration

            # Find matching scene containing segment start
            for start_sec, end_sec in scene_cuts:
                if start_sec <= seg.start <= end_sec:
                    scene_start = start_sec
                    scene_end = end_sec
                    break

            # Limit max scene extension length
            if (scene_end - scene_start) > self.settings.max_scene_duration_sec:
                scene_start = max(0.0, seg.start - (self.settings.max_scene_duration_sec / 2.0))
                scene_end = min(total_duration, seg.end + (self.settings.max_scene_duration_sec / 2.0))

            seg.start = round(scene_start, 3)
            seg.end = round(scene_end, 3)
            expanded.append(seg)

        return expanded

    def _detect_scenes(self, filepath: str) -> List[Tuple[float, float]]:
        """Invokes PySceneDetect ContentDetector if available."""
        try:
            from scenedetect import SceneManager, open_video
            from scenedetect.detectors import ContentDetector

            video = open_video(filepath)
            scene_manager = SceneManager()
            scene_manager.add_detector(ContentDetector())
            scene_manager.detect_scenes(video)
            scene_list = scene_manager.get_scene_list()

            return [(start.get_seconds(), end.get_seconds()) for start, end in scene_list]
        except Exception as e:
            logger.warning(f"PySceneDetect execution failed or not installed: {e}")
            return []
