from web3db.models import Profile

from web3 import Web3
from dotenv import load_dotenv

from web3mt.evm.client import Client
from web3mt.evm.models import BNB, opBNB
from web3mt.utils import read_json, logger

load_dotenv()
contract_address = '0xa4Aff9170C34c0e38Fed74409F5742617d9E80dc'


async def is_minted(client: Client) -> bool:
    minted = await client.balance_of(token_address=contract_address)
    if int(minted.Ether) == 1:
        return True
    return False


async def mint_profile(profile: Profile) -> str | bool:
    client = Client(BNB, profile)
    client.default_abi = read_json('abi.json')['profile']
    if await is_minted(client):
        logger.success(f'{profile.id} | {client.account.address} | Already minted')
        return True
    if (await client.get_native_balance()).Ether < 0.001:
        logger.info(f'{profile.id} | {profile.evm_address} | No balance, skipping')
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


async def mint_chip(profile: Profile, nonce: str, signature: str) -> bool:
    client = Client(opBNB, profile)
    contract = client.w3.eth.contract(
        address=client.w3.to_checksum_address('0x00a9de8af37a3179d7213426e78be7dfb89f2b19'),
        abi=read_json('abi.json')['ticket']
    )
    commodity_token = '0xe5116e725a8c1bF322dF6F5842b73102F3Ef0CeE'
    return await client.tx(
        to=contract_address, data=contract.encodeABI('safeBuyToken', args=[
            contract.address, commodity_token, client.account.address, 204, int(nonce, 16), signature
        ]),
        name='Mint chip'
    )
