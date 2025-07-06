import sys
from pathlib import Path
from loguru import logger as loguru_logger


class Logger:
    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, logs_dir_path: str = 'logs'):
        self._logs_dir_path = Path(__file__).parent / logs_dir_path
        self._file_handlers = []
        self.logger = loguru_logger
        self.logger.remove()
        self._setup_handlers()
        format_string = (
            "<white>{time:YYYY-MM-DD HH:mm:ss}</white> | <level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
        self.logger.add(sys.stderr, format=format_string)

    def _setup_handlers(self):
        self._logs_dir_path.mkdir(parents=True, exist_ok=True)

        format_string = (
            "<white>{time:YYYY-MM-DD HH:mm:ss}</white> | <level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
        log_configs = [
            ('success.log', ['SUCCESS']),
            ('info.log', ['INFO', 'DEBUG', 'TRACE', 'WARNING']),
            ('error.log', ['ERROR', 'CRITICAL']),
        ]
        for filename, levels in log_configs:
            path = self._logs_dir_path / filename
            handler_id = self.logger.add(
                path,
                rotation="500 MB",
                filter=lambda record, levels=levels: record["level"].name in levels,
                format=format_string
            )
            self._file_handlers.append(handler_id)
        handler_id = self.logger.add(
            self._logs_dir_path / 'all.log',
            rotation="500 MB",
            format=format_string
        )
        self._file_handlers.append(handler_id)

    def __getattr__(self, name):
        return getattr(self.logger, name)

    @property
    def logs_dir_path(self) -> Path:
        return self._logs_dir_path

    @logs_dir_path.setter
    def logs_dir_path(self, value: str):
        new_path = Path(value)
        for handler_id in self._file_handlers:
            self.logger.remove(handler_id)
        self._file_handlers.clear()
        self._logs_dir_path = new_path
        self._setup_handlers()


logger = Logger()

__all__ = ['logger']