import os
import asyncio
import random
from web3db import DBHelper

from config import *
from web3mt.utils import *
from web3mt.evm.models import *
from web3mt.evm.client import *

from dotenv import load_dotenv

load_dotenv()

db = DBHelper(os.getenv('CONNECTION_STRING'))
passphrase = os.getenv('PASSPHRASE')


async def check_balance_batch(network: Chain):
    profiles = await db.get_all_from_table(Profile)
    tasks = []
    for profile in profiles:
        client = Client(network, profile, encryption_password=os.getenv('PASSPHRASE'))
        tasks.append(asyncio.create_task(client.get_native_balance(echo=True)))
    total = await asyncio.gather(*tasks)
    ans = 0
    for el in total:
        ans += el.Ether
    logger.info(f'Total: {ans} {network.coin_symbol}')


async def check_xp_linea():
    lxp_contract_address = '0xd83af4fbD77f3AB65C3B1Dc4B38D7e67AEcf599A'
    profiles = await db.get_all_from_table(Profile)
    tasks = []
    for profile in profiles:
        client = Client(Linea, profile)
        tasks.append(asyncio.create_task(client.balance_of(token_address=lxp_contract_address, echo=True)))
    result = await asyncio.gather(*tasks)
    logger.success(f'Total - {sum([el.Ether for el in result])} LXP')


async def have_balance(client: Client, ethers: float = 0, echo: bool = False, get_usd_price: bool = False) -> bool:
    balance = await client.get_native_balance(echo=echo, get_usd_price=get_usd_price)
    if balance.Ether > ethers:
        return True
    return False


async def get_wallets_with_balance(network: Chain):
    profiles = await db.get_all_from_table(Profile)
    tasks = []
    for profile in profiles:
        client = Client(network, account=Account.from_key(decrypt(profile.evm_private, os.getenv('PASSPHRASE'))))
        tasks.append(asyncio.create_task(have_balance(client)))
    await asyncio.gather(*tasks)


async def opbnb_bridge(profile: Profile, amount: float = 0.002):
    if await have_balance(Client(opBNB, profile)):
        return
    client = Client(BNB, profile)
    contract_address = '0xF05F0e4362859c3331Cb9395CBC201E3Fa6757Ea'
    client.default_abi = read_json(OPBNB_BRIDGE_ABI)
    contract = client.w3.eth.contract(
        address=client.w3.to_checksum_address(contract_address),
        abi=client.default_abi
    )
    tx_hash = await client.send_transaction(
        to=contract_address,
        data=contract.encodeABI('depositETH', args=[1, b'']),
        value=TokenAmount(amount).Wei
    )
    if tx_hash:
        return tx_hash
    return False


async def check_galxe_kyc(client: Client):
    await client.balance_of(token_address='0xE84050261CB0A35982Ea0f6F3D9DFF4b8ED3C012', echo=True)


async def withdraw_zeta(profile: Profile):
    client = Client(ZetaChain, profile)
    try:
        if (await client.get_native_balance()).Ether > 1.5:
            await client.send_transaction(
                to=profile.okx_evm_address.strip(),
                value=TokenAmount(random.uniform(1.4, 1.5)).Wei
            )
            await sleep(5)
    except TimeoutError:
        logger.error(f'{profile} | {profile.evm_address}')


