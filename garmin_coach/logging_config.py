from __future__ import annotations

import logging
import os
import sys
from typing import Any

try:
    import logfire as _logfire_module
except ImportError:
    _logfire_module = None


_LOG_FORMAT = "%(asctime)s %(levelname)s [%(name)s] %(message)s"

_root_logger = logging.getLogger("garmin_coach")
if not _root_logger.handlers:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(logging.Formatter(_LOG_FORMAT))
    _root_logger.addHandler(handler)
_root_logger.setLevel(logging.INFO)
_root_logger.propagate = False


def _configure_logfire() -> None:
    if _logfire_module is None:
        return

    try:
        token = os.getenv("LOGFIRE_TOKEN")
        if token:
            _logfire_module.configure(token=token)
        else:
            _logfire_module.configure(send_to_logfire=False)
    except Exception:
        _root_logger.debug("logfire configuration failed", exc_info=True)


_configure_logfire()


def _emit_to_logfire(level: str, message: str, **context: Any) -> None:
    if _logfire_module is None:
        return

    try:
        logfire_fn = getattr(_logfire_module, level, None)
        if callable(logfire_fn):
            logfire_fn(message, **context)
    except Exception:
        _root_logger.debug("logfire emit failed", exc_info=True)


def get_logger(name: str | None = None) -> logging.Logger:
    return _root_logger if not name else _root_logger.getChild(name)


logger = get_logger()
std_logger = logger


def log_info(message: str, **context: Any) -> None:
    logger.info(message)
    _emit_to_logfire("info", message, **context)


def log_warning(message: str, exc: Exception | None = None, **context: Any) -> None:
    if exc is not None:
        logger.warning("%s: %s: %s", message, type(exc).__name__, exc)
        context = {**context, "exception_type": type(exc).__name__, "exception": str(exc)}
    else:
        logger.warning(message)
    _emit_to_logfire("warning", message, **context)


def log_error(message: str, exc: Exception | None = None, **context: Any) -> None:
    if exc is not None:
        logger.error("%s: %s: %s", message, type(exc).__name__, exc, exc_info=exc)
        context = {**context, "exception_type": type(exc).__name__, "exception": str(exc)}
    else:
        logger.error(message)
    _emit_to_logfire("error", message, **context)


def log_debug(message: str, **context: Any) -> None:
    logger.debug(message)
    _emit_to_logfire("debug", message, **context)


__all__ = [
    "get_logger",
    "log_debug",
    "log_error",
    "log_info",
    "log_warning",
    "logger",
    "std_logger",
]
