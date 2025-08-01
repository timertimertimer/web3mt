import asyncio
import redis.asyncio as redis
from httpx import AsyncClient

from web3mt.onchain.btclike.client import BaseClient
from web3mt.utils import logger


def add_unique_to_list(redis_client, key, value):
    if value not in redis_client.lrange(key, 0, -1):
        redis_client.rpush(key, value)


redis_client = redis.Redis(host="localhost", port=6379, decode_responses=True)

receivers = dict()


class WatcherClient:
    def __init__(self):
        self.client = AsyncClient(
            base_url="http://92.53.84.182:8095",
            headers={"Contet-Type": "application/json"},
        )

    async def append_addresses_to_watchlist(
        self, addresses: list[str] | list[dict]
    ) -> None:
        if isinstance(addresses[0], dict):
            addresses = [el["value"] for el in addresses]
        await redis_client.sadd("addresses", *addresses)
        existing_addresses = await redis_client.smembers("addresses")
        response = await self.client.post(
            "/watcher.addresses.v1.AddressesService/UpdateWatchList",
            json={
                "addresses": [
                    {"value": el, "blockchain": "BLOCKCHAIN_BITCOIN"}
                    for el in existing_addresses
                ]
            },
            headers={"X-Client-ID": "00000000-0000-0000-0000-000000000000"},
        )
        data = response.json()
        return data


async def main():
    client = BaseClient()
    watcher_client = WatcherClient()
    best_block_hash = await client.getbestblockhash()
    block_hash = best_block_hash
    for i in range(100):
        block_data = await client.get_block(block_hash)
        print(f"Block height: {block_data['height']}")
        tx_receivers = dict()
        for tx in block_data["tx"]:
            try:
                tx_data = await client.getrawtransaction(tx)
            except Exception as e:
                logger.warning(f"{e}")
                continue
            for out in tx_data["vout"]:
                if "address" in out["scriptPubKey"]:
                    tx_receivers[out["scriptPubKey"]["address"]] = (
                        tx_receivers.get(out["scriptPubKey"]["address"], 0) + 1
                    )
        addresses = []
        for address, count in sorted(tx_receivers.items(), key=lambda x: -x[1]):
            if count > 10:
                addresses.append(address)
            else:
                break
        await watcher_client.append_addresses_to_watchlist(addresses)
        block_hash = block_data["previousblockhash"]

    print(receivers)
    print(sorted(receivers.items(), key=lambda x: -x[1]))
    return tx_data

if __name__ == "__main__":
    asyncio.run(main())