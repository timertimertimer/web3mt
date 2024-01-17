import os
from pathlib import Path

CWD = Path(__file__).parent
DATA_PATH = CWD / 'data'
if not DATA_PATH.exists():
    DATA_PATH.mkdir()
    for file in ['discords.txt', 'twitters.txt', 'emails.txt', 'proxies.txt']:
        DATA_PATH.joinpath(file).touch()
DATA_FILES = os.listdir(DATA_PATH)

__all__ = [
    'DATA_PATH',
    'DATA_FILES'
]
