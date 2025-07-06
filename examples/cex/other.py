import asyncio

from web3db import DBHelper, Profile
from web3db.core import create_db_instance

from web3mt.cex.binance.client import Binance, ProfileBinance
from web3mt.cex.bybit.bybit import Bybit
from web3mt.cex.okx.okx import OKX
from web3mt.config import env
from web3mt.onchain.evm.models import Ethereum
from web3mt.utils import logger
from web3mt.utils.http_sessions import SessionConfig

db = create_db_instance()


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


async def binance():
    profile: Profile = await db.get_row_by_id(1, Profile)
    async with ProfileBinance(profile) as client:
        balance_before = await client.get_total_balance()
        for asset in client.main_user.trading_account:
            await client.transfer_from_trading_to_funding(client.main_user, asset)
        balance_after = await client.get_total_balance()
        return balance_after


if __name__ == "__main__":
    asyncio.run(binance())
