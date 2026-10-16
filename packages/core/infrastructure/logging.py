import logging
import sys
from logging.handlers import RotatingFileHandler

from packages.core.infrastructure.config import Config

# Enable VT100 ANSI escape sequences on Windows if running in terminal
if sys.platform == "win32":
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        kernel32.SetConsoleMode(kernel32.GetStdHandle(-11), 7)
    except Exception:
        pass


class ColoredFormatter(logging.Formatter):
    """
    Custom log formatter that adds ANSI colors to log level badges for stdout stream handlers.
    Unified format: 2026-08-11 09:15:00,123 [INFO] backend.investments - Message...
    """
    COLOR_MAP = {
        logging.DEBUG: "\033[36m",      # Cyan
        logging.INFO: "\033[32m",       # Green
        logging.WARNING: "\033[33m",    # Yellow
        logging.ERROR: "\033[31m",      # Red
        logging.CRITICAL: "\033[1;31m", # Bold Red
    }
    RESET = "\033[0m"
    BOLD = "\033[1m"

    def __init__(self, fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s", datefmt=None, use_color=True):
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.use_color = use_color

    def format(self, record):
        if not self.use_color:
            return super().format(record)

        orig_levelname = record.levelname
        color = self.COLOR_MAP.get(record.levelno, self.RESET)
        record.levelname = f"{color}{self.BOLD}{orig_levelname}{self.RESET}"
        res = super().format(record)
        record.levelname = orig_levelname
        return res


class LoggingManager:
    _instance = None
    _initialized = False

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(LoggingManager, cls).__new__(cls)
        return cls._instance

    def __init__(self):
        if self._initialized:
            return

        # Ensure config is initialized to have paths
        Config.initialize()

        self.log_file = Config.APP_LOG_FILE
        log_level_str = Config.LOG_LEVEL
        self.log_level = getattr(logging, log_level_str, logging.INFO)

        root_logger = logging.getLogger()
        root_logger.setLevel(self.log_level)

        # Clear existing handlers to avoid duplicates if re-initialized
        if root_logger.hasHandlers():
            root_logger.handlers.clear()

        uncolored_formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
        colored_formatter = ColoredFormatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")

        # Ensure directory exists
        self.log_file.parent.mkdir(parents=True, exist_ok=True)

        # File Handler (uncolored for clean log file storage)
        file_handler = RotatingFileHandler(
            self.log_file,
            maxBytes=10*1024*1024,  # 10MB
            backupCount=5
        )
        file_handler.setFormatter(uncolored_formatter)
        root_logger.addHandler(file_handler)

        # Stream Handler (Stdout with ANSI colors)
        stream_handler = logging.StreamHandler(sys.stdout)
        stream_handler.setFormatter(colored_formatter)
        root_logger.addHandler(stream_handler)

        LoggingManager._initialized = True

    @classmethod
    def get_logger(cls, name: str):
        if not cls._initialized:
            cls()
        return logging.getLogger(name)


def get_logger(name: str):
    """Convenience function to get a logger with unified colored formatting."""
    return LoggingManager.get_logger(name)


def setup_colored_logging(logger_name: str = None, level=logging.INFO):
    """Utility function to attach colored formatting to any logger."""
    lg = logging.getLogger(logger_name) if logger_name else logging.getLogger()
    lg.setLevel(level)
    colored_fmt = ColoredFormatter("%(asctime)s [%(levelname)s] %(name)s - %(message)s")
    for h in lg.handlers:
        if isinstance(h, logging.StreamHandler) and not isinstance(h, RotatingFileHandler):
            h.setFormatter(colored_fmt)
    return lg

