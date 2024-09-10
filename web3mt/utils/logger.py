import sys
from loguru import logger
from pathlib import Path

MAIN_DIR = Path(__file__).parent.parent.parent / 'logs'
if not Path.exists(MAIN_DIR):
    MAIN_DIR.mkdir()


class Logger:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        self.logger = logger
        self.logger.remove()
        format_string = (
            "<white>{time:YYYY-MM-DD HH:mm:ss}</white> | <level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
        log_configs = [
            ('success.log', ['SUCCESS']),
            ('info.log', ['INFO', 'DEBUG']),
            ('error.log', ['ERROR', 'CRITICAL', 'WARNING'])
        ]
        for filename, levels in log_configs:
            self.logger.add(
                MAIN_DIR / filename,
                rotation="500 MB",
                filter=lambda record, levels=levels: record["level"].name in levels,
                format=format_string
            )
        self.logger.add(sys.stderr, format=format_string)

    def __getattr__(self, name):
        return getattr(self.logger, name)


my_logger = Logger()
__all__ = ["my_logger"]
