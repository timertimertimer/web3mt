import sys
from loguru import logger
from pathlib import Path

MAIN_DIR = Path(__file__).parent.parent.parent


def error_filter(record):
    return record["level"].name in ["ERROR", "CRITICAL"]


def not_error_filter(record):
    return record["level"].name not in ["ERROR", "CRITICAL"]


logger.remove()
format_string = (
    "<white>{time:YYYY-MM-DD HH:mm:ss}</white> | <level>{level: <8}</level> | "
    "<cyan>{name}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
)
logger.add(sys.stderr, format=format_string)
logger.add(MAIN_DIR / "general.log", filter=not_error_filter, format=format_string)
logger.add(MAIN_DIR / "errors.log", filter=error_filter, format=format_string)

__all__ = ["logger"]
