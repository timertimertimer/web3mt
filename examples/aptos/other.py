import os
import asyncio

from aiohttp import payload
from web3db import DBHelper
from web3db.models import Profile
from aptos_sdk.async_client import ResourceNotFound
from dotenv import load_dotenv

from config import *
from web3mt.aptos.bluemove import BlueMove
from web3mt.utils import logger, read_json, Z8
from web3mt.aptos.client import Client

load_dotenv()
db = DBHelper(os.getenv('CONNECTION_STRING'))
passphrase = os.getenv('PASSPHRASE')


async def bluemove_batch_sell(profile: Profile):
    client = Client(profile, encryption_password=passphrase)
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
    client = Client(profile, encryption_password=passphrase)
    balance = await client.v2_token_data(COLLECTION_ID)
    logger.info(f"{client.profile.id} | {client.account_.address()} | Balance of aptmap - {balance}")
    for data in balance:
        payload = read_json('payload.json')
        token_name = data['current_token_data']['token_name']
        logger.info(f'{client.profile.id} | Changing price of {token_name}')
        storage_id = data['storage_id']
        payload['arguments'] += [{'inner': storage_id}, "6000000"]
        await client.send_transaction(payload)


async def sell_all_aptmaps(profile: Profile):
    async with BlueMove(profile, passphrase) as client:
        not_listed_aptmaps = await client.v2_token_data(COLLECTION_ID)
        listed_aptmaps = await client.get_listed_nfts()
        for listed_aptmap in listed_aptmaps:
            price = int(listed_aptmap['attributes']['price']) / Z8
            listing_id = listed_aptmap['attributes']['listing_id']
            token_name = listed_aptmap['attributes']['name']
            logger.info(f'{client.log_info} | Current listing info: {token_name} - {price} APT')
            if price > PRICE:
                await client.edit_listing_price(token_name, listing_id, PRICE)

        await client.batch_list_token_v2([aptmap['storage_id'] for aptmap in not_listed_aptmaps], PRICE)


async def verify(profile: Profile):
    client = Client(profile, encryption_password=passphrase)
    await client.verify_transaction('0xf2d1ede2c22f254a88ae9d3f7150543be8de8df867e97349eca3f25daa2d3582', 'smt')


async def check_balance_batch() -> int:
    tasks = []
    for profile in await db.get_all_from_table(Profile):
        client = Client(profile, encryption_password=passphrase)
        tasks.append(asyncio.create_task(client.account_balance(client.account_.address())))
    return sum(await asyncio.gather(*tasks))


async def check_v1_token_ownership(profile: Profile):
    client = Client(profile, encryption_password=passphrase)
    data = await client.v1_token_data(COLLECTION_ID)
    if not data:
        logger.error(f'{client.profile.id} | {client.account_.address()} {data}')
    else:
        logger.success(f'{client.profile.id} | {client.account_.address()} {data}')


async def check_v2_token_ownership(profile: Profile) -> int:
    client = Client(profile, encryption_password=passphrase)
    data = await client.v2_token_data(COLLECTION_ID)
    if not data:
        logger.error(f'{client.profile.id} | {client.account_.address()} {data}')
    else:
        logger.success(f'{client.profile.id} | {client.account_.address()} {data}')
    return len(data)


async def withdraw_to_okx(profile: Profile):
    client = Client(profile=profile, encryption_password=passphrase)
    balance = await client.account_balance(client.account_.address())
    await client.transfer(client.account_, profile.okx_aptos_address, int(balance * 0.8))
    logger.info(
        f'{profile.id} | {profile.aptos_address} | Sent {int(balance * 0.8) / Z8} APT to {profile.okx_aptos_address}'
    )


async def good_balance(profile: Profile, amount: int = 1.5):
    client = Client(profile=profile, encryption_password=passphrase)
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
    profiles: list[Profile] = await db.get_rows_by_id([102], Profile)
    for profile in profiles:
        tasks.append(asyncio.create_task(verify(profile)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    print(asyncio.run(main()))
