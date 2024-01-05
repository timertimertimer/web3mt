import sys
from loguru import logger


def error_filter(record):
    return record["level"].name in ["ERROR", "CRITICAL"]


def not_error_filter(record):
    return record["level"].name not in ["ERROR", "CRITICAL"]


logger.remove()
format_string = "<white>{time:HH:mm:ss}</white> | <level>{level: <8}</level> | <level>{message}</level>"
logger.add(sys.stderr, format=format_string)
logger.add("errors.log", filter=error_filter, format=format_string)
logger.add("general.log", filter=not_error_filter, format=format_string)

__all__ = ["logger"]
