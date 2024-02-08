import asyncio
import os
from dotenv import load_dotenv

from web3db import DBHelper
from eth_account import Account

from client import Client
from models import opBNB
from utils import get_accounts
from evm.examples import have_balance, opbnb_bridge

Account.enable_unaudited_hdwallet_features()
load_dotenv()
db = DBHelper(os.getenv('CONNECTION_STRING'))


async def main():
    wallets = get_accounts()
    for account in wallets:
        client = Client(account, opBNB)
        if await have_balance(client, 0.002):
            continue
        print(await opbnb_bridge(account))


if __name__ == '__main__':
    asyncio.run(main())
