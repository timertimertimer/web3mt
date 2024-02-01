import asyncio
import os

from eth_account import Account
from web3db import DBHelper
from web3db.models import Profile
from web3db.utils import decrypt

from logger import logger
from client import Client
from evm.config import LXP_ABI_PATH
from models import Network, Linea, opBNB

from dotenv import load_dotenv

from utils import read_json

load_dotenv()

db = DBHelper(os.getenv('CONNECTION_STRING'))


async def check_balance_batch(network: Network):
    profiles = await db.get_all_from_table(Profile)
    tasks = []
    for profile in profiles:
        client = Client(Account.from_key(decrypt(profile.evm_private, os.getenv('PASSPHRASE'))), network)
        tasks.append(asyncio.create_task(client.get_native_balance()))


async def check_xp_linea():
    lxp_contract_address = '0xd83af4fbD77f3AB65C3B1Dc4B38D7e67AEcf599A'
    profiles = await db.get_all_from_table(Profile)
    tasks = []
    for profile in profiles:
        client = Client(Account.from_key(decrypt(profile.evm_private, os.getenv('PASSPHRASE'))), Linea)
        client.default_abi = read_json(LXP_ABI_PATH)
        tasks.append(asyncio.create_task(client.balance_of(lxp_contract_address)))
    result = await asyncio.gather(*tasks)
    logger.success(f'Total - {sum([el.Ether for el in result])} LXP')


async def have_balance(client: Client):
    balance = await client.get_native_balance()
    if balance.Wei > 0:
        logger.success(f'{client.account.address} | Balance: {balance.Wei} {client.network.coin_symbol}')
        return client
    return False


async def get_wallets_with_balance(network: Network):
    profiles = await db.get_all_from_table(Profile)
    tasks = []
    for profile in profiles:
        client = Client(Account.from_key(decrypt(profile.evm_private, os.getenv('PASSPHRASE'))), network)
        tasks.append(asyncio.create_task(have_balance(client)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(get_wallets_with_balance(opBNB))
