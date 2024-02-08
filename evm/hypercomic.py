import os
import aiohttp
import asyncio
from dotenv import load_dotenv

from better_proxy import Proxy
from aiohttp_proxy import ProxyConnector
from eth_account import Account

from web3db.core import DBHelper
from web3db.models import Profile
from web3db.utils import DEFAULT_UA, decrypt

from evm.client import Client
from evm.config import HYPERCOMIC_ABI_PATH
from models import zkSync
from utils import read_json, logger

load_dotenv()

url = 'https://play.hypercomic.io/Claim/actionZK/conditionsCheck2'
db = DBHelper(os.getenv('CONNECTION_STRING'))
contracts = {
    0: '0x4041db404315d7c63aaadc8d6e3b93c0bd99b779',
    1: '0x976Af522E63fA603b9d48e9207831bffb5dd4829',
    2: '0xD092E42453D6864ea98597461C50190e372d2448',
    3: '0x3C2F9D813584dB751B5EA7829B280b8cD160DE7B',
    4: '0x8F7b0e3407E55834F35e8c6656DaCcBF9f816964',
    5: '0x5798C80608ede921E7028a740596b98aE0d8095A'
}


async def get_signature(proxy_string: str, nft_number: int, client: Client):
    async with aiohttp.ClientSession(
            connector=ProxyConnector.from_url(
                url=Proxy.from_str(proxy=proxy_string).as_url, verify_ssl=False
            ), headers={'User-Agent': DEFAULT_UA}) as session:
        payload = {
            'trancnt': await client.nonce(),
            'walletgbn': 'Metamask',
            'wallet': client.account.address.lower(),
            'nftNumber': nft_number
        }
        response = await session.post(url, data=payload)
        return await response.text()


async def mint(profile: Profile):
    account = Account.from_key(decrypt(profile.evm_private, os.getenv('PASSPHRASE')))
    client = Client(account, zkSync)
    client.default_abi = read_json(HYPERCOMIC_ABI_PATH)
    for i, contract_address in contracts.items():
        contract = client.w3.eth.contract(
            address=client.w3.to_checksum_address(contract_address),
            abi=client.default_abi
        )
        if (await client.balance_of(contract_address)).Ether == 1:
            logger.info(f'{client.account.address} | Already minted')
            continue
        signature = (await get_signature(proxy_string=profile.proxy.proxy_string, nft_number=i, client=client)).strip()
        if not signature.startswith('0x'):
            logger.error(f'{client.account.address} | {signature}')
            continue
        signature = bytes.fromhex(signature[2:])
        await client.send_transaction(
            to=contract_address,
            data=contract.encodeABI('mint', args=[signature]),
            max_priority_fee_per_gas=100000000
        )


async def main():
    profiles: list[Profile] = await db.get_all_from_table(Profile)
    tasks = []
    for profile in profiles:
        tasks.append(asyncio.create_task(mint(profile)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
