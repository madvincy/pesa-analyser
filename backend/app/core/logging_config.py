# app/core/logging_config.py
"""
Logging configuration for the FastAPI application.
"""

import logging
import sys
import os
from typing import Optional


# ANSI color codes for terminal output
class Colors:
    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    GRAY = "\033[90m"


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for terminal output."""

    COLORS = {
        logging.DEBUG: Colors.GRAY,
        logging.INFO: Colors.GREEN,
        logging.WARNING: Colors.YELLOW,
        logging.ERROR: Colors.RED,
        logging.CRITICAL: Colors.MAGENTA,
    }

    def format(self, record):
        color = self.COLORS.get(record.levelno, Colors.WHITE)
        # Add color to levelname
        record.levelname = f"{color}{record.levelname}{Colors.RESET}"
        return super().format(record)


def setup_logging(
    level: Optional[str] = None,
    format_string: Optional[str] = None,
    colored: bool = True,
) -> None:
    """
    Set up logging configuration for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        format_string: Custom log format string
        colored: Whether to use colored output
    """
    # Get log level from environment or use default
    if level is None:
        level = os.getenv("LOG_LEVEL", "INFO")

    if format_string is None:
        format_string = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"

    # Create handler
    handler = logging.StreamHandler(sys.stdout)

    # Use colored formatter if enabled
    if colored and sys.stdout.isatty():
        formatter = ColoredFormatter(format_string)
    else:
        formatter = logging.Formatter(format_string)

    handler.setFormatter(formatter)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, level.upper()))

    # Remove existing handlers to avoid duplicates
    for h in root_logger.handlers[:]:
        root_logger.removeHandler(h)

    root_logger.addHandler(handler)

    # Set specific log levels for third-party libraries
    logging.getLogger("uvicorn").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy").setLevel(logging.WARNING)
    logging.getLogger("pdfplumber").setLevel(logging.WARNING)
    logging.getLogger("PyPDF2").setLevel(logging.WARNING)

    # Set our app loggers to appropriate levels
    if level.upper() == "DEBUG":
        logging.getLogger("app").setLevel(logging.DEBUG)
        logging.getLogger("mpesa_analyzer").setLevel(logging.DEBUG)
        # Also set the upload router to DEBUG
        logging.getLogger("app.routers.upload").setLevel(logging.DEBUG)
    else:
        logging.getLogger("app").setLevel(logging.INFO)
        logging.getLogger("mpesa_analyzer").setLevel(logging.INFO)

    logger = logging.getLogger(__name__)
    logger.info(f"✅ Logging configured with level: {level}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with the given name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
