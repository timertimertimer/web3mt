import asyncio

from web3db import DBHelper, Profile

from web3mt.cex.bybit.bybit import Bybit
from web3mt.cex.okx.okx import OKX
from web3mt.config import env
from web3mt.onchain.evm.models import Ethereum
from web3mt.utils import my_logger as logger

db = DBHelper(env.LOCAL_CONNECTION_STRING)


async def get_total_balance():
    await Ethereum.native_token.update_price()
    logger.debug(f"1 ETH = {Ethereum.native_token.price}$")
    profiles: list[Profile] = await db.get_all_from_table(Profile)
    funcs = []
    for profile in profiles:
        if profile.bybit and profile.bybit.api_key:
            funcs.append(Bybit(profile).get_total_balance())
        if profile.okx and profile.okx.api_key:
            funcs.append(OKX(profile).get_total_balance())
    res = await asyncio.gather(*funcs)
    logger.debug(f"CEXs: {sum(res):.2f}$")


async def collect_on_main():
    await OKX().collect_on_funding_master()


if __name__ == "__main__":
    asyncio.run(get_total_balance())
