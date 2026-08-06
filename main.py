import sys
import os

# Ensure project root is in python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from PySide6.QtWidgets import QApplication
from gui.theme import apply_theme
from gui.main_window import MainWindow
from utils.logging import setup_logger

def main():
    logger = setup_logger(debug=True)
    logger.info("Initializing Media Sanitizer Pro Application...")

    app = QApplication(sys.argv)
    apply_theme(app)

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()
