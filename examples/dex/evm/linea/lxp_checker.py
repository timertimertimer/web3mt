import asyncio

from web3mt.local_db import DBHelper, Profile
from web3mt.onchain.evm.client import Client
from web3mt.onchain.evm.models import Linea, Token
from web3mt.utils import my_logger

db = DBHelper()


async def check_xp_linea():
    lxp_contract_address = '0xd83af4fbD77f3AB65C3B1Dc4B38D7e67AEcf599A'
    profiles = await db.get_all_from_table(Profile)
    tasks = []
    for profile in profiles:
        client = Client(chain=Linea, profile=profile)
        tasks.append(asyncio.create_task(
            client.balance_of(token=Token(Linea, address=lxp_contract_address), echo=True, remove_zero_from_echo=True)
        ))
    result = await asyncio.gather(*tasks)
    my_logger.success(f'Total - {sum([el.ether for el in result])}')


asyncio.run(check_xp_linea())
