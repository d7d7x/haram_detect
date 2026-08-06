import logging
import sys
from pathlib import Path
from utils.paths import get_app_dir

def setup_logger(debug: bool = False) -> logging.Logger:
    """Sets up standard logger for application console and file output."""
    logger = logging.getLogger("media_sanitizer")
    logger.setLevel(logging.DEBUG if debug else logging.INFO)
    logger.handlers.clear()

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Console Handler
    ch = logging.StreamHandler(sys.stdout)
    ch.setFormatter(formatter)
    logger.addHandler(ch)

    # File Handler
    log_file = get_app_dir() / "sanitizer.log"
    fh = logging.FileHandler(log_file, encoding="utf-8")
    fh.setFormatter(formatter)
    logger.addHandler(fh)

    return logger

logger = setup_logger()
