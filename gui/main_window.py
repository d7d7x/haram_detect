from pathlib import Path
from typing import Optional
from PySide6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QListWidget,
    QListWidgetItem, QPushButton, QLabel, QFileDialog, QMessageBox, QComboBox
)
from PySide6.QtCore import QThread, Signal, Qt
from core.config_manager import ConfigManager
from core.job_runner import JobRunner
from core.ffprobe_service import FFprobeService
from core.ffmpeg_service import FFmpegService
from core.models import MediaInfo, SanitizationSegment
from gui.widgets import DragDropArea
from gui.settings_view import SettingsView
from gui.terms_view import TermsView
from gui.review_view import ReviewView
from gui.progress_view import ProgressView
from utils.logging import logger

class WorkerThread(QThread):
    progress_signal = Signal(str, float)
    review_requested_signal = Signal(list)
    finished_signal = Signal(bool, str)

    def __init__(self, job_runner: JobRunner, video_path: str, external_sub: str, embedded_idx: int):
        super().__init__()
        self.job_runner = job_runner
        self.video_path = video_path
        self.external_sub = external_sub
        self.embedded_idx = embedded_idx
        self.reviewed_segments = None

    def set_reviewed_segments(self, segments: list[SanitizationSegment]):
        self.reviewed_segments = segments

    def run(self):
        try:
            def prog_cb(msg, p):
                self.progress_signal.emit(msg, p)

            def review_cb(segs):
                self.review_requested_signal.emit(segs)
                # Wait for GUI review response via confirm button
                while self.reviewed_segments is None and not self.job_runner.cancelled:
                    self.msleep(100)
                return self.reviewed_segments if self.reviewed_segments else segs

            success = self.job_runner.process_file(
                video_path=self.video_path,
                external_sub_path=self.external_sub,
                embedded_sub_index=self.embedded_idx if self.embedded_idx >= 0 else None,
                progress_callback=prog_cb,
                review_callback=review_cb
            )
            self.finished_signal.emit(success, "Processing completed successfully.")
        except Exception as e:
            logger.error(f"Job execution failed: {e}")
            self.finished_signal.emit(False, str(e))

