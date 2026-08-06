"""Structured logging via structlog.

Attaches a correlation id to every log line so a single user request can be
followed across the API, workers, and agent graph.
"""

import logging
from typing import Any

import structlog

from app.config import Settings


def configure_logging(settings: Settings) -> None:
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
    )
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(min_level=getattr(logging, settings.log_level.upper(), 20)),
        cache_logger_on_first_use=True,
    )


class Logger:
    """Convenience wrapper; prefer structlog.get_logger() directly in modules."""

    def __init__(self, name: str | None = None) -> None:
        self._logger = structlog.get_logger(name)

    def info(self, event: str, **kw: Any) -> None:
        self._logger.info(event, **kw)

    def error(self, event: str, **kw: Any) -> None:
        self._logger.error(event, **kw)

    def warning(self, event: str, **kw: Any) -> None:
        self._logger.warning(event, **kw)

    def debug(self, event: str, **kw: Any) -> None:
        self._logger.debug(event, **kw)


get_logger = structlog.get_logger