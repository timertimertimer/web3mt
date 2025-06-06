import asyncio
import httpx
from bitcoinrpc import BitcoinRPC
from bitcoinlib.keys import HDKey
from bitcoinutils.hdwallet import HDWallet
from bitcoinutils.setup import setup

from web3mt.consts import settings
setup('mainnet')

class BaseClient:
    def __init__(self, account: HDWallet, rpc: str = settings.BITCOIN_RPC):
        # self.account = account or HDKey()
        self.account = account or HDWallet()
        self.account.from_path("m/86'/0'/0'/0/0")
        self._taproot_address = self.account.get_private_key().get_public_key().get_taproot_address().to_string()
        self.account.from_path("m/84'/0'/0'/0/0")
        self._segwit_address = self.account.get_private_key().get_public_key().get_segwit_address().to_string()
        self._session = httpx.AsyncClient()
        self.w3 = BitcoinRPC(rpc, self._session)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._session.aclose()

    @property
    def account(self) -> HDWallet:
        return self._account

    @account.setter
    def account(self, account: HDWallet):
        self._account: HDWallet = account
        # self._update_log_info()

    # def _update_log_info(self):
    #     self.log_info = f'{self._account.} (Bitcoin)'  # FIXME: btc/bch/ltc

    async def tx(self):  # TODO
        ...

    async def balance_of(self):  # TODO
        ...

    async def send_btc(self):  # TODO
        ...

    async def get_utxo(self):
        response = await self._session.get(f'https://blockstream.info/api/address/{self._taproot_address}/utxo')
        data = response.json()
        return data


async def test(rpc: str):
    client = httpx.AsyncClient()
    async with BaseClient(account=HDWallet.from_mnemonic(settings.BITCOIN_MNEMONIC)) as client:
        utxo = await client.get_utxo()
        return utxo

    # async with BitcoinRPC(rpc, client) as rpc:
    #     data = await rpc.getblockchaininfo()
    #     return data


async def test_transfer():
    ...

async def send_btc():
    ...


async def main():
    for rpc in [settings.BITCOIN_RPC, settings.BITCOINCASH_RPC, settings.LITECOIN_RPC]:
        await test(rpc)


if __name__ == '__main__':
    asyncio.run(main())