async def decode_raw_input():
    client = Client(Ethereum)
    contract_abi = read_json('evm/abis/zetachain/zetaswap.json')
    contract_address = '0xc6f7a7ba5388bFB5774bFAa87D350b7793FD9ef1'
    contract = client.w3.eth.contract(address=contract_address, abi=contract_abi)
    transaction_input = '0xc7cd974800000000000000000000000000000000000000000000000000000000000000200000000000000000000000000000000000000000000000000000000000000120000000000000000000000000ef2e84afc6a01df147a0d5f940825d4602eb1fd9000000000000000000000000000000000000000000000000000000e8d4a51000000000000000000000000000000000000000000000000000000000001ff22aba00000000000000000000000067297ee4eb097e072b4ab6f1620268061ae804640000000000000000000000008afb66b7ffa1936ec5914c7089d50542520208b8000000000000000000000000000000000000000000000000000000000000006400000000000000000000000000000000000000000000000000000000000002a000000000000000000000000000000000000000000000000000000000000003200000000000000000000000000000000000000000000000000000000000000149000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000002ca7d64a7efe2d62a725e2b35cf7230d6677ffeeef2e84afc6a01df147a0d5f940825d4602eb1fd9d97b1de3619ed2c6beb3860147e30ca8a7dc98915f0b1a82749cb4e2278ec87f8bf6b618dc71a8bf000000000000000000000000000000000000000000000000000000001a140dfb000000000000000000000000000000000000000000000000000000e680992c000000000000000000000000000000000000000000000000000000000065e8fd0def2e84afc6a01df147a0d5f940825d4602eb1fd95645e18adbbc4171b83064293958b95c00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000004147cd5068148b40cbda99422da3ef23939d439e3904a829c11f55bc587678c6e952e0a6e5276c1ecf84a875f840dabc41c13103e0df313be5583807341ca833061b0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000010000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000000000000000000000000000000000000010438ed1739000000000000000000000000000000000000000000000000000000e680992c00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000a0000000000000000000000000ef2e84afc6a01df147a0d5f940825d4602eb1fd90000000000000000000000000000000000000000000000000000000065e8d72900000000000000000000000000000000000000000000000000000000000000020000000000000000000000005f0b1a82749cb4e2278ec87f8bf6b618dc71a8bf000000000000000000000000d97b1de3619ed2c6beb3860147e30ca8a7dc989100000000000000000000000000000000000000000000000000000000'
    print(contract.decode_function_input(transaction_input))


async def check_yogapetz_insights(profile: Profile):
    client = Client(opBNB, profile)
    abi = [
        {
            "inputs": [
                {
                    "internalType": "address",
                    "name": "",
                    "type": "address"
                }
            ],
            "name": "questResults",
            "outputs": [
                {
                    "internalType": "uint256",
                    "name": "uncommon",
                    "type": "uint256"
                },
                {
                    "internalType": "uint256",
                    "name": "rare",
                    "type": "uint256"
                },
                {
                    "internalType": "uint256",
                    "name": "legendary",
                    "type": "uint256"
                },
                {
                    "internalType": "uint256",
                    "name": "mythical",
                    "type": "uint256"
                }
            ],
            "stateMutability": "view",
            "type": "function"
        }
    ]
    contract = client.w3.eth.contract(address='0x73A0469348BcD7AAF70D9E34BBFa794deF56081F', abi=abi)
    res = await contract.functions.questResults(client.account.address).call()
    if any(res):
        logger.success(
            f'{profile.id} | {profile.evm_address} | Uncommon: {res[0]}, Rare: {res[1]}, Legendary: {res[2]}, Mythical: {res[3]}')


async def polymer_faucet(profile: Profile):
    client = Client(OP_Sepolia, profile, encryption_password=passphrase, wait_for_gwei=False)
    client.INCREASE_GWEI = 1.1
    while True:
        await client.tx(
            to='0x5c48ab8DFD7abd7D14027FF65f01887F78EfFE0F',
            data='0x24b5500000000000000000000000000042652e55a036d716cdd760543936e5a6c74523b16368616e6e656c2d3430323732000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000008ca0',
            name='Polymer Faucet',
        )
        await sleep(130)


async def withdraw_scroll(profile: Profile):
    client = Scroll(profile, passphrase)
    await client.withdraw()


async def main():
    profiles: list[Profile] = await db.get_rows_by_id([99], Profile)
    tasks = []
    for profile in profiles:
        tasks.append(asyncio.create_task(withdraw_scroll(profile)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
