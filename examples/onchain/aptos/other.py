import asyncio

from web3db import Profile
from web3db.core import create_db_instance

from web3mt.onchain.aptos import Client
from web3mt.onchain.aptos.models import Token, TokenAmount
from web3mt.utils import logger

db = create_db_instance()


async def check_balance_batch() -> None:
    await Token().update_price()
    total: TokenAmount = sum(
        await asyncio.gather(
            *[
                asyncio.create_task(Client(profile).balance(echo=True))
                for profile in await db.get_all_from_table(Profile)
            ]
        )
    )
    logger.info(f"Total: {total}")


async def withdraw_to_okx(profile: Profile):
    client = Client(profile=profile)
    balance = await client.account_balance(client.account_.address())
    await client.transfer(
        client.account_, profile.okx_deposit.aptos, int(balance * 0.8)
    )
    logger.info(
        f"{client} | Sent {TokenAmount(balance * 0.8, is_wei=True)} APT to {profile.okx_deposit.aptos}"
    )


if __name__ == "__main__":
    asyncio.run(check_balance_batch())
