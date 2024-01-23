import asyncio
import os

from eth_account import Account
from web3db import DBHelper
from web3db.utils import decrypt

from client import Client
from models import BNB

from dotenv import load_dotenv

load_dotenv()


async def check_balance_batch():
    db = DBHelper(os.getenv('CONNECTION_STRING'))
    profiles = await db.get_random_profiles_by_proxy_distinct()
    tasks = []
    for profile in profiles:
        client = Client(Account.from_key(decrypt(profile.evm_private, os.getenv('PASSPHRASE'))), BNB)
        tasks.append(asyncio.create_task(client.get_native_balance()))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(check_balance_batch())
