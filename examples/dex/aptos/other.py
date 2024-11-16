import asyncio

from web3db import LocalProfile

from config import *
from web3mt.local_db import DBHelper
from web3mt.onchain.aptos import Client, BlueMove
from web3mt.onchain.aptos.models import Token, TokenAmount
from web3mt.utils import my_logger, FileManager

db = DBHelper()


async def bluemove_batch_sell(profile: LocalProfile):
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


async def bluemove_batch_edit_sell_price(profile: LocalProfile):
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


async def sell_all_aptmaps(profile: LocalProfile):
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
