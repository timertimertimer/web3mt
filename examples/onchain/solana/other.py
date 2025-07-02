import asyncio

from solana.rpc.async_api import AsyncClient
from solana.rpc.commitment import Commitment

from solana.rpc.providers.async_http import AsyncHTTPProvider
from solana.rpc.types import TokenAccountOpts
from solders.account_decoder import UiAccountEncoding
from solders.pubkey import Pubkey
from solders.rpc.config import RpcTokenAccountsFilterMint, RpcAccountInfoConfig
from solders.rpc.requests import GetBalance, GetTransactionCount, GetTokenAccountsByOwner
from solders.rpc.responses import GetBalanceResp, GetTransactionCountResp, GetTokenAccountsByOwnerResp, \
    GetTokenAccountsByOwnerJsonParsedResp
from solders.keypair import Keypair

from web3db.core import DBHelper
from web3db.models import Profile

from web3mt.config import env
from web3mt.utils.logger import my_logger

# rpc = f"https://mainnet.helius-rpc.com/?api-key={env.HELIUS_API_KEY}"
rpc = 'https://grateful-jerrie-fast-mainnet.helius-rpc.com/'
OGMEME_token_mint_address = Pubkey.from_string('jE7q5qieKaUXmyhuWTXmGVtpeBoKtgbMbtks7LKogme')


async def get_balance_batch(profiles: list[Profile]):
    provider = AsyncHTTPProvider(rpc)
    step = 5
    total = 0
    for batch in range(0, len(profiles), step):
        profiles_ = profiles[batch:batch + step]
        reqs = tuple(GetBalance(
            Keypair.from_base58_string(profile.solana_private).pubkey()
        ) for profile in profiles_)
        parsers = (GetBalanceResp,) * len(profiles_)
        resps = await provider.make_batch_request(reqs, parsers)  # type: ignore
        for resp, profile in zip(resps, profiles_):
            balance = resp.value / 10 ** 9
            total += balance
            my_logger.info(
                f'{profile.id} | {Keypair.from_base58_string(profile.solana_private).pubkey()} | {balance} SOL'
            )
    return total


async def get_balance(profile: Profile):
    client = AsyncClient(rpc)
    address = Keypair.from_base58_string(profile.solana_private).pubkey()
    balance = await client.get_balance(address)
    my_logger.info(f'{profile.id} | {address} | {balance.value / 10 ** 9} SOL')


def get_metadata_address(mint_address: Pubkey) -> Pubkey:
    METADATA_PROGRAM_ID = Pubkey.from_string("metaqbxxUerdq28cj1RbAWkYQm3ybzjb6a8bt518x1s")
    seeds = [b"metadata", bytes(METADATA_PROGRAM_ID), bytes(mint_address)]
    metadata_pubkey, _ = Pubkey.find_program_address(seeds, METADATA_PROGRAM_ID)
    return metadata_pubkey


async def get_token_balance(profile: Profile, token_mint_address: Pubkey):
    client = AsyncClient(rpc)
    address = Keypair.from_base58_string(profile.solana_private).pubkey()
    token_accounts = await client.get_token_accounts_by_owner(address, TokenAccountOpts(mint=token_mint_address))
    token_account = token_accounts.value[0].pubkey
    token_balance = await client.get_token_account_balance(token_account)
    print(f"Баланс токена: {int(token_balance.value.amount) / 10 ** 6}")


async def get_token_balance_batch(profiles: list[Profile], token_address: Pubkey):
    provider = AsyncHTTPProvider(rpc)
    client = AsyncClient(rpc)
    resp = await client.get_account_info_json_parsed(token_address)
    step = 5
    total = 0
    for batch in range(0, len(profiles), step):
        profiles_ = profiles[batch:batch + step]
        reqs = tuple(GetTokenAccountsByOwner(
            Keypair.from_base58_string(profile.solana_private).pubkey(),
            RpcTokenAccountsFilterMint(token_address),
            RpcAccountInfoConfig(encoding=UiAccountEncoding.JsonParsed)
        ) for profile in profiles_)
        parsers = (GetTokenAccountsByOwnerJsonParsedResp,) * len(profiles_)
        resps = await provider.make_batch_request(reqs, parsers)  # type: ignore
        for resp, profile in zip(resps, profiles_):
            if resp.value:
                balance = int(resp.value[0].account.data.parsed['info']['tokenAmount']['amount']) / 10 ** 6
                total += balance
                my_logger.info(
                    f'{profile.id} | {Keypair.from_base58_string(profile.solana_private).pubkey()} | {balance} SOL'
                )
            else:
                my_logger.info(
                    f'{profile.id} | {Keypair.from_base58_string(profile.solana_private).pubkey()} | 0 SOL'
                )
    return total


async def main2():
    db = DBHelper(env.LOCAL_CONNECTION_STRING)
    profiles = await db.get_all_from_table(Profile)
    await get_token_balance(profiles[0])


async def main():
    db = DBHelper(env.LOCAL_CONNECTION_STRING)
    # profiles = await db.get_all_from_table(Profile)
    profiles = await db.get_rows_by_id([1], Profile)
    total = await get_token_balance_batch(profiles, OGMEME_token_mint_address)
    my_logger.success(f'Total: {total} SOL')
    # await asyncio.gather(*[get_token_balance(profile, OGMEME_token_mint_address) for profile in profiles])


async def test():
    metadata_address = get_metadata_address(OGMEME_token_mint_address)
    client = AsyncClient(rpc)
    metadata = await client.get_account_info(metadata_address, encoding='jsonParsed')
    print(metadata)


if __name__ == "__main__":
    asyncio.run(main())
