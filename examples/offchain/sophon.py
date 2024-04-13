import os
import asyncio

from curl_cffi.requests import RequestsError
from web3db import DBHelper, Profile
from dotenv import load_dotenv

from web3mt.evm.client import Client
from web3mt.utils import ProfileSession, logger, sleep

load_dotenv()


async def register(profile: Profile):
    api = 'https://sophon.xyz/api'
    headers = {
        'Origin': 'https://sophon.xyz',
        'Referer': 'https://sophon.xyz/'
    }
    client = Client(profile=profile)
    async with ProfileSession(profile, headers=headers, sleep_echo=False) as session:
        while True:
            try:
                response, data = await session.get(f'{api}/users/{profile.evm_address}')
                break
            except RequestsError as e:
                payload = {
                    'address': profile.evm_address.strip(),
                    'signature': client.sign('Sophon is leading us all towards a brighter future.')
                }
                response, data = await session.post(f'{api}/users/register', json=payload)
        if not data['hasTweeted']:
            response, data = await session.post(f'{api}/tweet', json={'address': profile.evm_address.strip()})
            logger.success(f'{profile.id} | {data}')
            return False
        else:
            return True


async def main():
    db = DBHelper(os.getenv('CONNECTION_STRING'))
    profiles: list[Profile] = await db.get_all_from_table(Profile)
    for profile in profiles:
        if not await register(profile):
            await sleep(30, 60, echo=False)


if __name__ == "__main__":
    asyncio.run(main())
