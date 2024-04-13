import os
import re
import asyncio
import random

from web3db import DBHelper, Profile
from dotenv import load_dotenv

from web3mt.evm import Client, Zora
from web3mt.utils import read_json, read_txt

load_dotenv()


class ZoraCo(Client):
    MINTER = '0x04E2516A2c207E84a1839755675dfd8eF6302F0a'

    def __init__(self, profile: Profile, links: list[str], referer: str = None):
        super().__init__(Zora, profile)
        self.referer = referer
        self.links = links
        self.abi = read_json('abi.json')

    async def start(self, quantity: int = 1):
        for link in self.links:
            contract_address, token_id = re.search('(0x[a-fA-F0-9]+)\/(\d+)', link).groups()
            contract = self.w3.eth.contract(address=contract_address, abi=self.abi)
            referer = random.choice([self.referer, None])
            await self.tx(
                contract.address, f'Mint {await contract.functions.name().call()}',
                contract.encodeABI('mintWithRewards', args=[
                    ZoraCo.MINTER, token_id, quantity, f'000000000000000000000000{self.account.address.lower()[2:]}',
                    referer or '0x0000000000000000000000000000000000000000'
                ])
            )


async def start(profile: Profile):
    async with ZoraCo(profile, links, referer) as client:
        if await client.get_native_balance():
            await client.start()


async def main():
    tasks = []
    db = DBHelper(os.getenv('CONNECTION_STRING'))
    profiles: list[Profile] = await db.get_all_from_table(Profile)

    for profile in profiles:
        tasks.append(asyncio.create_task(start(profile)))

    await asyncio.gather(*tasks)


if __name__ == '__main__':
    links = read_txt('links.txt').splitlines()
    referer = '0x4366E0C6ed744390EF6DA1cd3888FF476B088e2D'
    asyncio.run(main())
