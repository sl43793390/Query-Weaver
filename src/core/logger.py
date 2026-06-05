"""Centralized logging using loguru.

A rotating file is created under `logs/`, and errors are also written to the
console for development visibility.
"""
from __future__ import annotations

import sys

from loguru import logger

from config.settings import LOG_LEVEL, LOG_RETENTION, LOG_ROTATION, LOGS_DIR


def setup_logger() -> None:
    """Initialize the global loguru logger.

    Safe to call multiple times — loguru de-duplicates handlers.
    """
    logger.remove()

    # Console (development)
    logger.add(
        sys.stderr,
        level=LOG_LEVEL,
        format=(
            "<green>{time:HH:mm:ss}</green> | "
            "<level>{level: <7}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
    )

    # Rotating file
    logger.add(
        LOGS_DIR / "app.log",
        level=LOG_LEVEL,
        rotation=LOG_ROTATION,
        retention=LOG_RETENTION,
        encoding="utf-8",
        enqueue=True,
    )


__all__ = ["logger", "setup_logger"]
