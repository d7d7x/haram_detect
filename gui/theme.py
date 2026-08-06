DARK_THEME_QSS = """
QMainWindow {
    background-color: #121214;
    color: #E0E0E6;
}

QWidget {
    font-family: 'Segoe UI', Helvetica, Arial, sans-serif;
    font-size: 13px;
    color: #E0E0E6;
}

QTabWidget::pane {
    border: 1px solid #2A2A32;
    background-color: #18181C;
    border-radius: 6px;
}

QTabBar::tab {
    background-color: #222228;
    color: #A0A0B0;
    padding: 10px 18px;
    margin-right: 4px;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
}

QTabBar::tab:selected {
    background-color: #18181C;
    color: #6366F1;
    font-weight: bold;
    border-bottom: 2px solid #6366F1;
}

QPushButton {
    background-color: #6366F1;
    color: #FFFFFF;
    border: none;
    padding: 8px 16px;
    border-radius: 5px;
    font-weight: 600;
}

QPushButton:hover {
    background-color: #4F46E5;
}

QPushButton:pressed {
    background-color: #4338CA;
}

QPushButton:disabled {
    background-color: #2E2E38;
    color: #666675;
}

QLineEdit, QSpinBox, QDoubleSpinBox, QComboBox {
    background-color: #22222A;
    border: 1px solid #333340;
    border-radius: 4px;
    padding: 6px 10px;
    color: #FFFFFF;
}

QLineEdit:focus, QComboBox:focus {
    border: 1px solid #6366F1;
}

QTableWidget, QTableView {
    background-color: #18181C;
    gridline-color: #2A2A34;
    border: 1px solid #2A2A32;
    border-radius: 6px;
}

QHeaderView::section {
    background-color: #22222A;
    color: #A0A0B0;
    padding: 8px;
    border: none;
    font-weight: bold;
}

QProgressBar {
    border: 1px solid #2A2A34;
    border-radius: 6px;
    text-align: center;
    background-color: #22222A;
    color: #FFFFFF;
}

QProgressBar::chunk {
    background-color: #6366F1;
    border-radius: 5px;
}

QGroupBox {
    border: 1px solid #2A2A34;
    border-radius: 6px;
    margin-top: 12px;
    padding-top: 16px;
    font-weight: bold;
}

QGroupBox::title {
    subcontrol-origin: margin;
    subcontrol-position: top left;
    left: 10px;
    padding: 0 4px;
    color: #6366F1;
}
"""

def apply_theme(app):
    """Applies the custom dark QSS theme to the QApplication instance."""
    app.setStyleSheet(DARK_THEME_QSS)
