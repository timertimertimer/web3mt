import asyncio

from config import GONE_ABI
from client import Client
from models import Polygon
from utils import get_accounts, read_json

gone_contract_address = '0x162539172b53E9a93b7d98Fb6c41682De558a320'


async def main():
    accounts = get_accounts()
    tasks = []
    for account in accounts[:1]:
        client = Client(account, Polygon)
        client.default_abi = read_json(GONE_ABI)
        tasks.append(asyncio.create_task(client.balance_of(gone_contract_address)))
    results = await asyncio.gather(*tasks)
    print('\n'.join(map(str, results)))


if __name__ == '__main__':
    asyncio.run(main())
