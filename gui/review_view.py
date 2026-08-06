import uuid
from pathlib import Path
from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTableWidget, QTableWidgetItem,
    QPushButton, QLabel, QHeaderView, QComboBox, QCheckBox, QMessageBox
)
from PySide6.QtCore import Signal
from PySide6.QtGui import QPixmap
from core.models import SanitizationSegment, SanitizationAction
from core.ffmpeg_service import FFmpegService
from utils.paths import get_temp_dir
from utils.time_utils import seconds_to_timestamp, timestamp_to_seconds

class ReviewView(QWidget):
    confirm_requested = Signal(list)

    def __init__(self, ffmpeg_service: FFmpegService, parent=None):
        super().__init__(parent)
        self.ffmpeg_service = ffmpeg_service
        self.segments: list[SanitizationSegment] = []
        self.video_path: str = ""
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout(self)

        top_row = QHBoxLayout()
        top_row.addWidget(QLabel("Detected Sanitization Segments Review:"))
        
        btn_add = QPushButton("Add Manual Segment")
        btn_add.clicked.connect(self.add_segment)
        btn_del = QPushButton("Delete Selected")
        btn_del.clicked.connect(self.delete_selected_segment)

        top_row.addWidget(btn_add)
        top_row.addWidget(btn_del)
        layout.addLayout(top_row)

        self.table = QTableWidget(0, 7)
        self.table.setHorizontalHeaderLabels([
            "Enable", "Start Time", "End Time", "Matched Text", "Pattern", "Action", "Confidence"
        ])
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.Stretch)
        self.table.itemSelectionChanged.connect(self.on_selection_changed)
        layout.addWidget(self.table)

        # Bottom Preview Area & Action Button
        preview_layout = QHBoxLayout()
        self.thumb_label = QLabel("No Thumbnail Preview")
        self.thumb_label.setFixedSize(160, 90)
        self.thumb_label.setStyleSheet("border: 1px solid #333340; background-color: #000;")
        preview_layout.addWidget(self.thumb_label)

        self.info_label = QLabel("Select a segment above to view details and preview frame.")
        preview_layout.addWidget(self.info_label, 1)

        layout.addLayout(preview_layout)

        # Confirm & Render Button
        self.btn_confirm = QPushButton("Confirm & Render Video")
        self.btn_confirm.setStyleSheet("font-size: 15px; padding: 12px; background-color: #10B981; font-weight: bold;")
        self.btn_confirm.clicked.connect(self.emit_confirmation)
        layout.addWidget(self.btn_confirm)

    def load_segments(self, video_path: str, segments: list[SanitizationSegment]):
        self.video_path = video_path
        self.segments = segments
        self.table.setRowCount(0)

        for row, seg in enumerate(segments):
            self.table.insertRow(row)

            # Enable Checkbox
            cb = QCheckBox()
            cb.setChecked(seg.enabled)
            cb.stateChanged.connect(lambda state, r=row: self.update_segment_enable(r, state))
            self.table.setCellWidget(row, 0, cb)

            # Start Time
            item_start = QTableWidgetItem(seconds_to_timestamp(seg.start))
            self.table.setItem(row, 1, item_start)

            # End Time
            item_end = QTableWidgetItem(seconds_to_timestamp(seg.end))
            self.table.setItem(row, 2, item_end)

            # Matched Text
            self.table.setItem(row, 3, QTableWidgetItem(seg.matched_text))

            # Pattern
            self.table.setItem(row, 4, QTableWidgetItem(seg.matched_term))

            # Action Combo Box
            combo = QComboBox()
            for act in SanitizationAction:
                combo.addItem(act.value, act)
            combo.setCurrentText(seg.action.value)
            combo.currentTextChanged.connect(lambda text, r=row: self.update_segment_action(r, text))
            self.table.setCellWidget(row, 5, combo)

            # Confidence
            self.table.setItem(row, 6, QTableWidgetItem(f"{seg.confidence*100:.0f}%"))

    def update_segment_enable(self, row: int, state: int):
        if row < len(self.segments):
            self.segments[row].enabled = (state != 0)

    def update_segment_action(self, row: int, action_str: str):
        if row < len(self.segments):
            self.segments[row].action = SanitizationAction(action_str)

    def add_segment(self):
        new_seg = SanitizationSegment(
            id=str(uuid.uuid4())[:8],
            start=0.0,
            end=1.0,
            action=SanitizationAction.BLACK_MUTE,
            matched_term="manual",
            matched_text="manual addition",
            term_list_id="manual",
            enabled=True,
            manual_override=True
        )
        self.segments.append(new_seg)
        self.load_segments(self.video_path, self.segments)

    def delete_selected_segment(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.segments):
            del self.segments[row]
            self.load_segments(self.video_path, self.segments)

    def on_selection_changed(self):
        row = self.table.currentRow()
        if 0 <= row < len(self.segments):
            seg = self.segments[row]
            self.info_label.setText(
                f"Segment ID: {seg.id}\nMatched Text: {seg.matched_text}\nDuration: {seg.end - seg.start:.2f}s"
            )

            # Generate Thumbnail
            if self.video_path and Path(self.video_path).exists():
                thumb_file = str(get_temp_dir() / f"preview_{seg.id}.jpg")
                mid_time = (seg.start + seg.end) / 2.0
                if self.ffmpeg_service.generate_thumbnail(self.video_path, mid_time, thumb_file):
                    pixmap = QPixmap(thumb_file).scaled(160, 90)
                    self.thumb_label.setPixmap(pixmap)

    def get_confirmed_segments(self) -> list[SanitizationSegment]:
        """Reads edited start and end times back into segments list."""
        for row in range(self.table.rowCount()):
            if row < len(self.segments):
                try:
                    start_str = self.table.item(row, 1).text()
                    end_str = self.table.item(row, 2).text()
                    self.segments[row].start = timestamp_to_seconds(start_str)
                    self.segments[row].end = timestamp_to_seconds(end_str)
                except Exception:
                    pass
        return self.segments

    def emit_confirmation(self):
        confirmed = self.get_confirmed_segments()
        self.confirm_requested.emit(confirmed)