class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Media Sanitizer Pro - Local Content Filter")
        self.resize(1000, 700)

        self.config_manager = ConfigManager()
        self.ffprobe = FFprobeService(self.config_manager.settings.ffprobe_path)
        self.ffmpeg = FFmpegService(self.config_manager.settings)
        self.job_runner = JobRunner(self.config_manager.settings, self.config_manager.term_lists)

        self.file_queue: list[dict] = []
        self.worker_thread: Optional[WorkerThread] = None

        self.init_ui()

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        main_layout = QVBoxLayout(central_widget)

        self.tabs = QTabWidget()

        # Tab 1: Main Queue
        self.tab_main = QWidget()
        self.setup_main_tab()
        self.tabs.addTab(self.tab_main, "Batch Queue")

        # Tab 2: Terms Manager
        self.terms_view = TermsView(self.config_manager)
        self.tabs.addTab(self.terms_view, "Terms Manager")

        # Tab 3: Review Segments
        self.review_view = ReviewView(self.ffmpeg)
        self.review_view.confirm_requested.connect(self.on_review_confirmed)
        self.tabs.addTab(self.review_view, "Review Segments")

        # Tab 4: Settings
        self.settings_view = SettingsView(self.config_manager)
        self.tabs.addTab(self.settings_view, "Settings")

        # Tab 5: Progress & Logs
        self.progress_view = ProgressView()
        self.progress_view.cancel_requested.connect(self.cancel_active_job)
        self.tabs.addTab(self.progress_view, "Progress & Logs")

        main_layout.addWidget(self.tabs)

    def setup_main_tab(self):
        layout = QVBoxLayout(self.tab_main)

        # Drag and Drop Box
        self.drag_drop = DragDropArea()
        self.drag_drop.files_dropped.connect(self.add_files)
        layout.addWidget(self.drag_drop)

        # File List Controls
        ctrl_row = QHBoxLayout()
        btn_browse = QPushButton("Add Files...")
        btn_browse.clicked.connect(self.browse_files)
        btn_clear = QPushButton("Clear Queue")
        btn_clear.clicked.connect(self.clear_queue)
        ctrl_row.addWidget(btn_browse)
        ctrl_row.addWidget(btn_clear)
        ctrl_row.addStretch()
        layout.addLayout(ctrl_row)

        # Queue List Widget
        self.queue_list = QListWidget()
        layout.addWidget(self.queue_list)

        # Subtitle selection & Output Folder
        sub_row = QHBoxLayout()
        sub_row.addWidget(QLabel("External Subtitle (.srt/.vtt):"))
        self.btn_select_sub = QPushButton("Select Subtitle...")
        self.btn_select_sub.clicked.connect(self.browse_subtitle)
        self.sub_label = QLabel("None")
        sub_row.addWidget(self.btn_select_sub)
        sub_row.addWidget(self.sub_label)
        sub_row.addStretch()
        layout.addLayout(sub_row)

        # MKV Embedded Subtitle Selection
        emb_sub_row = QHBoxLayout()
        emb_sub_row.addWidget(QLabel("MKV Embedded Subtitle Track (ترجمة MKV المدمجة):"))
        self.embedded_sub_combo = QComboBox()
        self.embedded_sub_combo.addItem("Auto-Detect Embedded Subtitle Track (Recommended)", -2)
        self.embedded_sub_combo.addItem("None - Force Whisper AI Speech Recognition", -1)
        emb_sub_row.addWidget(self.embedded_sub_combo)
        emb_sub_row.addStretch()
        layout.addLayout(emb_sub_row)

        # Start Button
        btn_start = QPushButton("Start Sanitization Process")
        btn_start.setStyleSheet("font-size: 15px; padding: 12px; background-color: #10B981;")
        btn_start.clicked.connect(self.start_processing)
        layout.addWidget(btn_start)

    def browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "Select Video Files", "", "Video Files (*.mp4 *.mkv *.webm *.mov *.avi *.ts *.m4v)"
        )
        if files:
            self.add_files(files)

    def add_files(self, filepaths: list[str]):
        for fp in filepaths:
            if not any(f["path"] == fp for f in self.file_queue):
                info = self.ffprobe.inspect_file(fp)
                self.file_queue.append({
                    "path": fp,
                    "info": info,
                    "sub_path": None,
                    "status": "Ready"
                })
                item_text = f"{Path(fp).name} | {info.duration:.1f}s | Codec: {info.video_codec} | Size: {info.file_size_bytes/(1024*1024):.1f}MB"
                if info.subtitle_streams:
                    item_text += f" [{len(info.subtitle_streams)} Embedded Subtitle Track(s)]"
                if info.is_drm_protected:
                    item_text += " [DRM PROTECTED - ERROR]"
                self.queue_list.addItem(item_text)

                # Populate embedded subtitle track dropdown
                self.embedded_sub_combo.clear()
                if info.subtitle_streams:
                    self.embedded_sub_combo.addItem("Auto-Detect Embedded Subtitle Track (Recommended)", -2)
                    for sub_stream in info.subtitle_streams:
                        title_str = f"Stream #{sub_stream.index} - {sub_stream.language} ({sub_stream.title or sub_stream.codec_name})"
                        self.embedded_sub_combo.addItem(title_str, sub_stream.index)
                self.embedded_sub_combo.addItem("None - Force Whisper AI Speech Recognition", -1)

    def clear_queue(self):
        self.file_queue.clear()
        self.queue_list.clear()

    def browse_subtitle(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "Select Subtitle File", "", "Subtitle Files (*.srt *.vtt *.ass *.ssa)"
        )
        if file:
            self.sub_label.setText(Path(file).name)
            if self.file_queue:
                self.file_queue[0]["sub_path"] = file

    def start_processing(self):
        if not self.file_queue:
            QMessageBox.warning(self, "Empty Queue", "Please add at least one video file to process.")
            return

        item = self.file_queue[0]
        if item["info"].is_drm_protected:
            QMessageBox.critical(self, "DRM Error", "Selected file is DRM protected and cannot be sanitized.")
            return

        self.tabs.setCurrentWidget(self.progress_view)

        # Resolve embedded subtitle index
        sel_idx = self.embedded_sub_combo.currentData()
        if sel_idx is None or sel_idx == -2:
            sub_streams = item["info"].subtitle_streams
            if sub_streams:
                ar_stream = next((s for s in sub_streams if s.language in ["ara", "ar", "arabic"]), None)
                sel_idx = ar_stream.index if ar_stream else sub_streams[0].index
            else:
                sel_idx = -1

        # Re-instantiate job runner with latest settings/terms
        self.job_runner = JobRunner(self.config_manager.settings, self.config_manager.term_lists)

        self.worker_thread = WorkerThread(
            job_runner=self.job_runner,
            video_path=item["path"],
            external_sub=item.get("sub_path", ""),
            embedded_idx=sel_idx
        )
        self.worker_thread.progress_signal.connect(self.progress_view.update_progress)
        self.worker_thread.review_requested_signal.connect(self.on_review_requested)
        self.worker_thread.finished_signal.connect(self.on_job_finished)
        self.worker_thread.start()

    def on_review_requested(self, segments: list[SanitizationSegment]):
        item = self.file_queue[0]
        self.review_view.load_segments(item["path"], segments)
        self.tabs.setCurrentWidget(self.review_view)

    def on_review_confirmed(self, confirmed_segs: list[SanitizationSegment]):
        if self.worker_thread:
            self.worker_thread.set_reviewed_segments(confirmed_segs)
            self.tabs.setCurrentWidget(self.progress_view)

    def on_job_finished(self, success: bool, message: str):
        if success:
            if hasattr(self.job_runner, "last_job_results") and self.job_runner.last_job_results:
                self.progress_view.show_completed_outputs(self.job_runner.last_job_results)
            QMessageBox.information(self, "Complete", message)
        else:
            QMessageBox.critical(self, "Error", f"Processing failed: {message}")

    def cancel_active_job(self):
        if self.job_runner:
            self.job_runner.cancel()
            self.progress_view.update_progress("Cancellation requested...", 0)
