import os
import asyncio

from web3db import DBHelper, Profile
from dotenv import load_dotenv

from web3mt.onchain.evm.client import ProfileClient
from web3mt.onchain.evm.models import Token
from web3mt.utils import Profilecurl_cffiAsyncSession, logger, set_windows_event_loop_policy, FileManager

load_dotenv()
set_windows_event_loop_policy()

db = DBHelper(os.getenv('CONNECTION_STRING'))
abi = FileManager.read_json('abi.json')
token_address = '0xC71B5F631354BE6853eFe9C3Ab6b9590F8302e81'


async def claim(profile: Profile):
    headers = {
        'Host': 'pub-88646eee386a4ddb840cfb05e7a8d8a5.r2.dev',
        'Origin': 'https://polyhedra.foundation',
        'Referer': 'https://polyhedra.foundation/'
    }
    client = ProfileClient(profile=profile)
    contract = client.w3.eth.contract(
        address=client.w3.to_checksum_address('0x9234f83473C03be04358afC3497d6293B2203288'),
        abi=abi
    )
    async with Profilecurl_cffiAsyncSession(profile, headers=headers, sleep_echo=False) as session:
        response, data = await session.get(
            url=f'https://pub-88646eee386a4ddb840cfb05e7a8d8a5.r2.dev/eth_data/{profile.evm_address[2:5].lower()}.json',
            headers=headers,
            verify=True,
            retry_count=10
        )
        if not data:
            return 0
        amount = 0
        address = client.w3.to_checksum_address(profile.evm_address)
        if address in data:
            data = data[address]
            amount = int(data['amount'], 16)
            index = data['index']
            merkle_proof = data['proof']
            if await contract.functions.isClaimed(index).call():
                logger.success(f'{profile.id} | {address} | Already claimed {int(amount / 1.e18)} ZK')
                return int(amount / 1.e18)
            await client.tx(
                to=contract.address,
                name='Polyhedra ZK',
                data=contract.encodeABI('claim', args=[index, address, amount, merkle_proof]),
                check_existing=False
            )
        return amount


async def send_to_okx(profile: Profile):
    client = ProfileClient(profile=profile)
    balance = await client.balance_of(token=Token(chain=client.chain, address=token_address))
    if balance.wei > 0:
        ok, tx_hash_or_err = await client.transfer_token(
            to=profile.okx_evm_address,
            amount=balance,
            token_address=token_address
        )
        await client.verify_transaction(tx_hash_or_err, f'Transfer {balance.ether} ZK to OKX')


async def main():
    tasks = []
    profiles: list[Profile] = await db.get_all_from_table(Profile)
    for profile in profiles:
        tasks.append(asyncio.create_task(send_to_okx(profile)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
