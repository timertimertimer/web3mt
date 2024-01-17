import asyncio

from client import Client
from models import BNB
from utils import get_accounts


async def main():
    accounts = get_accounts()
    tasks = []
    for account in accounts:
        client = Client(account, BNB)
        tasks.append(asyncio.create_task(client.get_native_balance()))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
