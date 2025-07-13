import asyncio

from web3mt.cex.mexc.client import MEXC
from web3mt.models import TokenAmount
from web3mt.onchain.monero.models import XMR


async def some():
    client = MEXC()
    data = await client.get_all_supported_coins_info()
    return data


async def main():
    client = MEXC()
    await client.update_balances()
    xmr_balance = client.main_user.funding_account.get(XMR)
    data = await client.withdraw(
        "48N7tGNrcAoXnJ3e4CjpaAhewmr8UC4LcbGLADCZR2gSLWZPULNiRs9Gia5z7Ug4FKLCv7NAgzfwg3i8uGKVSXjTAJ9soqj",
        TokenAmount(XMR, xmr_balance.available_balance),
    )
    return data


if __name__ == "__main__":
    asyncio.run(some())
