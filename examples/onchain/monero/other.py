import asyncio
from decimal import Decimal

from web3mt.models import TokenAmount
from web3mt.onchain.monero.client import BaseClient
from web3mt.onchain.monero.models import XMR
from web3mt.utils import logger

client = BaseClient()

async def versions():
    node_version = await client.daemon.get_version()
    wallet_version = await client.wallet.get_version()
    logger.info(f"Node version: {node_version}")
    logger.info(f"Wallet version: {wallet_version}")

async def collect_on_primary_account():
    await client.collect_on_primary_account()

async def main():
    accounts = await client.wallet.get_accounts()
    amount = TokenAmount(token=XMR, amount=Decimal(0.1))
    addresses = [
        "89eCJipw7t4HgeCBy9myphMJ48NXYLdCvRoTk72hrdfkFFUidbtYjtsKrhpmtPJ1xPf69iMoief6U9H3zLqbyrcND6x33c7",  # mexc
        "83GUuR77xrScJv1oHXJjTmcXBa15xeGkY5fb4nmBJ1hjj9NpBC4bFdWXhRqAAc4NUEgAsnwMu8bUd1ZAMymDNufjK9szVkk",  # kucoin
        "89WUjP2hfHzRaBArMMXgxQaYABfGexR5aQNaeouF8LJoGRoVuEi35dsZKNf9qEqkdB1DQj9nH68ufDUXYCAUqbJLLJgC1bN",  # htx
    ]
    tx = await client.transfer(
        [{"amount": amount.converted, "address": address} for address in addresses],
        account_index=4,
    )
    return accounts

if __name__ == '__main__':
    asyncio.run(collect_on_primary_account())
