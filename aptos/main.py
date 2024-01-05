import asyncio

from aptos.utils import get_accounts, get_config_section, logger
from client import AptosClient
from utils import read_json

Z8 = 10 ** 8


async def main():
    tasks = []
    aptos_config = get_config_section('aptos')
    amount_percentage = float(aptos_config['amount_percentage'])
    price = float(aptos_config['price'])
    collection_id = aptos_config['collection_id']
    for account in get_accounts():
        client = AptosClient(account)
        balance = await client.get_storage_ids(collection_id)
        for data in balance[:int(len(balance) * amount_percentage / 100) - 1]:
            payload = read_json('payload.json')
            token_name = data['current_token_data']['token_name']
            logger.info(f'Selling {token_name}')
            storage_id = data['storage_id']
            payload['arguments'][0] = [{'inner': storage_id}]
            payload['arguments'][2] = [f'{int(price * Z8)}']
            tasks.append(asyncio.create_task(client.send_transaction(payload)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
