import asyncio
from eth_account import Account
from web3.exceptions import Web3RPCError
from web3db import LocalProfile
from config import *
from web3mt.onchain.evm.client import Client, BaseClient
from web3mt.onchain.evm.models import *
from web3mt.consts import Web3mtENV
from web3mt.onchain.evm.models import OP_Sepolia
from web3mt.local_db import DBHelper
from web3mt.utils import my_logger, sleep

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
    chains = chains or [Ethereum, Scroll, zkSync, Base, Zora, Optimism, Arbitrum]
    profiles = await db.get_all_from_table(LocalProfile)
    total = 0
    full_log = 'Natives on wallets:\n'
    totals_by_chains = await asyncio.gather(*[_get_balance_multicall(chain, profiles) for chain in chains])
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


async def opbnb_bridge(profile: LocalProfile, amount: float = 0.002):
    if await have_balance(Client(chain=opBNB, profile=profile)):
        return
    client = Client(chain=BNB, profile=profile)
    contract_address = '0xF05F0e4362859c3331Cb9395CBC201E3Fa6757Ea'
    client.default_abi = abis['opbnb_bridge']
    contract = client.w3.eth.contract(
        address=client.w3.to_checksum_address(contract_address),
        abi=client.default_abi
    )
    tx_hash = await client.tx(
        to=contract_address,
        name='opBNB bridge',
        data=contract.encodeABI('depositETH', args=[1, b'']),
        value=TokenAmount(amount).wei
    )
    if tx_hash:
        return tx_hash
    return False


async def decode_raw_input():
    client = Client(Ethereum)
    contract_abi = FileManager.read_json('evm/abis/zetachain/zetaswap.json')
    contract_address = '0xc6f7a7ba5388bFB5774bFAa87D350b7793FD9ef1'
    contract = client.w3.eth.contract(address=contract_address, abi=contract_abi)
    transaction_input = (
        '0xc7cd974800000000000000000000000000000000000000000000000000000000000000200000000000000000000'
        '000000000000000000000000000000000000000000120000000000000000000000000ef2e84afc6a01df147a0d5f9'
        '40825d4602eb1fd9000000000000000000000000000000000000000000000000000000e8d4a510000000000000000'
        '00000000000000000000000000000000000000000001ff22aba00000000000000000000000067297ee4eb097e072b'
        '4ab6f1620268061ae804640000000000000000000000008afb66b7ffa1936ec5914c7089d50542520208b80000000'
        '000000000000000000000000000000000000000000000000000000064000000000000000000000000000000000000'
        '00000000000000000000000002a000000000000000000000000000000000000000000000000000000000000003200'
        '000000000000000000000000000000000000000000000000000000000000149000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000002ca7d64a7efe2d62a72'
        '5e2b35cf7230d6677ffeeef2e84afc6a01df147a0d5f940825d4602eb1fd9d97b1de3619ed2c6beb3860147e30ca8'
        'a7dc98915f0b1a82749cb4e2278ec87f8bf6b618dc71a8bf000000000000000000000000000000000000000000000'
        '000000000001a140dfb000000000000000000000000000000000000000000000000000000e680992c000000000000'
        '000000000000000000000000000000000000000000000065e8fd0def2e84afc6a01df147a0d5f940825d4602eb1fd'
        '95645e18adbbc4171b83064293958b95c000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '00000000000000000000000000000000000000000000000000000000000000000000000000000000000004147cd50'
        '68148b40cbda99422da3ef23939d439e3904a829c11f55bc587678c6e952e0a6e5276c1ecf84a875f840dabc41c13'
        '103e0df313be5583807341ca833061b00000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000100000000000000000000000000000'
        '000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000'
        '00010438ed1739000000000000000000000000000000000000000000000000000000e680992c00000000000000000'
        '000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
        '000000000000000000a0000000000000000000000000ef2e84afc6a01df147a0d5f940825d4602eb1fd9000000000'
        '0000000000000000000000000000000000000000000000065e8d72900000000000000000000000000000000000000'
        '000000000000000000000000020000000000000000000000005f0b1a82749cb4e2278ec87f8bf6b618dc71a8bf000'
        '000000000000000000000d97b1de3619ed2c6beb3860147e30ca8a7dc989100000000000000000000000000000000'
        '000000000000000000000000'
    )
    print(contract.decode_function_input(transaction_input))


async def check_yogapetz_insights(profile: LocalProfile):
    client = Client(chain=opBNB, profile=profile)
    abi = abis['yogapets_insights']
    contract = client.w3.eth.contract(address='0x73A0469348BcD7AAF70D9E34BBFa794deF56081F', abi=abi)
    res = await contract.functions.questResults(client.account.address).call()
    if any(res):
        my_logger.success(
            f'{profile.id} | {client.account.address} | Uncommon: {res[0]}, Rare: {res[1]}, Legendary: {res[2]}, '
            f'Mythical: {res[3]}'
        )


async def polymer_faucet(profile: LocalProfile):
    client = Client(chain=OP_Sepolia, profile=profile)
    client.INCREASE_GWEI = 1.1
    while True:
        await client.tx(
            to='0x5c48ab8DFD7abd7D14027FF65f01887F78EfFE0F',
            data=(
                '0x24b5500000000000000000000000000042652e55a036d716cdd760543936e5a6c74523b16368616e6e656c2d343032373200'
                '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000008ca0'
            ),
            name='Polymer Faucet',
        )
        await sleep(130)


async def check_eth_activated_profile(profile: LocalProfile, log_only_acivated: bool = False) -> int | None:
    client = Client(profile=profile)
    nonce = await client.nonce()
    log = f'{client} | Nonce - {nonce}'
    if nonce == 0:
        if log_only_acivated:
            return
        my_logger.warning(log)
    else:
        my_logger.success(log)
        return profile.id


if __name__ == '__main__':
    asyncio.run(check_balance_batch_multicall())
