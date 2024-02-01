import asyncio

from aptos.utils import get_accounts, get_config_section, logger
from client import AptosClient
from utils import read_json, MWD

aptos_config = get_config_section('aptos')


async def bluemove_sell_nfts():
    tasks = []
    amount_percentage = float(aptos_config['amount_percentage'])
    price = float(aptos_config['price'])
    collection_id = aptos_config['collection_id']
    for account in get_accounts():
        client = AptosClient(account)
        balance = await client.get_storage_ids(collection_id)
        logger.info(f"{client.account_.address()} | Balance of aptmap - {balance}")
        for data in balance[:int(len(balance) * amount_percentage / 100)]:
            payload = read_json('payload.json')
            token_name = data['current_token_data']['token_name']
            logger.info(f'Selling {token_name}')
            storage_id = data['storage_id']
            payload['arguments'][0] = [{'inner': storage_id}]
            payload['arguments'][2] = [f'{int(price * Z8)}']
            tasks.append(asyncio.create_task(client.send_transaction(payload)))
    await asyncio.gather(*tasks)


async def aptmap_balance():
    collection_id = aptos_config['collection_id']
    total = 0
    for account in get_accounts(MWD / 'aptos' / 'accounts.txt'):
        client = AptosClient(account)
        balance = await client.get_storage_ids(collection_id)
        total += len(balance)
        logger.info(f"{str(client.account_.address())[:6]} | Balance of aptmap - {len(balance)}")
    logger.info(f'Total: {total}')


async def batch_balance():
    total = 0
    for account in get_accounts(MWD / 'aptos' / 'accounts.txt'):
        client = AptosClient(account)
        balance = await client.balance()
        total += balance
    print(total)


if __name__ == '__main__':
    asyncio.run(aptmap_balance())
