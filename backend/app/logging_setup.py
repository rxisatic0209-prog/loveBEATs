from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import settings


LOG_FORMAT = "%(asctime)s | %(levelname)s | %(name)s | %(message)s"


def setup_logging() -> None:
    root_logger = logging.getLogger()
    app_logger = logging.getLogger("pulseagent")

    if getattr(setup_logging, "_configured", False):
        return

    log_dir = Path(settings.log_dir).expanduser()
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / settings.log_filename

    formatter = logging.Formatter(LOG_FORMAT)
    log_level = _resolve_log_level(settings.log_level)

    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    console_handler.setLevel(log_level)

    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=settings.log_max_bytes,
        backupCount=settings.log_backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)
    file_handler.setLevel(log_level)

    root_logger.handlers.clear()
    root_logger.setLevel(log_level)
    root_logger.addHandler(console_handler)
    root_logger.addHandler(file_handler)

    app_logger.info("logging configured")
    app_logger.info("log file: %s", log_file)
    setup_logging._configured = True


def get_logger(name: str) -> logging.Logger:
    setup_logging()
    return logging.getLogger(name)


def _resolve_log_level(value: str) -> int:
    level_name = value.upper().strip()
    return getattr(logging, level_name, logging.INFO)
