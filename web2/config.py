import os
from pathlib import Path

CWD = Path(__file__).parent
DATA_PATH = CWD / 'data'
DATA_FILES = os.listdir(DATA_PATH)

__all__ = [
    'DATA_PATH',
    'DATA_FILES'
]
