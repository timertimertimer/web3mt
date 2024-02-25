import os
import sys
from pathlib import Path

from utils import read_json

if getattr(sys, 'frozen', False):
    ROOT_DIR = Path(sys.executable).parent.absolute()
else:
    ROOT_DIR = Path(__file__).parent.absolute()

ABIS_DIR = ROOT_DIR / 'abis'
TOKEN_ABI = read_json(ABIS_DIR / 'erc-20.json')

REIKI_ABI_PATH = os.path.join(ABIS_DIR, 'reiki.json')
LXP_ABI_PATH = os.path.join(ABIS_DIR, 'lxp.json')
OPBNB_BRIDGE_ABI_PATH = os.path.join(ABIS_DIR, 'opbnb_bridge.json')
HYPERCOMIC_ABI_PATH = os.path.join(ABIS_DIR, 'hypercomic.json')
