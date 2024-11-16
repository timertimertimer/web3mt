import asyncio

from eth_account import Account
from web3.exceptions import Web3RPCError
from web3db import LocalProfile, DBHelper

from web3mt.consts import Web3mtENV
from web3mt.onchain.evm.client import Client, BaseClient
from web3mt.onchain.evm.models import *
from web3mt.utils import my_logger

db = DBHelper(Web3mtENV.LOCAL_CONNECTION_STRING)
main_chains = [Ethereum, Scroll, zkSync, Base, Zora, Optimism, Arbitrum]


async def _get_balance(profile: LocalProfile, chain: Chain, semaphore: asyncio.Semaphore) -> TokenAmount:
    async with semaphore:
        client = Client(chain=chain, profile=profile)
        return await client.balance_of()


async def _get_balance_multicall(chain: Chain, profiles: list[LocalProfile], echo: bool = False) -> TokenAmount:
    client = BaseClient(chain=chain)
    total_by_chain = TokenAmount(0, token=chain.native_token)
    batch_size = 10
    all_balances = []
    for i in range(0, len(profiles), batch_size):
        async with client.w3.batch_requests() as batch:
            for profile in profiles[i:i + batch_size]:
                batch.add(client.w3.eth.get_balance(Account.from_key(profile.evm_private).address))
            try:
                balances = await batch.async_execute()
            except Web3RPCError as e:
                my_logger.warning(f'{chain} | {e}')
                balances = [0] * batch_size
            except TimeoutError as e:
                pass  # FIXME:
        all_balances += balances
    for balance, profile in zip(all_balances, profiles):
        token_amount = TokenAmount(balance, wei=True, token=chain.native_token)
        if echo:
            my_logger.info(f'{profile.id} | {profile.evm_address} ({chain}) | {token_amount}')
        total_by_chain += token_amount
    return total_by_chain


async def check_balance_batch_multicall(chains: list[Chain] = None):
    chains = chains or main_chains
    await Ethereum.native_token.update_price()
    my_logger.success(f'1 ETH = {Ethereum.native_token.price}$')
    profiles = await db.get_all_from_table(LocalProfile)
    total = 0
    full_log = 'Natives on wallets:\n'
    totals_by_chains = await asyncio.gather(*[_get_balance_multicall(chain, profiles, True) for chain in chains])
    for chain, total_by_chain in zip(chains, totals_by_chains):
        s = (
            f'{total_by_chain.ether} {total_by_chain.token.symbol} ({total_by_chain.token.chain}) = '
            f'{total_by_chain.amount_in_usd:.2f}$'
        )
        my_logger.info(s)
        full_log += s + '\n'
        total += total_by_chain.ether
    full_log += f'Total natives in wallets: {total} ETH = {(total * Ethereum.native_token.price):.2f}$'
    my_logger.info(full_log)


async def check_balance_batch(chains: list[Chain] = None):
    chains = chains or main_chains
    await Ethereum.native_token.update_price()
    my_logger.success(f'1 ETH = {Ethereum.native_token.price}$')
    chains = chains or [Ethereum, Scroll, zkSync, Base, Zora, Optimism, Arbitrum]
    profiles = await db.get_all_from_table(LocalProfile)
    semaphore = asyncio.Semaphore(8)
    total = 0
    full_log = 'Natives on wallets:\n'
    for chain in chains:
        total_balance: TokenAmount = sum(
            el for el in await asyncio.gather(
                *[asyncio.create_task(_get_balance(profile, chain, semaphore)) for profile in profiles]
            )
        )
        s = (
            f'{total_balance.ether} {total_balance.token.symbol} ({total_balance.token.chain}) = '
            f'{total_balance.amount_in_usd:.2f}$'
        )
        my_logger.info(s)
        full_log += s + '\n'
        total += total_balance.ether
    full_log += f'Total natives in wallets: {total} ETH = {(total * Ethereum.native_token.price):.2f}$'
    my_logger.info(full_log)


async def have_balance(client: Client, ethers: float = 0, echo: bool = False) -> bool:
    balance = await client.balance_of(echo=echo)
    if balance.ether > ethers:
        return True
    return False


async def check_eth_activated_profile(profile: LocalProfile, log_only_activated: bool = False) -> int | None:
    client = Client(profile=profile)
    nonce = await client.nonce()
    log = f'{client} | Nonce - {nonce}'
    if nonce == 0:
        if log_only_activated:
            return
        my_logger.warning(log)
    else:
        my_logger.success(log)
        return profile.id


if __name__ == '__main__':
    asyncio.run(check_balance_batch_multicall())
