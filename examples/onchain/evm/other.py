import asyncio

from eth_account import Account

from eth_utils.address import to_checksum_address
from web3.exceptions import Web3RPCError
from web3db import Profile, DBHelper

from web3mt.consts import Web3mtENV
from web3mt.onchain.evm.client import Client, BaseClient, TransactionParameters
from web3mt.onchain.evm.models import *
from web3mt.onchain.evm.models import Xterio
from web3mt.utils import my_logger, ProfileSession

db = DBHelper(Web3mtENV.LOCAL_CONNECTION_STRING)
main_chains = [Ethereum, Scroll, zkSync, Base, Zora, Optimism, Arbitrum, Linea]


async def _get_balance(profile: Profile, chain: Chain, semaphore: asyncio.Semaphore) -> TokenAmount:
    async with semaphore:
        client = Client(chain=chain, profile=profile)
        return await client.balance_of()


async def _get_balance_multicall(
        chain: Chain, profiles: list[Profile],
        token: Token = Ethereum.native_token, echo: bool = False,
        is_condition=lambda x: x.ether > 0
) -> TokenAmount:
    client = BaseClient(chain=chain)

    contract = client.w3.eth.contract(to_checksum_address(token.address), abi=DefaultABIs.token)
    total_by_chain = TokenAmount(0, token=token)
    batch_size = 10
    all_balances = []
    for i in range(0, len(profiles), batch_size):
        async with client.w3.batch_requests() as batch:
            for profile in profiles[i:i + batch_size]:
                if token == chain.native_token:
                    batch.add(client.w3.eth.get_balance(Account.from_key(profile.evm_private).address))
                else:
                    batch.add(contract.functions.balanceOf(profile.evm_address).call())
            try:
                balances = await batch.async_execute()
            except Web3RPCError as e:
                my_logger.warning(f'{chain} | {e}')
                balances = [0] * batch_size
            except TimeoutError as e:
                pass  # FIXME:
        all_balances += balances
    for balance, profile in zip(all_balances, profiles):
        token_amount = TokenAmount(balance, wei=True, token=token)
        if is_condition(token_amount):
            if echo:
                my_logger.info(f'{profile.id} | {profile.evm_address} ({chain}) | {token_amount}')
            total_by_chain += token_amount
    return total_by_chain


async def check_balance_batch_multicall(
        chains: list[Chain] = None, token: Token = Ethereum.native_token,
        is_condition=lambda x: x.ether > 0
):
    chains = chains or main_chains
    await token.get_token_info()
    await token.update_price()
    my_logger.success(f'1 {token.symbol} = {token.price}$')
    my_logger.info(repr(token))
    profiles = await db.get_all_from_table(Profile)
    total = 0
    full_log = f'{token.symbol} on wallets:\n'
    totals_by_chains = await asyncio.gather(
        *[_get_balance_multicall(chain, profiles, token, True, is_condition) for chain in chains]
    )
    for chain, total_by_chain in zip(chains, totals_by_chains):
        s = f'{total_by_chain.ether} {total_by_chain.token.symbol} ({chain}) = {total_by_chain.amount_in_usd:.2f}$'
        my_logger.info(s)
        full_log += s + '\n'
        total += total_by_chain.ether
    full_log += f'Total {token.symbol} in wallets: {total} {token.symbol} = {(total * token.price):.2f}$'
    my_logger.info(full_log)


async def check_balance_batch(chains: list[Chain] = None):
    chains = chains or main_chains
    await Ethereum.native_token.update_price()
    my_logger.success(f'1 ETH = {Ethereum.native_token.price}$')
    chains = chains or [Ethereum, Scroll, zkSync, Base, Zora, Optimism, Arbitrum]
    profiles = await db.get_all_from_table(Profile)
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


async def check_eth_activated_profile(profile: Profile, log_only_activated: bool = False) -> int | None:
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


async def deposit_token_to_okx(profile: Profile, amount: TokenAmount, use_full_balance: bool = False):
    client = Client(profile=profile, chain=amount.token.chain)
    balance = await client.balance_of(token=amount.token)
    client.chain.eip1559_tx = False
    TransactionParameters.gas_price_multiplier = 1.7
    if not balance:
        return
    if amount.token != client.chain.native_token:
        await client.transfer_token(
            to_checksum_address(profile.okx_deposit.evm),
            f'Deposit {amount} to OKX',
            amount,
            use_full_balance=use_full_balance,
        )
    else:
        await client.tx(
            to=to_checksum_address(profile.okx_deposit.evm),
            name=f'Deposit {amount} to OKX',
            use_full_balance=use_full_balance,
        )


async def info():
    profiles: list[Profile] = await db.get_rows_by_id(
        [1, 99, 101, 102, 103, 110, 113, 115, 120, 122, 124, 127], Profile
    )

    for profile in profiles:
        print(profile.evm_private)

    print()

    for profile in profiles:
        print(profile.proxy.proxy_string)

    for profile in profiles:
        await ProfileSession(profile).check_proxy()


async def main():
    profiles = await db.get_rows_by_id([105], Profile)
    await asyncio.gather(
        *[deposit_token_to_okx(profile, TokenAmount(0, token=Token(Scroll)), True) for profile in profiles]
    )


if __name__ == '__main__':
    SCR = Token(Scroll, address='0xd29687c813d741e2f938f4ac377128810e217b1b')
    # asyncio.run(check_balance_batch_multicall(chains=[Scroll], token=SCR))
    asyncio.run(check_balance_batch_multicall())
    # asyncio.run(main())
    # asyncio.run(info())
