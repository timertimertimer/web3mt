import sys
from pathlib import Path

from web3mt.utils.file_manager import FileManager

if getattr(sys, 'frozen', False):
    ROOT_DIR = Path(sys.executable).parent.absolute()
else:
    ROOT_DIR = Path(__file__).parent.absolute()

abis = FileManager.read_json(ROOT_DIR / 'abi.json')
