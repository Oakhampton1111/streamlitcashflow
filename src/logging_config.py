"""
Central logging configuration: outputs JSON logs to stdout.
Fields: timestamp, level, logger, function, message, exception (if any).
Level: default INFO, override via LOG_LEVEL env var.
"""

import logging
import os
import sys
import json
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    """Formatter that outputs log records in JSON format.

    The JSON log record includes the following fields:
    timestamp (ISO8601 UTC), level, logger, function, message,
    and exception (if any).
    """

    def format(self, record):
        log_record = {
            "timestamp": datetime.fromtimestamp(record.created, tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "function": record.funcName,
            "message": record.getMessage(),
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return json.dumps(log_record)


def configure_logging():
    """Configure the root logger to output JSON logs to stdout.

    Sets the log level based on the LOG_LEVEL environment variable (default INFO).
    Adds a StreamHandler to stdout with the JsonFormatter.

    Returns:
        None
    """
    level_name = os.getenv("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, None)
    if not isinstance(level, int):
        level = logging.INFO
    root = logging.getLogger()
    if not root.handlers:
        root.setLevel(level)
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(level)
        handler.setFormatter(JsonFormatter())
        root.addHandler(handler)


def get_logger(name: str) -> logging.Logger:
    """Get a logger configured to output JSON logs to stdout.

    Args:
        name (str): Name of the logger.

    Returns:
        logging.Logger: Configured logger instance.
    """
    configure_logging()
    return logging.getLogger(name)
