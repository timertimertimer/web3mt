import asyncio
from decimal import Decimal

from web3db import Profile
from web3db.core import create_db_instance

from examples.utils.other import data_path
from web3mt.cex.binance.client import ProfileBinance
from web3mt.cex.bybit.client import Bybit
from web3mt.cex.okx.client import OKX
from web3mt.models import Coin
from web3mt.onchain.evm.client import ProfileClient
from web3mt.onchain.evm.models import Ethereum, BSC
from web3mt.utils import logger

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
    with open(data_path / "addresses.txt", encoding="utf-8") as f:
        addresses = [row.strip() for row in f]
    amount = Decimal("0.0023")
    coin = Coin("BNB")
    profile: Profile = await db.get_row_by_id(1, Profile)
    bsc_client = ProfileClient(profile, chain=BSC)
    async with ProfileBinance(profile) as client:
        # await client.get_all_supported_coins_info()
        await client.update_balances()
        for address in addresses:
            balance = await bsc_client.balance_of(owner_address=address)
            if balance:
                continue
            await client.withdraw(coin, address, amount, "BSC", update_balance=False)


if __name__ == "__main__":
    asyncio.run(binance())
