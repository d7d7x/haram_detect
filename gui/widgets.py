from PySide6.QtWidgets import QFrame, QVBoxLayout, QLabel, QWidget
from PySide6.QtCore import Qt, Signal
from PySide6.QtGui import QDragEnterEvent, QDropEvent

class DragDropArea(QFrame):
    files_dropped = Signal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAcceptDrops(True)
        self.setFrameShape(QFrame.StyledPanel)
        self.setStyleSheet("""
            QFrame {
                border: 2px dashed #4A4A5A;
                border-radius: 10px;
                background-color: #1A1A22;
                min-height: 120px;
            }
            QFrame:hover {
                border-color: #6366F1;
                background-color: #20202E;
            }
        """)

        layout = QVBoxLayout(self)
        self.label = QLabel("Drag & Drop Video Files Here\nor Click 'Browse Files'", self)
        self.label.setAlignment(Qt.AlignCenter)
        self.label.setStyleSheet("color: #A0A0B0; font-size: 14px; font-weight: 500;")
        layout.addWidget(self.label)

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = [url.toLocalFile() for url in event.mimeData().urls() if url.isLocalFile()]
        if files:
            self.files_dropped.emit(files)

class WaveformPlaceholder(QWidget):
    """Placeholder widget for audio waveform visual representation."""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFixedHeight(50)
        self.setStyleSheet("""
            QWidget {
                background-color: #22222A;
                border: 1px solid #333340;
                border-radius: 4px;
            }
        """)
        layout = QVBoxLayout(self)
        label = QLabel("Audio Waveform Preview Placeholder", self)
        label.setAlignment(Qt.AlignCenter)
        label.setStyleSheet("color: #666675; font-size: 11px;")
        layout.addWidget(label)
