import asyncio
import json
import random
from random import choice

import aiofiles
import pytz
from curl_cffi import CurlMime
from sqlalchemy import select
from web3db import Profile
from faker import Faker
from datetime import datetime, timedelta
from dateutil.parser import parse

from examples.dex.evm.cysic.db import CysicAccount, CONNECTION_STRING
from web3mt.dex.models import DEX
from web3mt.utils.db import create_db_instance
from web3mt.utils import logger, sleep
from examples.utils.other import photos_path, parse_date

fake = Faker()
chain_id = 9527
with open('codes.txt') as f:
    codes = set([l.strip() for l in f.readlines()])


async def get_random_photo():
    file = choice([f for f in photos_path.iterdir() if f.is_file()])
    async with aiofiles.open(file, 'rb') as f:
        return await f.read(), str(file.name)


class Cysic(DEX):
    API_URL = 'https://api-testnet.prover.xyz/api/v1'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.http_session.headers.update({
            'x-cysic-address': self.evm_client.account.address, 'x-cysic-sign': self.evm_client.sign('Welcome to Cysic！')
        })
        self.db_helper = create_db_instance(CONNECTION_STRING)

    async def profile(self):
        _, data = await self.http_session.get(f'{self.API_URL}/myPage/{self.evm_client.account.address}/profile')
        if data['msg'] == 'success':
            data = data["data"]
            logger.info(
                f'{self} | Username: {data["name"] or None}, '
                f'creation date: {parse_date(data["searchResult"]["WhitelistInfo"]["CreatedAt"])}'
            )
            return data
        elif data['msg'] == 'not in list':
            logger.warning(f'{self} | Not registered')
        else:
            pass

    async def check_code(self, code: str) -> bool:
        _, data = await self.http_session.get(f'{self.API_URL}/referral/check/{code}')
        return data['data']['exist']

    async def bind(self, code: str):
        if await self.check_code(code):
            _, data = await self.http_session.put(f'{self.API_URL}/referral/bind/{code}/{self.evm_client.account.address}')
            if data['msg'] == f'Invite Code Success: {code}':
                logger.success(f'{self} | {data["msg"]}')
                return True
            else:
                logger.warning(f'{self} | {data}')
                return False
        else:
            logger.warning(f'{self} | No such code')
            return False

    async def upload(self):
        file_data, name = await get_random_photo()
        mp = CurlMime()
        mp.addpart('file', content_type='multipart/form-data', filename=name, data=file_data)
        _, data = await self.http_session.post(f'{self.API_URL}/upload', multipart=mp)
        if data['msg'] == 'success':
            logger.success(f'{self} | Uploaded "{name}"')
            return data['data']

    async def register(self, code: str = None):
        profile_data = await self.profile()
        if not profile_data:
            if not code:
                logger.warning(f'{self} | Need code')
                return
            if not await self.bind(code):
                return
        if profile_data and profile_data.get('name'):
            logger.success(f'{self} | Already registered')
            return
        image = await self.upload()
        username = fake.profile(['username'])['username'][:12]
        logo = f'https://api-testnet.prover.xyz{image}'
        while True:
            timestamp = int(datetime.now().timestamp())
            headers = {
                'x-cysis-chain-id': str(chain_id),
                'x-cysis-signature': '0x' + self.evm_client.sign(
                    json.dumps({'name': username, 'logo': logo}) + str(chain_id) + str(timestamp)
                ),
                'x-cysic-timestamp': str(timestamp),
                'x-cysic-wallet': self.evm_client.account.address
            }
            data = {'claim_reward_address': self.evm_client.account.address, 'logo': logo, 'name': username}
            _, data = await self.http_session.post(f'{self.API_URL}/register', json=data, headers=headers)
            if data['msg'] == 'success':
                logger.success(f'{self} | Registered')
                creation_date = (await self.profile())["searchResult"]["WhitelistInfo"]["CreatedAt"]
                new_account = CysicAccount(
                    profile_id=self.evm_client.profile.id if getattr(self.evm_client, 'profile') else None,
                    address=self.evm_client.account.address,
                    name=username,
                    created_at=parse(creation_date)
                )
                await self.db_helper.add_record(new_account)
                break
            elif data['msg'] == 'name exist':
                logger.warning(f'{self} | Name {username} already exists')
                username = username[:-1] + str(random.randrange(10))
            else:
                pass
        return data

    async def _latest_claim_record(self, address: str):
        _, data = await self.http_session.get(f'{self.API_URL}/myPage/faucet/{address}/latestRecord')
        if data['msg'] == 'success':
            return data['data']
        else:
            logger.warning(f'{self} | {data}')

    async def claim_faucet(self):
        profile_data = await self.profile()
        cosmos_address = profile_data['cosmosAddress']
        latest_claim_record_data = await self._latest_claim_record(cosmos_address)
        if not latest_claim_record_data:
            return
        latest_claim_time_str = latest_claim_record_data['latestClaimTime']
        next_claim_datetime_with_tz = (parse(latest_claim_time_str) + timedelta(days=1)).replace(tzinfo=pytz.utc)
        time_to_wait = next_claim_datetime_with_tz - datetime.now(pytz.utc)
        if time_to_wait < timedelta(minutes=5):
            time_to_wait = timedelta(minutes=5)
        logger.info(f'{self} | Waiting next claim time: {next_claim_datetime_with_tz.isoformat()}')
        await sleep(time_to_wait.total_seconds(), log_info=f'{self}', echo=True)
        _, data = await self.http_session.get(f'{self.API_URL}/myPage/faucet/{cosmos_address}')
        if data['msg'] == 'success':
            logger.success(f'{self} | Claimed {latest_claim_record_data["nextTimeSendAmount"]} $CYS')
        else:
            logger.warning(f'{self} | {data}')
        await self.schedule_next_claim()

    async def schedule_next_claim(self):
        await sleep(24 * 60 * 60 + 5 * 60, log_info=f'{self}', echo=True)
        await self.claim_faucet()


async def register(profile: Profile):
    client = Cysic(profile=profile)
    await client.register(codes.pop())


async def claim_faucet():
    accounts = (
        await create_db_instance(CONNECTION_STRING).execute_query(select(CysicAccount.profile_id))
    ).scalars().all()
    profiles = await create_db_instance().get_rows_by_id(accounts, Profile)
    await asyncio.gather(*[Cysic(profile=profile).claim_faucet() for profile in profiles])


async def register():
    profiles = await create_db_instance().get_rows_by_id(
        [
            144
        ],
        Profile
    )
    await asyncio.gather(*[register(profile) for profile in profiles])


async def get_balance():
    import cosmpy
    from cosmpy.aerial.client import LedgerClient, NetworkConfig
    ledger_client = LedgerClient(NetworkConfig(
        chain_id='cysicmint_9001-1',
        url='grpc+https://rpc-testnet.prover.xyz/',
        fee_minimum_gas_price=0.025,
        fee_denomination="CYS",
        staking_denomination="CGT",
    ))
    print(ledger_client.query_bank_balance('cysic1gmvn43rt55mhn6akmdnuqjfgf73ywa5ncwerfe'))


if __name__ == '__main__':
    asyncio.run(claim_faucet())
