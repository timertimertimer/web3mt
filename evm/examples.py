import asyncio
import os

from eth_account import Account
from web3db import DBHelper
from web3db.models import Profile
from web3db.utils import decrypt

from logger import logger
from client import Client
from evm.config import LXP_ABI_PATH, OPBNB_BRIDGE_ABI_PATH
from models import Network, Linea, opBNB, BNB, TokenAmount

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


async def have_balance(client: Client, ethers: float = 0.002, echo: bool = False) -> bool:
    if (await client.get_native_balance(echo=echo)).Ether > ethers:
        return True
    return False


async def get_wallets_with_balance(network: Network):
    profiles = await db.get_all_from_table(Profile)
    tasks = []
    for profile in profiles:
        client = Client(Account.from_key(decrypt(profile.evm_private, os.getenv('PASSPHRASE'))), network)
        tasks.append(asyncio.create_task(have_balance(client)))
    await asyncio.gather(*tasks)


async def opbnb_bridge(account: Account, amount: float = 0.002):
    if await have_balance(Client(account, opBNB)):
        return
    client = Client(account, BNB)
    contract_address = '0xF05F0e4362859c3331Cb9395CBC201E3Fa6757Ea'
    client.default_abi = read_json(OPBNB_BRIDGE_ABI_PATH)
    contract = client.w3.eth.contract(
        address=client.w3.to_checksum_address(contract_address),
        abi=client.default_abi
    )
    tx_hash = await client.send_transaction(
        to=contract_address,
        data=contract.encodeABI('depositETH', args=[1, b'']),
        value=TokenAmount(amount).Wei
    )
    if tx_hash:
        return tx_hash
    return False


if __name__ == '__main__':
    asyncio.run(get_wallets_with_balance(opBNB))
