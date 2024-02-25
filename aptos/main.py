import asyncio
import os

from web3db import DBHelper
from web3db.models import Profile

from aptos.client import Client
from utils import read_json

db = DBHelper(os.getenv('CONNECTION_STRING'))


async def buy(client: Client, payload):
    while True:
        await client.send_transaction(payload)


async def main():
    payload = read_json('payload.json')
    tasks = []
    profiles = await db.get_all_from_table(Profile)
    for profile in profiles:
        client = Client(profile)
        tasks.append(asyncio.create_task(buy(client, payload)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
