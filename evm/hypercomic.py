import os
import aiohttp
import asyncio
from dotenv import load_dotenv

from better_proxy import Proxy
from aiohttp_proxy import ProxyConnector

from web3db.core import DBHelper
from web3db.models import Profile
from web3db.utils import DEFAULT_UA

from evm.client import Client
from evm.config import HYPERCOMIC_ABI_PATH
from evm.examples import have_balance
from models import zkSync, TokenAmount
from utils import read_json, logger

load_dotenv()

url = 'https://play.hypercomic.io/Claim/actionZK/conditionsCheck2'
db = DBHelper(os.getenv('CONNECTION_STRING'))
contracts = {
    # 0: '0x4041db404315d7c63aaadc8d6e3b93c0bd99b779',
    # 1: '0x976Af522E63fA603b9d48e9207831bffb5dd4829',
    # 2: '0xD092E42453D6864ea98597461C50190e372d2448',
    # 3: '0x3C2F9D813584dB751B5EA7829B280b8cD160DE7B',
    # 4: '0x8F7b0e3407E55834F35e8c6656DaCcBF9f816964',
    # 5: '0x5798C80608ede921E7028a740596b98aE0d8095A',
    6: '0x9d405d767b5d2c3F6E2ffBFE07589c468d3fc04E',
    7: '0x02e1eb4547a6869da1e416cfd5916c213655aa24',
    8: '0x9f5417dc26622a4804aa4852dfbf75db6f8c6f9f',
    9: '0x761ccce4a16a670db9527b1a17eca4216507946f',
    10: '0xdc5401279a735ff9f3fab1d73d51d520dc1d8fdf',
    11: '0x8cc9502fd26222ab38a25eee76ae4c7493a3fa2a',
    12: '0xee8020254c67547cee7ff8df15ddbc1ffa0c477a',
    13: '0x3f332b469fbc7a580b00b11df384bdbebbd65588'
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
    client = Client(zkSync, profile)
    client.default_abi = read_json(HYPERCOMIC_ABI_PATH)
    enough_balance = await have_balance(client, ethers=0, echo=True)
    if not enough_balance:
        return
    for i, contract_address in contracts.items():
        contract = client.w3.eth.contract(
            address=client.w3.to_checksum_address(contract_address),
            abi=client.default_abi
        )
        if (await client.balance_of(token_address=contract_address)).Ether == 1:
            logger.success(f'{profile.id} | {client.account.address} | Already minted NFT #{i}')
            continue
        signature = (await get_signature(proxy_string=profile.proxy.proxy_string, nft_number=i, client=client)).strip()
        if not signature.startswith('0x'):
            if i == 6:
                logger.warning(f'{profile.id} | {client.account.address} | Need dmail transaction')
            else:
                logger.warning(
                    f'{profile.id} | {client.account.address} | Contract: {contract_address} Signature: {signature}')
            continue
        signature = bytes.fromhex(signature[2:])
        await client.send_transaction(
            to=contract_address,
            data=contract.encodeABI('mint', args=[signature]),
            max_priority_fee_per_gas=100000000,
            value=TokenAmount(0.00012).Wei
        )


async def main():
    # profiles: list[Profile] = await db.get_rows_by_id(
    #     [1, 99, 100, 101, 102, 103, 104, 105, 107, 108, 113, 114, 116],
    #     Profile
    # )
    profiles: list[Profile] = await db.get_rows_by_id([1], Profile)
    tasks = []
    for profile in profiles:
        tasks.append(asyncio.create_task(mint(profile)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
