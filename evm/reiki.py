from web3db.models import Profile

from evm.config import REIKI_ABI_PATH
from evm.client import Client
from logger import logger
from web3 import Web3

from evm.models import BNB
from utils import read_json
from dotenv import load_dotenv

load_dotenv()
contract_address = '0xa4Aff9170C34c0e38Fed74409F5742617d9E80dc'


async def is_minted(client: Client) -> bool:
    minted = await client.balance_of(token_address=contract_address)
    if int(minted.Ether) == 1:
        return True
    return False


async def mint(profile: Profile) -> str | bool:
    client = Client(BNB, profile)
    client.default_abi = read_json(REIKI_ABI_PATH)
    if await is_minted(client):
        logger.success(f'{profile.id} | {client.account.address} | Already minted')
        return True
    if (await client.get_native_balance()).Ether < 0.001:
        logger.info(f'{profile.id} | No balance, skipping')
        return False
    contract = client.w3.eth.contract(
        address=Web3.to_checksum_address(contract_address),
        abi=client.default_abi
    )
    ok, tx_hash = await client.send_transaction(
        to=contract_address,
        data=contract.encodeABI('safeMint', args=[str(client.account.address)])
    )
    if ok:
        return tx_hash
    return False
