import os
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QProgressBar, QPushButton, QTextEdit, QGroupBox
)
from PySide6.QtCore import Signal, QUrl
from PySide6.QtGui import QDesktopServices

class ProgressView(QWidget):
    cancel_requested = Signal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.last_results = {}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        self.status_label = QLabel("Status: Idle")
        self.status_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #6366F1;")
        layout.addWidget(self.status_label)

        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        layout.addWidget(self.progress_bar)

        self.btn_cancel = QPushButton("Cancel Job")
        self.btn_cancel.setStyleSheet("background-color: #EF4444;")
        self.btn_cancel.clicked.connect(self.cancel_requested.emit)
        layout.addWidget(self.btn_cancel)

        # Output Summary Group (Hidden during processing, shown on completion)
        self.output_group = QGroupBox("Output Files & Transcripts (ملفات المخرجات والترانزكريبت)")
        self.output_group.setVisible(False)
        out_layout = QVBoxLayout(self.output_group)

        self.video_label = QLabel("Filtered Video: -")
        self.txt_ar_label = QLabel("Arabic Transcript: -")
        self.txt_en_label = QLabel("English Transcript: -")

        out_layout.addWidget(self.video_label)
        out_layout.addWidget(self.txt_ar_label)
        out_layout.addWidget(self.txt_en_label)

        btn_row = QHBoxLayout()
        self.btn_open_video = QPushButton("🎥 Open Video (فتح المقطع المفلتر)")
        self.btn_open_video.clicked.connect(lambda: self.open_file("output_video"))

        self.btn_open_ar_txt = QPushButton("📜 Open Arabic Transcript (تفريغ عربي)")
        self.btn_open_ar_txt.clicked.connect(lambda: self.open_file("transcript_ar_txt"))

        self.btn_open_en_txt = QPushButton("📜 Open English Transcript (تفريغ إنجليزي)")
        self.btn_open_en_txt.clicked.connect(lambda: self.open_file("transcript_en_txt"))

        self.btn_open_folder = QPushButton("📁 Open Folder (فتح المجلد)")
        self.btn_open_folder.clicked.connect(self.open_folder)

        btn_row.addWidget(self.btn_open_video)
        btn_row.addWidget(self.btn_open_ar_txt)
        btn_row.addWidget(self.btn_open_en_txt)
        btn_row.addWidget(self.btn_open_folder)
        out_layout.addLayout(btn_row)

        layout.addWidget(self.output_group)

        layout.addWidget(QLabel("Execution Logs:"))
        self.log_edit = QTextEdit()
        self.log_edit.setReadOnly(True)
        self.log_edit.setStyleSheet("font-family: Consolas, monospace; font-size: 11px;")
        layout.addWidget(self.log_edit)

    def update_progress(self, message: str, percentage: float):
        self.status_label.setText(f"Status: {message}")
        self.progress_bar.setValue(int(percentage))
        self.log_edit.append(f"[{percentage:.0f}%] {message}")

    def append_log(self, text: str):
        self.log_edit.append(text)

    def show_completed_outputs(self, results: dict):
        self.last_results = results
        vid_path = results.get("output_video", "")
        ar_txt = results.get("transcript_ar_txt", "")
        en_txt = results.get("transcript_en_txt", "")

        self.video_label.setText(f"Filtered Video: {Path(vid_path).name if vid_path else 'N/A'}")
        self.txt_ar_label.setText(f"Arabic Transcript (.txt): {Path(ar_txt).name if ar_txt else 'N/A'}")
        self.txt_en_label.setText(f"English Transcript (.txt): {Path(en_txt).name if en_txt else 'N/A'}")

        self.output_group.setVisible(True)

    def open_file(self, key: str):
        filepath = self.last_results.get(key, "")
        if filepath and os.path.exists(filepath):
            QDesktopServices.openUrl(QUrl.fromLocalFile(filepath))

    def open_folder(self):
        vid_path = self.last_results.get("output_video", "")
        if vid_path and os.path.exists(vid_path):
            folder = str(Path(vid_path).parent)
            QDesktopServices.openUrl(QUrl.fromLocalFile(folder))

