import asyncio
import os

from web3db import DBHelper
from web3db.models import Profile

from utils import ProfileSession, logger


async def join_waitlist(profile: Profile):
    async with ProfileSession(profile) as session:
        url = 'https://www.fuel.domains/api/domain'
        response, data = await session.request(method='POST', url=url, json={'email': profile.email.login})
        logger.success(f'{profile.id} | {profile.email.login} | {data}')


async def main():
    db = DBHelper(os.getenv('CONNECTION_STRING'))
    profiles: list[Profile] = await db.get_all_from_table(Profile)
    tasks = []
    for profile in profiles:
        tasks.append(asyncio.create_task(join_waitlist(profile)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
