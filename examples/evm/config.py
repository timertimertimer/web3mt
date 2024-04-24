import sys
from pathlib import Path

from web3mt.utils import read_json

if getattr(sys, 'frozen', False):
    ROOT_DIR = Path(sys.executable).parent.absolute()
else:
    ROOT_DIR = Path(__file__).parent.absolute()

abis = read_json(ROOT_DIR / 'abi.json')
OPBNB_BRIDGE_ABI = abis['opbnb_bridge']
