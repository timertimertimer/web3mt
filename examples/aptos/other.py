import os
import asyncio
from web3db import DBHelper
from web3db.models import Profile
from aptos_sdk.async_client import ResourceNotFound
from dotenv import load_dotenv

from config import *
from web3mt.utils import logger, read_json, Z8
from web3mt.aptos.client import Client

load_dotenv()
db = DBHelper(os.getenv('CONNECTION_STRING'))


async def bluemove_batch_sell(profile: Profile):
    client = Client(profile)
    balance = await client.v2_token_data(COLLECTION_ID)
    logger.info(f"{profile.id} | {client.account_.address()} | Balance of aptmap - {balance}")
    for data in balance[:int(len(balance) * AMOUNT_PERCENTAGE / 100)]:
        payload = read_json('payload.json')
        token_name = data['current_token_data']['token_name']
        logger.info(f'{profile.id} | Selling {token_name}')
        storage_id = data['storage_id']
        payload['arguments'][0] = [{'inner': storage_id}]
        payload['arguments'][2] = [f'{int(PRICE * Z8)}']
        await client.send_transaction(payload)


async def bluemove_batch_edit_sell_price(profile: Profile):
    client = Client(profile)
    balance = await client.v2_token_data(COLLECTION_ID)
    logger.info(f"{client.profile.id} | {client.account_.address()} | Balance of aptmap - {balance}")
    for data in balance:
        payload = read_json('payload.json')
        token_name = data['current_token_data']['token_name']
        logger.info(f'{client.profile.id} | Changing price of {token_name}')
        storage_id = data['storage_id']
        payload['arguments'] += [{'inner': storage_id}, "5300000"]
        await client.send_transaction(payload)


async def check_balance_batch() -> int:
    tasks = []
    for profile in await db.get_all_from_table(Profile):
        client = Client(profile)
        tasks.append(asyncio.create_task(client.account_balance(client.account_.address())))
    return sum(await asyncio.gather(*tasks))


async def batch_balance_from_privates(privates: list[str]) -> int:
    tasks = []
    for private in privates:
        client = Client(private=private)
        tasks.append(asyncio.create_task(client.balance()))
    return sum(await asyncio.gather(*tasks))


async def check_v1_token_ownership(profile: Profile):
    client = Client(profile)
    data = await client.v1_token_data(COLLECTION_ID)
    if not data:
        logger.error(f'{client.profile.id} | {client.account_.address()} {data}')
    else:
        logger.success(f'{client.profile.id} | {client.account_.address()} {data}')


async def check_v2_token_ownership(profile: Profile) -> int:
    client = Client(profile)
    data = await client.v2_token_data(COLLECTION_ID)
    if not data:
        logger.error(f'{client.profile.id} | {client.account_.address()} {data}')
    else:
        logger.success(f'{client.profile.id} | {client.account_.address()} {data}')
    return len(data)


async def withdraw_to_okx(profile: Profile):
    client = Client(profile=profile)
    balance = await client.account_balance(client.account_.address())
    await client.transfer(client.account_, profile.okx_aptos_address, int(balance * 0.8))
    logger.info(
        f'{profile.id} | {profile.aptos_address} | Sent {int(balance * 0.8) / Z8} APT to {profile.okx_aptos_address}'
    )


async def good_balance(profile: Profile, amount: int = 1.5):
    client = Client(profile=profile)
    try:
        balance = await client.account_balance(client.account_.address()) / Z8
    except ResourceNotFound:
        balance = 0
    s = f'{profile.id} | {client.account_.address()} | Balance: {balance} APT'
    if balance > amount:
        logger.success(s)
        return True
    logger.info(s)
    return False


async def main():
    tasks = []
    profiles: list[Profile] = await db.get_rows_by_id([1], Profile)
    for profile in profiles:
        tasks.append(asyncio.create_task(bluemove_batch_edit_sell_price(profile)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    print(asyncio.run(check_balance_batch()))
