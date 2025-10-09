import logging
import os
import sys
from datetime import datetime

from src.utils.config import LOG_DIR, LOG_FILE


class AnsiColor:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    # colors
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"


class ColorFormatter(logging.Formatter):
    LEVEL_TO_COLOR = {
        logging.DEBUG: AnsiColor.DIM + AnsiColor.CYAN,
        logging.INFO: AnsiColor.GREEN,
        logging.WARNING: AnsiColor.YELLOW,
        logging.ERROR: AnsiColor.RED,
        logging.CRITICAL: AnsiColor.BOLD + AnsiColor.RED,
    }

    def format(self, record: logging.LogRecord) -> str:
        ts = datetime.fromtimestamp(record.created).strftime("%Y-%m-%d %H:%M:%S")
        level_color = self.LEVEL_TO_COLOR.get(record.levelno, "")
        reset = AnsiColor.RESET
        # Example: [2025-10-09 12:34:56] [FaceRecog] INFO - message
        prefix = f"[{ts}] [{record.name}] {record.levelname}"
        if sys.stderr.isatty() or sys.stdout.isatty():
            prefix = f"{level_color}{prefix}{reset}"
        msg = super().format(record)
        return f"{prefix} - {msg}"


def get_logger(name: str = "ai-guard") -> logging.Logger:
    logger = logging.getLogger(name)
    if getattr(logger, "_initialized", False):
        return logger

    logger.setLevel(logging.DEBUG)
    os.makedirs(LOG_DIR, exist_ok=True)

    # Console handler with colors
    ch = logging.StreamHandler(stream=sys.stdout)
    ch.setLevel(logging.DEBUG)
    ch.setFormatter(ColorFormatter("%(message)s"))

    # File handler without ANSI colors (plain text)
    fh = logging.FileHandler(LOG_FILE, encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(logging.Formatter("[%(asctime)s] [%(name)s] %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"))

    logger.addHandler(ch)
    logger.addHandler(fh)
    logger._initialized = True
    return logger


# Convenience category loggers for subsystems
def get_face_logger() -> logging.Logger:
    return get_logger("FaceRecog")

def get_asr_logger() -> logging.Logger:
    return get_logger("ASR")

def get_state_logger() -> logging.Logger:
    return get_logger("StateManager")



