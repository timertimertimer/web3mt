import asyncio
import random
import time

from aptos_sdk.account_address import AccountAddress
from aptos_sdk.authenticator import Authenticator, Ed25519Authenticator
from aptos_sdk.bcs import Serializer
from aptos_sdk.transactions import RawTransaction, TransactionPayload, EntryFunction, TransactionArgument, \
    SignedTransaction
from web3db import LocalProfile

from web3mt.local_db import DBHelper
from web3mt.onchain.aptos import Client
from web3mt.onchain.aptos.models import TokenAmount
from web3mt.utils import my_logger

ZERO_BALANCE = TokenAmount(0)


async def is_minted(client: Client) -> bool:
    nfts_data = await client.nfts_data()
    for nft in nfts_data:
        if nft.name == "Aptos TWO Mainnet Anniversary 2024":
            return True
    return False


async def mint(profile: LocalProfile):
    client = Client(profile)
    client.session.config.try_with_default_proxy = True
    amount = 1
    balance = await client.balance()
    if await is_minted(client):
        my_logger.debug(f'{client} | Already minted')
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
            my_logger.success(f'{client} | Minted {amount} NFTs')
        else:
            my_logger.error(f'{client} | Failed {tx_hash}')


async def main():
    db = DBHelper()
    profiles = await db.get_all_from_table(LocalProfile)
    await asyncio.gather(*[mint(profile) for profile in profiles])


if __name__ == '__main__':
    asyncio.run(main())
