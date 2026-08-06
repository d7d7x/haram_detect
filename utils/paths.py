import sys
from pathlib import Path

def get_app_dir() -> Path:
    """Returns the base application root directory."""
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

def get_config_dir() -> Path:
    """Returns the path to the configuration directory."""
    config_dir = get_app_dir() / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir

def get_temp_dir() -> Path:
    """Returns a temporary working directory for intermediate files."""
    temp_dir = get_app_dir() / "temp_workspace"
    temp_dir.mkdir(parents=True, exist_ok=True)
    return temp_dir
