import asyncio
from decimal import Decimal
from typing import Optional

from eth_account import Account

from eth_utils.address import to_checksum_address
from web3.exceptions import Web3RPCError, BadResponseFormat
from web3db import Profile
from web3db.core import create_db_instance

from web3mt.cex import OKX
from web3mt.models import Coin
from web3mt.onchain.evm.client import (
    ProfileClient,
    BaseClient,
    TransactionParameters,
)
from web3mt.onchain.evm.models import *
from web3mt.utils import logger, Profilecurl_cffiAsyncSession

main_chains = [
    Ethereum,
    Scroll,
    zkSync,
    Base,
    Zora,
    Optimism,
    Arbitrum,
    Linea,
    BSC,
    Polygon,
    Avalanche,
]
db = create_db_instance()


async def _get_balance(
        profile: Profile, chain: Chain, semaphore: asyncio.Semaphore
) -> TokenAmount:
    async with semaphore:
        client = ProfileClient(chain=chain, profile=profile)
        return await client.balance_of()


async def _get_balance_multicall(
        chain: Chain,
        profiles: list[Profile],
        token: Optional[Token] = None,
        echo: bool = False,
        is_condition=lambda x: x.ether > 0,
) -> TokenAmount:
    client = BaseClient(chain=chain)
    contract = None
    token = token or chain.native_token
    if token != chain.native_token:
        contract = client.w3.eth.contract(
            to_checksum_address(token.address), abi=DefaultABIs.token
        )
    total_by_chain = TokenAmount(0, token=token)
    batch_size = 10
    all_balances = []
    for i in range(0, len(profiles), batch_size):
        async with client.w3.batch_requests() as batch:
            for profile in profiles[i: i + batch_size]:
                if token == chain.native_token:
                    batch.add(
                        client.w3.eth.get_balance(
                            Account.from_key(profile.evm_private).address
                        )
                    )
                else:
                    batch.add(contract.functions.balanceOf(profile.evm_address).call())
            try:
                balances = await batch.async_execute()
            except Web3RPCError as exception:
                logger.warning(f"{chain} | {exception=}")
                balances = [0] * batch_size
            except (TimeoutError, BadResponseFormat) as exception:
                logger.warning(f"{chain} | {type(exception)=}, {exception=}")
                raise exception
        all_balances += balances
    for balance, profile in zip(all_balances, profiles):
        token_amount = TokenAmount(balance, is_wei=True, token=token)
        if is_condition(token_amount):
            if echo:
                logger.info(
                    f"{profile.id} | {profile.evm_address} ({chain}) | {token_amount}"
                )
            total_by_chain += token_amount
    return total_by_chain


async def check_balance_batch_multicall(
        chains: Optional[list[Chain]] = None,
        token: Optional[Token] = None,
        is_condition=lambda x: x.ether > 0,
):
    chains = chains or main_chains
    if token:
        await token.get_token_info()
        await token.update_price()
        logger.success(f"1 {token.symbol} = {token.price}$")
        logger.info(repr(token))
    else:
        native_tokens = {chain.native_token.symbol: Decimal(0) for chain in chains}
        for symbol in native_tokens:
            price = await OKX().get_coin_price(symbol)
            logger.success(f"1 {symbol} = {price}$")
    profiles = await db.get_all_from_table(Profile)
    if token:
        full_log = f"{token.symbol} on wallets:\n"
    else:
        full_log = ""
    totals_by_chains = await asyncio.gather(
        *[
            _get_balance_multicall(chain, profiles, token, True, is_condition)
            for chain in chains
        ]
    )
    total = 0
    for chain, total_by_chain in zip(chains, totals_by_chains):
        s = f"{total_by_chain.ether} {total_by_chain.token.symbol} ({chain}) = {total_by_chain.amount_in_usd or 1:.2f}$"
        logger.info(s)
        full_log += s + "\n"
        if not token:
            native_tokens[chain.native_token.symbol] += total_by_chain.ether
        else:
            total += total_by_chain.ether
    if token:
        full_log += f"Total {token.symbol} in wallets: {total} {token.symbol} = {(total * token.price):.2f}$"
        logger.info(full_log)
        return total * token.price
    else:
        total_in_usd = 0
        for symbol, amount in native_tokens.items():
            total_in_usd += amount * Coin.instances()[symbol].price
            logger.info(
                f"Total {symbol} in wallets: {amount} {symbol} = {(amount * Coin.instances()[symbol].price):.2f}$"
            )
        return total_in_usd


