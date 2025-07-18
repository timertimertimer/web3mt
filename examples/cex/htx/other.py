import asyncio
from decimal import Decimal

from web3mt.cex.htx.client import HTX
from web3mt.models import TokenAmount
from web3mt.onchain.monero.models import XMR


async def main():
    client = HTX()
    balance = await client.get_trading_balance()
    xmr_balance = client.main_user.trading_account.get(XMR)
    data = await client.withdraw(
        "48N7tGNrcAoXnJ3e4CjpaAhewmr8UC4LcbGLADCZR2gSLWZPULNiRs9Gia5z7Ug4FKLCv7NAgzfwg3i8uGKVSXjTAJ9soqj",
        TokenAmount(XMR, xmr_balance.available_balance - Decimal("0.002")),
        # fee=TokenAmount(XMR, 0.002),
    )
    return data


if __name__ == "__main__":
    asyncio.run(main())
