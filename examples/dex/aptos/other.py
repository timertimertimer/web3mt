import asyncio

from web3db import Profile

from config import *
from web3mt.local_db import DBHelper
from web3mt.onchain.aptos import Client, BlueMove
from web3mt.onchain.aptos.models import Token, TokenAmount
from web3mt.utils import my_logger, FileManager

db = DBHelper()


async def bluemove_batch_sell(profile: Profile):
    client = Client(profile)
    balance = await client.nfts_data(COLLECTION_ID)
    my_logger.info(f"{profile.id} | {client.account_.address()} | Balance of aptmap - {balance}")
    for data in balance[: int(len(balance) * AMOUNT_PERCENTAGE / 100)]:
        payload = await FileManager.read_json_async("payload.json")
        token_name = data["current_token_data"]["token_name"]
        my_logger.info(f"{profile.id} | Selling {token_name}")
        storage_id = data["storage_id"]
        payload["arguments"][0] = [{"inner": storage_id}]
        payload["arguments"][2] = [f"{int(TokenAmount(PRICE).wei)}"]
        await client.send_transaction(payload)


async def bluemove_batch_edit_sell_price(profile: Profile):
    client = Client(profile)
    balance = await client.nfts_data(COLLECTION_ID)
    my_logger.info(f"{client.profile.id} | {client.account_.address()} | Balance of aptmap - {balance}")
    for data in balance:
        payload = await FileManager.read_json_async("payload.json")
        token_name = data["current_token_data"]["token_name"]
        my_logger.info(f"{client.profile.id} | Changing price of {token_name}")
        storage_id = data["storage_id"]
        payload["arguments"] += [{"inner": storage_id}, "6000000"]
        await client.send_transaction(payload)


async def sell_all_aptmaps(profile: Profile):
    async with BlueMove(profile) as client:
        not_listed_aptmaps = await client.v2_token_data(COLLECTION_ID)
        listed_aptmaps = await client.get_listed_nfts()
        for listed_aptmap in listed_aptmaps:
            price = int(TokenAmount(listed_aptmap["attributes"]["price"], wei=True).ether)
            listing_id = listed_aptmap["attributes"]["listing_id"]
            token_name = listed_aptmap["attributes"]["name"]
            my_logger.info(f"{client.log_info} | Current listing info: {token_name} - {price} APT")
            if price > PRICE:
                await client.edit_listing_price(token_name, listing_id, PRICE)

        await client.batch_list_token_v2([aptmap["storage_id"] for aptmap in not_listed_aptmaps], PRICE)


async def verify(profile: Profile):
    client = Client(profile)
    await client.verify_transaction("0xf2d1ede2c22f254a88ae9d3f7150543be8de8df867e97349eca3f25daa2d3582", "smt")


async def check_balance_batch() -> None:
    await Token().update_price()
    total: TokenAmount = sum(await asyncio.gather(*[
        asyncio.create_task(Client(profile).balance(echo=True)) for profile in await db.get_all_from_table(Profile)
    ]))
    my_logger.info(f'Total: {total}')


async def withdraw_to_okx(profile: Profile):
    client = Client(profile=profile)
    balance = await client.account_balance(client.account_.address())
    await client.transfer(client.account_, profile.okx_aptos_address, int(balance * 0.8))
    my_logger.info(
        f"{profile.id} | {profile.aptos_address} | Sent {TokenAmount(balance * 0.8, wei=True)} APT to {profile.okx_aptos_address}"
    )


async def test(profile: Profile):
    client = Client(profile)
    await client.nfts_data()


async def main():
    tasks = []
    profiles: list[Profile] = await db.get_rows_by_id([1], Profile)
    for profile in profiles:
        tasks.append(asyncio.create_task(test(profile)))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    print(asyncio.run(check_balance_batch()))
