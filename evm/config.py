import os
import sys
from pathlib import Path

if getattr(sys, 'frozen', False):
    ROOT_DIR = Path(sys.executable).parent.absolute()
else:
    ROOT_DIR = Path(__file__).parent.absolute()

ABIS_DIR = os.path.join(ROOT_DIR, 'abis')

REIKI_ABI = os.path.join(ABIS_DIR, 'reiki.json')

private_key = ''
seed = ''
eth_rpc = 'https://mainnet.infura.io/v3/'
