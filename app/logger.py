"""Comprehensive logging system for StreamPortal API using uvicorn logger."""

import json
import logging
from typing import Any, Optional


class StreamPortalLogger:
    """Main logger class for StreamPortal API using uvicorn logger."""

    def __init__(self, name: str = "streamportal", log_level: str = "INFO") -> None:
        """Initialize StreamPortalLogger.

        Args:
            name: Logger name
            log_level: Logging level
        """
        self.name = name
        self.log_level = getattr(logging, log_level.upper())

        # Use uvicorn's logger as base
        self.logger = logging.getLogger("uvicorn.error")
        self.logger.setLevel(self.log_level)

    def _log_with_extra(
        self, level: int, message: str, extra_fields: Optional[dict[str, Any]] = None
    ) -> None:
        """Log with extra structured fields."""
        if extra_fields:
            # Format extra fields as JSON and append to message
            extra_json = json.dumps(extra_fields, ensure_ascii=False)
            formatted_message = f"{message} | {extra_json}"
            self.logger.log(level, formatted_message)
        else:
            self.logger.log(level, message)

    def info(self, message: str, extra_fields: Optional[dict[str, Any]] = None) -> None:
        """Log info message."""
        self._log_with_extra(logging.INFO, message, extra_fields)

    def warning(
        self, message: str, extra_fields: Optional[dict[str, Any]] = None
    ) -> None:
        """Log warning message."""
        self._log_with_extra(logging.WARNING, message, extra_fields)

    def error(
        self, message: str, extra_fields: Optional[dict[str, Any]] = None
    ) -> None:
        """Log error message."""
        self._log_with_extra(logging.ERROR, message, extra_fields)

    def critical(
        self, message: str, extra_fields: Optional[dict[str, Any]] = None
    ) -> None:
        """Log critical message."""
        self._log_with_extra(logging.CRITICAL, message, extra_fields)

    def debug(
        self, message: str, extra_fields: Optional[dict[str, Any]] = None
    ) -> None:
        """Log debug message."""
        self._log_with_extra(logging.DEBUG, message, extra_fields)

    def exception(
        self, message: str, extra_fields: Optional[dict[str, Any]] = None
    ) -> None:
        """Log exception with traceback."""
        if extra_fields:
            # Format extra fields as JSON and append to message
            extra_json = json.dumps(extra_fields, ensure_ascii=False)
            formatted_message = f"{message} | {extra_json}"
            self.logger.exception(formatted_message)
        else:
            self.logger.exception(message)


# Global logger instance using uvicorn logger
logger = StreamPortalLogger()


def get_logger(name: Optional[str] = None) -> StreamPortalLogger:
    """Get logger instance."""
    if name:
        return StreamPortalLogger(name)
    return logger


# Also provide direct access to uvicorn logger for compatibility
uvicorn_logger = logging.getLogger("uvicorn.error")
