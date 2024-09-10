import asyncio

from web3mt.cex.bybit.bybit import Bybit
from web3mt.cex.okx.okx import OKX
from web3mt.consts import Web3mtENV
from web3mt.local_db import DBHelper
from web3mt.onchain.evm.models import Ethereum
from web3mt.utils import my_logger
from web3db import Profile

db = DBHelper(Web3mtENV.LOCAL_CONNECTION_STRING)


async def get_total_balance():
    await Ethereum.native_token.update_price()
    my_logger.debug(f'1 ETH = {Ethereum.native_token.price}$')
    profiles = await db.get_all_from_table(Profile)
    funcs = []
    for profile in profiles:
        if profile.bybit_api_key:
            funcs.append(Bybit(profile).get_total_balance())
        if profile.okx_api_key:
            funcs.append(OKX(profile).get_total_balance())
    res = await asyncio.gather(*funcs)
    my_logger.debug(f'CEXs: {sum(res):.2f}$')


async def collect_on_main():
    await OKX().collect_on_funding_master()


if __name__ == '__main__':
    asyncio.run(get_total_balance())
