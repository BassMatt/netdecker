import logging
import os
import platform
import sys
from pathlib import Path
from typing import Final


def get_app_data_dir() -> Path:
    """Get the platform-appropriate directory for application data."""

    system = platform.system()
    home = Path.home()

    if system == "Darwin":  # macOS
        app_dir = home / "Library" / "Application Support" / "netdecker"
    elif system == "Windows":
        # Use APPDATA environment variable, fallback to home

        appdata = os.environ.get("APPDATA")
        if appdata:
            app_dir = Path(appdata) / "netdecker"
        else:
            app_dir = home / "AppData" / "Roaming" / "netdecker"
    else:  # Linux and other Unix-like systems
        # Follow XDG Base Directory Specification

        xdg_data_home = os.environ.get("XDG_DATA_HOME")
        if xdg_data_home:
            app_dir = Path(xdg_data_home) / "netdecker"
        else:
            app_dir = home / ".local" / "share" / "netdecker"

    # Create directory if it doesn't exist
    app_dir.mkdir(parents=True, exist_ok=True)
    return app_dir


# Get the application data directory and database path
APP_DATA_DIR = get_app_data_dir()
DB_PATH = APP_DATA_DIR / "proxy.db"
DB_CONNECTION_STRING = f"sqlite:///{DB_PATH}"


def setup_logger() -> logging.Logger:
    logger = logging.getLogger("netdecker")
    logger.setLevel(logging.INFO)  # Set this to the desired level

    # Create handlers
    c_handler = logging.StreamHandler(sys.stdout)
    log_file = APP_DATA_DIR / "netdecker.log"
    f_handler = logging.FileHandler(log_file)
    c_handler.setLevel(logging.INFO)  # Console handler level
    f_handler.setLevel(logging.DEBUG)  # File handler level

    # Create formatters and add it to handlers
    log_format = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )
    c_handler.setFormatter(log_format)
    f_handler.setFormatter(log_format)

    # Add handlers to the logger
    logger.addHandler(c_handler)
    logger.addHandler(f_handler)

    return logger


LOGGER: Final[logging.Logger] = setup_logger()
