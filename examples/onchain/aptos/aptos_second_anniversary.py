import asyncio
from aptos_sdk.account_address import AccountAddress
from aptos_sdk.bcs import Serializer
from aptos_sdk.transactions import EntryFunction, TransactionArgument
from web3db import Profile, DBHelper
from web3mt.onchain.aptos import Client
from web3mt.onchain.aptos.models import TokenAmount
from web3mt.utils import logger

ZERO_BALANCE = TokenAmount(0)


async def is_minted(client: Client) -> bool:
    nfts_data = await client.nfts_data()
    for nft in nfts_data:
        if nft.name == "Aptos TWO Mainnet Anniversary 2024":
            return True
    return False


async def mint(profile: Profile):
    client = Client(profile)
    client.session.config.try_with_default_proxy = True
    amount = 1
    balance = await client.balance()
    if await is_minted(client):
        logger.debug(f'{client} | Already minted')
        return
    if balance > ZERO_BALANCE:
        payload = EntryFunction.natural(
            module="0x96c192a4e3c529f0f6b3567f1281676012ce65ba4bb0a9b20b46dec4e371cccd::unmanaged_launchpad",
            function="mint",
            ty_args=[],
            args=[
                TransactionArgument(
                    AccountAddress.from_str('0xd42cd397c41a62eaf03e83ad0324ff6822178a3e40aa596c4b9930561d4753e5'),
                    Serializer.struct
                ),
                TransactionArgument([amount], Serializer.sequence_serializer(value_encoder=Serializer.u64))
            ],
        )
        tx_hash = await client.send_transaction(payload, 2000)
        if tx_hash:
            logger.success(f'{client} | Minted {amount} NFTs')
        else:
            logger.error(f'{client} | Failed {tx_hash}')


async def main():
    db = DBHelper()
    profiles = await db.get_all_from_table(Profile)
    await asyncio.gather(*[mint(profile) for profile in profiles])


if __name__ == '__main__':
    asyncio.run(main())
