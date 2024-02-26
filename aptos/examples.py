import asyncio
import os

from web3db import DBHelper
from web3db.models import Profile

from utils import get_config_section, logger, read_json, Z8
from client import Client
from dotenv import load_dotenv

load_dotenv()

aptos_config = get_config_section('aptos')
amount_percentage = float(aptos_config['amount_percentage'])
price = float(aptos_config['price'])
collection_id = aptos_config['collection_id']


async def bluemove_batch_sell(profile: Profile):
    client = Client(profile)
    balance = await client.v2_token_data(collection_id)
    logger.info(f"{client.account_.address()} | Balance of aptmap - {balance}", id=profile.id)
    for data in balance[:int(len(balance) * amount_percentage / 100)]:
        payload = read_json('payload.json')
        token_name = data['current_token_data']['token_name']
        logger.info(f'Selling {token_name}', id=profile.id)
        storage_id = data['storage_id']
        payload['arguments'][0] = [{'inner': storage_id}]
        payload['arguments'][2] = [f'{int(price * Z8)}']
        await client.send_transaction(payload)


async def batch_balance(profiles: list[Profile]) -> int:
    tasks = []
    for profile in profiles:
        client = Client(profile)
        tasks.append(asyncio.create_task(client.balance()))
    results = await asyncio.gather(*tasks)
    return sum(results)


async def check_v1_token_ownership(profile: Profile):
    client = Client(profile)
    data = await client.v1_token_data(collection_id)
    if not data['data']['current_token_ownerships']:
        logger.error(f'{profile.id} | {client.account_.address()} {data["data"]["current_token_ownerships"]}')
    else:
        logger.success(f'{profile.id} | {client.account_.address()} {data["data"]["current_token_ownerships"]}')


async def check_v2_token_ownership(profile: Profile):
    client = Client(profile)
    data = await client.v1_token_data(collection_id)
    if not data['data']['current_token_ownerships']:
        logger.error(f'{profile.id} | {client.account_.address()} {data["data"]["current_token_ownerships"]}')
    else:
        logger.success(f'{profile.id} | {client.account_.address()} {data["data"]["current_token_ownerships"]}')


async def main():
    db = DBHelper(os.getenv('CONNECTION_STRING'))
    profiles: list[Profile] = await db.get_all_from_table(Profile)
    await batch_balance(profiles)


if __name__ == '__main__':
    asyncio.run(main())
