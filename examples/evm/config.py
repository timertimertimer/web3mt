import sys
from pathlib import Path

from web3mt.utils import read_json

if getattr(sys, 'frozen', False):
    ROOT_DIR = Path(sys.executable).parent.absolute()
else:
    ROOT_DIR = Path(__file__).parent.absolute()

ABIS_DIR = ROOT_DIR / 'abis'

abis = read_json(ABIS_DIR / 'abi.json')
OPBNB_BRIDGE_ABI = abis['opbnb_bridge']
