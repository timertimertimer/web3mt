import asyncio
import redis.asyncio as redis

from web3mt.onchain.btclike.client import BaseClient

redis_client = redis.Redis(host='localhost', port=6379, decode_responses=True)

# get sender from vin tx

receivers = dict()

async def main():
    client = BaseClient()
    best_block_hash = await client.getbestblockhash()
    block_hash = best_block_hash
    for i in range(10):
        block_data = await client.get_block(block_hash)
        print(f"Block height: {block_data['height']}")
        tx_receivers = dict()
        for tx in block_data["tx"]:
            tx_data = await client.getrawtransaction(tx)
            for out in tx_data["vout"]:
                if 'address' in out['scriptPubKey']:
                    tx_receivers[out['scriptPubKey']['address']] = tx_receivers.get(out['scriptPubKey']['address'], 0) + 1
        for address, count in sorted(tx_receivers.items(), key=lambda x: -x[1]):
            if count > 10:
                receivers[address] = receivers.get(address, 0) + 1
            else:
                break
        block_hash = block_data['previousblockhash']
    print(receivers)
    print(sorted(receivers.items(), key=lambda x: -x[1]))
    return tx_data


if __name__ == "__main__":
    asyncio.run(main())