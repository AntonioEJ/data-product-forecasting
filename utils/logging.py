"""
Centralized structured logging configuration for data-product-forecasting.

Designed for AWS CloudWatch compatibility.
"""

import logging
import sys
from typing import Optional

LOG_FORMAT = (
    "%(asctime)s | %(levelname)s | %(name)s | %(module)s | %(message)s"
)

_LOGGER_INITIALIZED = False


def setup_logging(level: int = logging.INFO) -> None:
    """
    Configure root logger for structured logging.

    Ensures logs are compatible with AWS CloudWatch and avoids duplicate setup.

    Args:
        level (int): Logging level (default: INFO).
    """
    global _LOGGER_INITIALIZED

    if _LOGGER_INITIALIZED:
        return

    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    formatter = logging.Formatter(LOG_FORMAT)
    handler.setFormatter(formatter)

    root_logger.handlers.clear()
    root_logger.addHandler(handler)

    # Reduce noise from AWS SDK
    logging.getLogger("boto3").setLevel(logging.WARNING)
    logging.getLogger("botocore").setLevel(logging.WARNING)

    root_logger.info(
        "Logging initialized | level=%s",
        logging.getLevelName(level),
    )

    _LOGGER_INITIALIZED = True


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance with consistent configuration.

    Args:
        name (Optional[str]): Logger name (typically __name__).

    Returns:
        logging.Logger: Configured logger.
    """
    return logging.getLogger(name)