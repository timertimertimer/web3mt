import asyncio
import httpx
from bitcoinrpc import BitcoinRPC
from bitcoinlib.keys import HDKey

from web3mt.consts import settings


class BaseClient:
    def __init__(self, account: HDKey, rpc: str = settings.BITCOIN_RPC):
        self.account = account or HDKey()
        self.w3 = BitcoinRPC(rpc, httpx.AsyncClient())

    @property
    def account(self) -> HDKey:
        return self._account

    @account.setter
    def account(self, account: HDKey):
        self._account: HDKey = account
        self._update_log_info()

    def _update_log_info(self):
        self.log_info = f'{self._account.address()} (Bitcoin)'  # FIXME: btc/bch/ltc

    async def tx(self):  # TODO
        ...

    async def balance_of(self):  # TODO
        ...

    async def send_btc(self):  # TODO
        ...


async def test(rpc: str):
    client = httpx.AsyncClient()
    async with BitcoinRPC(rpc, client) as rpc:
        data = await rpc.getblockchaininfo()
        return data


async def test_transfer():
    ...


async def main():
    for rpc in [settings.BITCOIN_RPC, settings.BITCOINCASH_RPC, settings.LITECOIN_RPC]:
        await test(rpc)


if __name__ == '__main__':
    asyncio.run(main())
