from __future__ import annotations

import logging
from typing import Any


_LOGGER: logging.Logger | None = None


def _get_logger() -> logging.Logger:
    global _LOGGER
    if _LOGGER is not None:
        return _LOGGER
    logger = logging.getLogger("dc_cut")
    if not logger.handlers:
        logger.setLevel(logging.INFO)
        handler = logging.StreamHandler()
        fmt = logging.Formatter("[%(levelname)s] %(message)s")
        handler.setFormatter(fmt)
        logger.addHandler(handler)
        try:
            logger.propagate = False
        except Exception:
            pass
    _LOGGER = logger
    return logger


def info(msg: str, *args: Any, **kwargs: Any) -> None:
    _get_logger().info(msg, *args, **kwargs)


def warn(msg: str, *args: Any, **kwargs: Any) -> None:
    _get_logger().warning(msg, *args, **kwargs)


def error(msg: str, *args: Any, **kwargs: Any) -> None:
    _get_logger().error(msg, *args, **kwargs)











