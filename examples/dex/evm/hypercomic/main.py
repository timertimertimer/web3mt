import asyncio
from web3mt.local_db import DBHelper, Profile
from web3mt.onchain.evm.client import Client
from web3mt.onchain.evm.models import zkSync, TokenAmount
from web3mt.utils import FileManager, my_logger, CustomAsyncSession

url = "https://play.hypercomic.io/Claim/actionZK/conditionsCheck2"
db = DBHelper()
contracts = {
    0: '0x4041db404315d7c63aaadc8d6e3b93c0bd99b779',
    1: '0x976Af522E63fA603b9d48e9207831bffb5dd4829',
    2: '0xD092E42453D6864ea98597461C50190e372d2448',
    3: '0x3C2F9D813584dB751B5EA7829B280b8cD160DE7B',
    4: '0x8F7b0e3407E55834F35e8c6656DaCcBF9f816964',
    5: '0x5798C80608ede921E7028a740596b98aE0d8095A',
    6: "0x9d405d767b5d2c3F6E2ffBFE07589c468d3fc04E",
    7: "0x02e1eb4547a6869da1e416cfd5916c213655aa24",
    8: "0x9f5417dc26622a4804aa4852dfbf75db6f8c6f9f",
    9: "0x761ccce4a16a670db9527b1a17eca4216507946f",
    10: "0xdc5401279a735ff9f3fab1d73d51d520dc1d8fdf",
    11: "0x8cc9502fd26222ab38a25eee76ae4c7493a3fa2a",
    12: "0xee8020254c67547cee7ff8df15ddbc1ffa0c477a",
    13: "0x3f332b469fbc7a580b00b11df384bdbebbd65588",
    14: "0x1a640bf545e04416df6ffa2f9cc4813003e52649",
}
abi = FileManager.read_json("abi.json")


async def get_signature(proxy_string: str, nft_number: int, client: Client):
    async with CustomAsyncSession(proxy_string) as session:
        payload = {
            "trancnt": await client.nonce(),
            "walletgbn": "Metamask",
            "wallet": client.account.address.lower(),
            "nftNumber": nft_number,
        }
        response = await session.post(url, data=payload)
        return await response.text()


async def mint(profile: Profile):
    client = Client(chain=zkSync, profile=profile)
    client.default_abi = abi
    if not await client.balance_of():
        my_logger.info(f"{client} | No balance, skipping")
        return
    for i, contract_address in contracts.items():
        contract = client.w3.eth.contract(
            address=client.w3.to_checksum_address(contract_address), abi=client.default_abi
        )
        if (await client.balance_of(contract=contract)).ether == 1:
            my_logger.success(f"{profile.id} | {client.account.address} | Already minted NFT #{i}")
            continue
        signature = (await get_signature(proxy_string=profile.proxy.proxy_string, nft_number=i, client=client)).strip()
        if not signature.startswith("0x"):
            if i == 6:
                my_logger.warning(f"{profile.id} | {client.account.address} | Need dmail transaction")
            else:
                my_logger.warning(
                    f"{profile.id} | {client.account.address} | Contract: {contract_address} Signature: {signature}"
                )
            continue
        signature = bytes.fromhex(signature[2:])

        await client.tx(
            to=contract_address,
            name='Mint',
            data=contract.encodeABI("mint", args=[signature]),
            max_priority_fee_per_gas=100000000 if i != 14 else 0,
            max_fee_per_gas=None if i != 14 else 100000000,
            value=TokenAmount(0.00012).wei if i != 14 else TokenAmount(0.00013).wei,
        )


async def main():
    profiles: list[Profile] = await db.get_all_from_table(Profile)
    tasks = []
    for profile in profiles:
        tasks.append(asyncio.create_task(mint(profile)))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
