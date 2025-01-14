import asyncio

from solana.rpc.async_api import AsyncClient

from solana.rpc.providers.async_http import AsyncHTTPProvider
from solders.rpc.requests import GetBalance, GetTransactionCount
from solders.rpc.responses import GetBalanceResp, GetTransactionCountResp
from solders.keypair import Keypair

from web3db.core import DBHelper
from web3db.models import Profile

from web3mt.consts import Web3mtENV
from web3mt.utils.logger import my_logger

# rpc = f"https://mainnet.helius-rpc.com/?api-key={Web3mtENV.HELIUS_API_KEY}"
rpc = 'https://grateful-jerrie-fast-mainnet.helius-rpc.com/'


async def get_balance_batch(profiles: list[Profile]):
    provider = AsyncHTTPProvider(rpc)
    step = 5
    total = 0
    for batch in range(0, len(profiles), step):
        profiles_ = profiles[batch:batch + step]
        reqs = tuple(GetBalance(Keypair.from_base58_string(profile.solana_private).pubkey()) for profile in profiles_)
        parsers = (GetBalanceResp,) * len(profiles_)
        resps = await provider.make_batch_request(reqs, parsers)  # type: ignore
        for resp, profile in zip(resps, profiles_):
            balance = resp.value / 10 ** 9
            total += balance
            my_logger.info(
                f'{profile.id} | {Keypair.from_base58_string(profile.solana_private).pubkey()} | {balance} SOL')
    return total


async def get_balance(profile: Profile):
    client = AsyncClient(rpc)
    address = Keypair.from_base58_string(profile.solana_private).pubkey()
    balance = await client.get_balance(address)
    my_logger.info(f'{profile.id} | {address} | {balance.value / 10 ** 9} SOL')


async def main():
    db = DBHelper(Web3mtENV.LOCAL_CONNECTION_STRING)
    profiles = await db.get_all_from_table(Profile)
    total = await get_balance_batch(profiles)
    my_logger.success(f'Total: {total} SOL')
    # await asyncio.gather(*[get_balance(profile) for profile in profiles])


if __name__ == "__main__":
    asyncio.run(main())
