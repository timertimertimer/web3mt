import asyncio
import os

from config import read_config, ABIS_DIR
from logger import logger
from web3 import Web3
from utils import (
    get_web3, get_accounts, get_address,
    get_gwei, get_nonce, get_chain_id,
    PRICE_FACTOR, INCREASE_GAS, read_json
)
from client import Client
from models import BNB

aw20_contract = '0x403bAC110F91F1bA4c427F4BF1c3A7cb334E8c27'
data = '0x7b2270223a2261772d32302d6e6577222c226f70223a226d696e74222c227469636b223a226553706f727473222c22616d74223a2231303030227d'


async def main():
    account = get_accounts()[0]
    AW20_ABI = read_json(os.path.join(ABIS_DIR, 'aw20.json'))
    Client.default_abi = AW20_ABI
    client = Client(account, BNB)
    while True:
        res = await client.send_transaction(
            to=aw20_contract,
            data=data,
            increase_gas=INCREASE_GAS,
            max_priority_fee_per_gas=3000000000,
        )
        logger.info(res)


if __name__ == '__main__':
    asyncio.run(main())
