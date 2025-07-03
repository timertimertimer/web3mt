import asyncio
from typing import List, Optional, Union, Dict, Literal

from bitcoinrpc.bitcoin_rpc import BitcoinRPC
from bitcoinlib.keys import HDKey
from bitcoinlib.transactions import Transaction, Output
from httpx import AsyncClient

from web3mt.utils import CustomAsyncSession
from web3mt.utils.logger import logger
from web3mt.config import btc_env
from web3mt.onchain.btc.models import BTCLikeAmount, Token


class BitcoindRPCError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message


native_segwit_derivation_path = "m/84'/2'/0'/0/0"


class Client(BitcoinRPC):
    def __init__(
        self,
        rpc: str = btc_env.bitcoin_public_rpc,
        network: Literal["bitcoin", "litecoin"] = "bitcoin",
        mnemonic: str = btc_env.bitcoin_mnemonic,
        derivation_path: str = native_segwit_derivation_path,
    ):
        self.network = network
        self.hk = HDKey.from_passphrase(mnemonic, network=self.network).subkey_for_path(
            path=derivation_path, network=self.network
        )
        super().__init__(rpc, AsyncClient(timeout=10))

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self._client.aclose()

    async def stop(self):
        return await self.acall("stop", [])

    async def get_tx_out(
        self, txid: str, n: int, include_mempool: Optional[bool] = True
    ):
        return await self.acall("gettxout", [txid, n, include_mempool])

    async def listunspent(
        self,
        minconf: Optional[int] = 1,
        maxconf: Optional[int] = 9999999,
        addresses: Optional[List] = None,
        query_options: Optional[Dict] = None,
    ):
        return await self.acall(
            "listunspent", [minconf, maxconf, addresses, query_options]
        )

    async def list_unspent(
        self,
        minconf: Optional[int] = 1,
        maxconf: Optional[int] = 9999999,
        addresses: Optional[List] = None,
        query_options: Optional[Dict] = None,
    ):
        return await self.listunspent(
            minconf=minconf,
            maxconf=maxconf,
            addresses=addresses,
            query_options=query_options,
        )

    async def sendrawtransaction(
        self, hexstring: str, maxfeerate: Optional[Union[int, str]] = 0.10
    ):
        return await self.acall("sendrawtransaction", [hexstring, maxfeerate])

    async def send_raw_transaction(
        self, hex_string: str, max_fee_rate: Optional[Union[int, str]] = 0.10
    ):
        return await self.sendrawtransaction(hex_string, max_fee_rate)

    async def get_blockchain_info(self):
        return await self.getblockchaininfo()

    async def sign_tx(
        self, to: str, amount: BTCLikeAmount, fee: Optional[BTCLikeAmount] = None
    ):
        # FIXME: hardcode litecoin
        # FIXME: hardcode litecoin
        # FIXME: hardcode litecoin
        utxos = await LitecoinSpace().get_utxo(self.hk.address())
        fee = fee or BTCLikeAmount(0.001, token=Token(chain=self.network))
        total = 0
        selected = []
        for u in utxos:
            selected.append(u)
            total += u["value"]
            if total >= amount.sat + fee.sat:
                break
        if total < amount.sat + fee.sat:
            raise Exception("Not enough balance")
        change = total - amount.sat - fee.sat
        tx = Transaction(network=self.network)
        for u in selected:
            tx.add_input(
                prev_txid=u["txid"],
                output_n=u["vout"],
                value=u["value"],
                keys=[self.hk],
                witness_type="segwit",
            )
        tx.outputs.append(Output(amount.sat, to, network=self.network))
        if change > 0:
            tx.outputs.append(Output(change, self.hk.address(), network=self.network))
        tx.sign()
        return tx.as_hex()

    async def send_btc(self, to: str, amount: BTCLikeAmount):
        sign_hash = await self.sign_tx(to=to, amount=amount)
        tx_hash = await self.send_raw_transaction(sign_hash)
        logger.info(
            f"{self.hk.address()} ({self.network.capitalize()}) | Transfer {amount} to {to} sent. Tx: {tx_hash}"
        )
        return tx_hash


class LitecoinSpace(CustomAsyncSession):
    def __init__(self, base_api_url: str = "https://litecoinspace.org"):
        super().__init__(base_url=base_api_url)

    async def get_utxo(self, address: str) -> list[dict]:
        resp, data = await self.get(f"api/address/{address}/utxo")
        return data


if __name__ == "__main__":
    asyncio.run(
        Client(
            rpc=btc_env.litecoin_rpc,
            network="litecoin",
            mnemonic=btc_env.litecoin_mnemonic,
        ).send_btc(
            to="ltc1q7qelkfpcua7ppkj58tgdk2ptlsdnkaqwjeq6pn",
            amount=BTCLikeAmount(0.01, token=Token(chain="litecoin")),
        )
    )
