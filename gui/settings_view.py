from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QFormLayout, QGroupBox, QLineEdit,
    QPushButton, QComboBox, QDoubleSpinBox, QSpinBox, QCheckBox, QFileDialog, QMessageBox
)
from core.models import AppSettings, SanitizationAction, SegmentExpansionMode
from core.config_manager import ConfigManager
from core.validators import check_ffmpeg_installed

class SettingsView(QWidget):
    def __init__(self, config_manager: ConfigManager, parent=None):
        super().__init__(parent)
        self.config_manager = config_manager
        self.settings = config_manager.settings
        self.init_ui()

    def init_ui(self):
        main_layout = QVBoxLayout(self)

        # 1. Paths Group
        paths_group = QGroupBox("System Paths")
        paths_layout = QFormLayout(paths_group)

        self.ffmpeg_input = QLineEdit(self.settings.ffmpeg_path)
        self.ffprobe_input = QLineEdit(self.settings.ffprobe_path)
        
        btn_ffmpeg = QPushButton("Browse")
        btn_ffmpeg.clicked.connect(self.browse_ffmpeg)
        btn_ffprobe = QPushButton("Browse")
        btn_ffprobe.clicked.connect(self.browse_ffprobe)

        f_row = QHBoxLayout()
        f_row.addWidget(self.ffmpeg_input)
        f_row.addWidget(btn_ffmpeg)

        fp_row = QHBoxLayout()
        fp_row.addWidget(self.ffprobe_input)
        fp_row.addWidget(btn_ffprobe)

        paths_layout.addRow("FFmpeg Binary:", f_row)
        paths_layout.addRow("FFprobe Binary:", fp_row)

        btn_verify = QPushButton("Test FFmpeg Setup")
        btn_verify.clicked.connect(self.test_ffmpeg)
        paths_layout.addRow("", btn_verify)

        main_layout.addWidget(paths_group)

        # 2. Transcription Group
        whisper_group = QGroupBox("Local Speech Recognition (Whisper)")
        w_layout = QFormLayout(whisper_group)

        self.model_combo = QComboBox()
        self.model_combo.addItems(["tiny", "base", "small", "medium", "large-v3-turbo", "large-v3"])
        self.model_combo.setCurrentText(self.settings.whisper_model)

        self.device_combo = QComboBox()
        self.device_combo.addItems(["auto", "cpu", "cuda"])
        self.device_combo.setCurrentText(self.settings.device)

        self.lang_input = QLineEdit(self.settings.language)

        self.task_combo = QComboBox()
        self.task_combo.addItems(["transcribe", "translate"])
        self.task_combo.setCurrentText(getattr(self.settings, "whisper_task", "transcribe"))

        self.target_lang_combo = QComboBox()
        self.target_lang_combo.addItem("ar (Arabic - العربية)", "ar")
        self.target_lang_combo.addItem("en (English)", "en")
        self.target_lang_combo.addItem("none (Original Language)", "none")

        curr_target = getattr(self.settings, "target_subtitle_language", "ar")
        idx = self.target_lang_combo.findData(curr_target)
        if idx >= 0:
            self.target_lang_combo.setCurrentIndex(idx)

        w_layout.addRow("Whisper Model:", self.model_combo)
        w_layout.addRow("Compute Device:", self.device_combo)
        w_layout.addRow("Language (auto or code):", self.lang_input)
        w_layout.addRow("Whisper Task (transcribe / translate):", self.task_combo)
        w_layout.addRow("Target Subtitle Language:", self.target_lang_combo)

        main_layout.addWidget(whisper_group)

        # 3. Sanitization & Timing Group
        san_group = QGroupBox("Sanitization & Timing Controls")
        s_layout = QFormLayout(san_group)

        self.pre_pad_spin = QDoubleSpinBox()
        self.pre_pad_spin.setRange(0.0, 5.0)
        self.pre_pad_spin.setSingleStep(0.05)
        self.pre_pad_spin.setValue(self.settings.pre_padding_sec)

        self.post_pad_spin = QDoubleSpinBox()
        self.post_pad_spin.setRange(0.0, 5.0)
        self.post_pad_spin.setSingleStep(0.05)
        self.post_pad_spin.setValue(self.settings.post_padding_sec)

        self.min_dur_spin = QDoubleSpinBox()
        self.min_dur_spin.setRange(0.1, 10.0)
        self.min_dur_spin.setValue(self.settings.min_segment_duration_sec)

        self.merge_thresh_spin = QDoubleSpinBox()
        self.merge_thresh_spin.setRange(0.0, 5.0)
        self.merge_thresh_spin.setValue(self.settings.merge_threshold_sec)

        self.action_combo = QComboBox()
        for act in SanitizationAction:
            self.action_combo.addItem(act.value, act)
        self.action_combo.setCurrentText(self.settings.default_action.value)

        self.mode_combo = QComboBox()
        for mode in SegmentExpansionMode:
            self.mode_combo.addItem(mode.value, mode)
        self.mode_combo.setCurrentText(self.settings.expansion_mode.value)

        s_layout.addRow("Pre-Padding (sec):", self.pre_pad_spin)
        s_layout.addRow("Post-Padding (sec):", self.post_pad_spin)
        s_layout.addRow("Min Segment Duration (sec):", self.min_dur_spin)
        s_layout.addRow("Merge Threshold (sec):", self.merge_thresh_spin)
        s_layout.addRow("Default Action:", self.action_combo)
        s_layout.addRow("Expansion Mode:", self.mode_combo)

        main_layout.addWidget(san_group)

        # 4. Rendering Codec Options
        codec_group = QGroupBox("Rendering Codec Settings")
        c_layout = QFormLayout(codec_group)

        self.v_codec_input = QLineEdit(self.settings.video_codec)
        self.crf_spin = QSpinBox()
        self.crf_spin.setRange(0, 51)
        self.crf_spin.setValue(self.settings.crf)

        self.preset_combo = QComboBox()
        self.preset_combo.addItems(["ultrafast", "superfast", "veryfast", "faster", "fast", "medium", "slow", "slower", "veryslow"])
        self.preset_combo.setCurrentText(self.settings.preset)

        c_layout.addRow("Video Codec:", self.v_codec_input)
        c_layout.addRow("CRF (Quality):", self.crf_spin)
        c_layout.addRow("Encoding Preset:", self.preset_combo)

        main_layout.addWidget(codec_group)

        # Save Button
        btn_save = QPushButton("Save Settings")
        btn_save.clicked.connect(self.save_settings)
        main_layout.addWidget(btn_save)
        main_layout.addStretch()

    def browse_ffmpeg(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select FFmpeg Binary")
        if file:
            self.ffmpeg_input.setText(file)

    def browse_ffprobe(self):
        file, _ = QFileDialog.getOpenFileName(self, "Select FFprobe Binary")
        if file:
            self.ffprobe_input.setText(file)

    def test_ffmpeg(self):
        ok, msg = check_ffmpeg_installed(self.ffmpeg_input.text(), self.ffprobe_input.text())
        if ok:
            QMessageBox.information(self, "Success", msg)
        else:
            QMessageBox.critical(self, "Error", msg)

    def save_settings(self):
        s = self.settings
        s.ffmpeg_path = self.ffmpeg_input.text()
        s.ffprobe_path = self.ffprobe_input.text()
        s.whisper_model = self.model_combo.currentText()
        s.device = self.device_combo.currentText()
        s.language = self.lang_input.text()
        s.whisper_task = self.task_combo.currentText()
        s.target_subtitle_language = self.target_lang_combo.currentData()
        s.pre_padding_sec = self.pre_pad_spin.value()
        s.post_padding_sec = self.post_pad_spin.value()
        s.min_segment_duration_sec = self.min_dur_spin.value()
        s.merge_threshold_sec = self.merge_thresh_spin.value()
        s.default_action = SanitizationAction(self.action_combo.currentText())
        s.expansion_mode = SegmentExpansionMode(self.mode_combo.currentText())
        s.video_codec = self.v_codec_input.text()
        s.crf = self.crf_spin.value()
        s.preset = self.preset_combo.currentText()

        if self.config_manager.save_settings(s):
            QMessageBox.information(self, "Settings", "Settings saved successfully.")
        else:
            QMessageBox.warning(self, "Settings", "Failed to save settings.")
