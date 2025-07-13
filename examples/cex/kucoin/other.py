import asyncio

from web3mt.cex.kucoin.client import Kucoin
from web3mt.models import TokenAmount
from web3mt.onchain.monero.models import XMR


async def main():
    client = Kucoin()
    await client.update_balances()  # FIXME: 2 requests -> 1 request
    xmr_balance = client.main_user.funding_account.get(XMR)
    data = await client.withdraw(
        "48N7tGNrcAoXnJ3e4CjpaAhewmr8UC4LcbGLADCZR2gSLWZPULNiRs9Gia5z7Ug4FKLCv7NAgzfwg3i8uGKVSXjTAJ9soqj",
        TokenAmount(XMR, xmr_balance.available_balance),
    )
    return data


if __name__ == "__main__":
    asyncio.run(main())
