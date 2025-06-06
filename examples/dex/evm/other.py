import asyncio
import random

from eth_utils import to_checksum_address, to_wei
from web3db import Profile, DBHelper

from examples.dex.evm.config import abis
from examples.onchain.evm.other import have_balance
from web3mt.onchain.evm.client import ProfileClient
from web3mt.onchain.evm.models import *
from web3mt.consts import env
from web3mt.onchain.evm.models import OP_Sepolia, Xterio
from web3mt.utils import my_logger, sleep, FileManager, CustomAsyncSession, ProfileSession
from web3mt.utils.custom_sessions import SessionConfig

db = DBHelper(env.LOCAL_CONNECTION_STRING)
main_chains = [Ethereum, Scroll, zkSync, Base, Zora, Optimism, Arbitrum]


async def opbnb_bridge(profile: Profile, amount: float = 0.002):
    if await have_balance(ProfileClient(chain=opBNB, profile=profile)):
        return
    client = ProfileClient(chain=BNB, profile=profile)
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
    client = ProfileClient(Ethereum)
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


async def check_yogapetz_insights(profile: Profile):
    client = ProfileClient(chain=opBNB, profile=profile)
    abi = abis['yogapets_insights']
    contract = client.w3.eth.contract(address='0x73A0469348BcD7AAF70D9E34BBFa794deF56081F', abi=abi)
    res = await contract.functions.questResults(client.account.address).call()
    if any(res):
        my_logger.success(
            f'{profile.id} | {client.account.address} | Uncommon: {res[0]}, Rare: {res[1]}, Legendary: {res[2]}, '
            f'Mythical: {res[3]}'
        )


async def polymer_faucet(profile: Profile):
    client = ProfileClient(chain=OP_Sepolia, profile=profile)
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


async def bridge_to_xterio(profile: Profile):
    if not await ProfileSession(profile, config=SessionConfig(sleep_after_request=False, retry_count=1)).check_proxy():
        profile.proxy.proxy_string = env.DEFAULT_PROXY

    bsc_client = ProfileClient(chain=BNB, profile=profile)
    xterio_client = ProfileClient(chain=Xterio, profile=profile)
    bsc_balance = await bsc_client.balance_of()
    xterio_balance = await xterio_client.balance_of()
    if (
            bsc_balance > TokenAmount(0.001, token=BNB.native_token)
            and xterio_balance < TokenAmount(0.0005, token=Xterio.native_token)
    ):
        contract = bsc_client.w3.eth.contract(
            '0xC3671e7E875395314bBad175b2b7F0EF75DA5339', abi=abis['bridge_to_xterio']
        )
        amount = TokenAmount(0.0003, token=BNB.native_token)
        await bsc_client.tx(
            contract.address,
            f'Bridge {amount} to Xterio',
            contract.encode_abi('bridgeETHTo', args=[bsc_client.account.address, 200000, b'7375706572627269646765']),
            amount
        )


async def main():
    profiles = await db.get_all_from_table(Profile)
    await asyncio.gather(*[bridge_to_xterio(profile) for profile in profiles])


if __name__ == '__main__':
    asyncio.run(main())
