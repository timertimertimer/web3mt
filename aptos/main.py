import asyncio
import os

from web3db import DBHelper
from web3db.models import Profile

from aptos.examples import check_v1_token_ownership

db = DBHelper(os.getenv('CONNECTION_STRING'))


async def main():
    tasks = []
    profiles = await db.get_all_from_table(Profile)
    for profile in profiles:
        tasks.append(asyncio.create_task(check_v1_token_ownership(profile)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