async def check_balance_batch(chains: list[Chain] = None):
    chains = chains or main_chains
    await Ethereum.native_token.update_price()
    logger.success(f"1 ETH = {Ethereum.native_token.price}$")
    chains = chains or [
        Ethereum,
        Scroll,
        zkSync,
        Base,
        Zora,
        Optimism,
        Arbitrum,
    ]
    profiles = await db.get_all_from_table(Profile)
    semaphore = asyncio.Semaphore(8)
    total = 0
    full_log = "Natives on wallets:\n"
    for chain in chains:
        total_balance: TokenAmount = sum(
            el
            for el in await asyncio.gather(
                *[
                    asyncio.create_task(_get_balance(profile, chain, semaphore))
                    for profile in profiles
                ]
            )
        )
        s = (
            f"{total_balance.ether} {total_balance.token.symbol} ({total_balance.token.chain}) = "
            f"{total_balance.amount_in_usd:.2f}$"
        )
        logger.info(s)
        full_log += s + "\n"
        total += total_balance.ether
    full_log += f"Total natives in wallets: {total} ETH = {(total * Ethereum.native_token.price):.2f}$"
    logger.info(full_log)


async def have_balance(
        client: ProfileClient, ethers: float = 0, echo: bool = False
) -> bool:
    balance = await client.balance_of(echo=echo)
    if balance.ether > ethers:
        return True
    return False


async def check_eth_activated_profile(
        profile: Profile, log_only_activated: bool = False
) -> int | None:
    client = ProfileClient(profile=profile)
    nonce = await client.nonce()
    log = f"{client} | Nonce - {nonce}"
    if nonce == 0:
        if not log_only_activated:
            logger.warning(log)
        return None
    else:
        logger.success(log)
        return profile.id


async def deposit_token_to_okx(
        profile: Profile, amount: TokenAmount, use_full_balance: bool = False
):
    client = ProfileClient(profile=profile, chain=amount.token.chain)
    balance = await client.balance_of(token=amount.token)
    client.chain.eip1559_tx = False
    TransactionParameters.gas_price_multiplier = 1.7
    if not balance:
        return
    if amount.token != client.chain.native_token:
        await client.transfer_token(
            to_checksum_address(profile.okx_deposit.evm),
            f"Deposit {amount} to OKX",
            amount,
            use_full_balance=use_full_balance,
        )
    else:
        await client.tx(
            to=to_checksum_address(profile.okx_deposit.evm),
            name=f"Deposit {amount} to OKX",
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
        await Profilecurl_cffiAsyncSession(profile).check_proxy()


async def sign(profile: Profile, message: str):
    client = ProfileClient(profile=profile)
    print(client.sign(message))


async def main():
    profiles = await db.get_rows_by_id([1], Profile)
    await asyncio.gather(*[sign(profile, "Welcome to Cysic！") for profile in profiles])


if __name__ == "__main__":
    asyncio.run(check_balance_batch_multicall())
    # SAHARA_TOKEN = Token(chain=BSC, address="0xFDFfB411C4A70AA7C95D5C981a6Fb4Da867e1111")
    # total = asyncio.run(check_balance_batch_multicall([BSC], SAHARA_TOKEN))
    # for chain_name, tokens_dict in TOKENS.items():
    #     for token_name, token in tokens_dict.items():
    #         total += asyncio.run(check_balance_batch_multicall([token.chain], token))
    # logger.info(total)
    # asyncio.run(check_balance_batch_multicall([Linea], LINEA_TOKENS['LXP']))
    # asyncio.run(check_balance_batch_multicall([Zora], ZORA_TOKENS["ZORA"]))
    # asyncio.run(check_balance_batch_multicall([zkSync], ZKSYNC_TOKENS["USDC"]))
    # asyncio.run(main())
    # asyncio.run(info())
