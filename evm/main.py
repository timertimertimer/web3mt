import asyncio
import os
from dotenv import load_dotenv

from web3db import DBHelper
from eth_account import Account

from client import Client
from models import opBNB, BNB
from utils import get_accounts
from evm.examples import have_balance, opbnb_bridge

Account.enable_unaudited_hdwallet_features()
load_dotenv()
db = DBHelper(os.getenv('CONNECTION_STRING'))


async def main():
    wallets = get_accounts()
    for account in wallets:
        opBNB_client = Client(account, opBNB)
        BNB_client = Client(account, BNB)
        if await have_balance(opBNB_client, 0.001, echo=True):
            continue
        await opbnb_bridge(account)


if __name__ == '__main__':
    asyncio.run(main())
