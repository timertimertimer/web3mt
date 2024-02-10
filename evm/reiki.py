import asyncio

from evm.config import REIKI_ABI_PATH
from evm.client import Client
from logger import logger
from web3 import Web3

from evm.models import BNB
from utils import get_accounts, read_json
from dotenv import load_dotenv

load_dotenv()
contract_address = '0xa4Aff9170C34c0e38Fed74409F5742617d9E80dc'


async def is_minted(client: Client) -> bool:
    minted = await client.balance_of(contract_address)
    if int(minted.Ether) == 1:
        return True
    return False


async def mint(client: Client) -> str | bool:
    if await is_minted(client):
        logger.success(f'Already minted', id=client.account.address)
        return True
    contract = client.w3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=client.default_abi
    )
    tx_hash = await client.send_transaction(
        to=contract_address,
        data=contract.encodeABI('safeMint', args=[str(client.account.address)])
    )
    if tx_hash:
        return tx_hash
    return False


async def main():
    accounts = get_accounts()
    tasks = []
    for account in accounts:
        client = Client(account, BNB)
        client.default_abi = read_json(REIKI_ABI_PATH)
        tasks.append(asyncio.create_task(mint(client)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
