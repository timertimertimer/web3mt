import asyncio

from web3mt.cex.htx.client import HTX


async def main():
    client = HTX()
    balance = await client.get_trading_balance()
    data = await client.withdraw(
        "48N7tGNrcAoXnJ3e4CjpaAhewmr8UC4LcbGLADCZR2gSLWZPULNiRs9Gia5z7Ug4FKLCv7NAgzfwg3i8uGKVSXjTAJ9soqj",
    )
    return data


if __name__ == "__main__":
    asyncio.run(main())
