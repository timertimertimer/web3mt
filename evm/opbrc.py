import asyncio

from config import read_config
from logger import logger
from web3 import Web3
from utils import get_web3, get_accounts, get_address
from utils import get_gwei, get_nonce, get_chain_id

price_factor = 1.1
increase_gas = 1.2
data = '646174613a6170706c69636174696f6e2f6a736f6e2c7b2270223a226f70627263222c226f70223a226d696e74222c227469636b223a226f70626e227d'


async def main():
    config = read_config()
    opbrc = config['opbrc']
    node_url = opbrc['NODE_URL']
    w3 = await get_web3(node_url)
    target_address = w3.to_checksum_address('0x83b978cf73ee1d571b1a2550c5570861285af337')

    tasks = []
    gwei = w3.from_wei(number=await get_gwei(w3), unit='gwei')
    for private in get_accounts():
        wallet_address = get_address(private)
        tasks = [get_nonce(w3, wallet_address), get_chain_id(w3)]
        nonce, chain_id = await asyncio.gather(*tasks)
        transaction = {
            'from': wallet_address,
            'to': target_address,
            'gasPrice': w3.to_wei(gwei, 'gwei'),
            'nonce': nonce,
            'data': data,
            'chainId': chain_id,
            'value': 0
        }
        transaction['gas'] = int((await w3.eth.estimate_gas(transaction)) * increase_gas)
        signed_txn = w3.eth.account.sign_transaction(transaction, private)
        txn_hash = w3.to_hex(w3.keccak(await w3.eth.send_raw_transaction(signed_txn.rawTransaction)))
        logger.info(txn_hash)
        txn_receipt = await w3.eth.wait_for_transaction_receipt(txn_hash)
        logger.info(txn_receipt)


if __name__ == '__main__':
    asyncio.run(main())
