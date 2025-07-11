import asyncio
from typing import List, Optional, Union, Dict, Literal

from bitcoinrpc.bitcoin_rpc import BitcoinRPC
from bitcoinlib.keys import HDKey
from bitcoinlib.transactions import Transaction, Output
from httpx import AsyncClient

from web3mt.utils import curl_cffiAsyncSession
from web3mt.utils.logger import logger
from web3mt.config import btc_env, DEV
from web3mt.onchain.btc.models import BTCLikeAmount, Token


class BitcoindRPCError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message


# m / purpose' / coin_type' / account' / change / address_index
native_segwit_derivation_path = "m/84'/2'/0'/0/{i}"


class Client(BitcoinRPC):
    def __init__(
        self,
        rpc: str = btc_env.bitcoin_public_rpc,
        network: Literal["bitcoin", "litecoin"] = "bitcoin",
        mnemonic: str = btc_env.bitcoin_mnemonic,
        derivation_path: str = native_segwit_derivation_path.format(i=0),
        **kwargs,
    ):
        self.network = network
        self.master_key = HDKey.from_passphrase(mnemonic, network=self.network)
        self.hk = self.master_key.subkey_for_path(
            path=derivation_path, network=self.network
        )
        client = kwargs.pop("client", AsyncClient(timeout=10))
        super().__init__(rpc, client=client, **kwargs)

    def __str__(self):
        return f"{self.hk.address()} ({self.network.capitalize()})"

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

    async def get_balance(
        self, address_index: int = None, echo: bool = DEV
    ) -> tuple[BTCLikeAmount, list[dict]]:
        if address_index:
            hk = self.master_key.subkey_for_path(
                path=native_segwit_derivation_path.format(i=address_index),
                network=self.network,
            )
        else:
            hk = self.hk
        utxos = await LitecoinSpace().get_utxo(hk.address())
        total = BTCLikeAmount(0, token=Token(chain=self.network))
        for u in utxos:
            total.sat += u["value"]
        if echo:
            logger.info(
                f"{hk.address()}, index={address_index or 0} ({self.network.capitalize()}) | Balance: {total}"
            )
        return total, utxos

    async def sign_tx(
        self,
        to: Optional[str] = None,
        amount: Optional[BTCLikeAmount] = None,
        custom_outputs: Optional[list[Output]] = None,
        fee: Optional[BTCLikeAmount] = None,
        use_full_balance: Optional[bool] = False,
    ):
        # FIXME: hardcode litecoin
        # FIXME: hardcode litecoin
        # FIXME: hardcode litecoin
        fee = fee or BTCLikeAmount(0.0001, token=Token(chain=self.network))
        balance, utxos = await self.get_balance()

        if custom_outputs:
            amount = BTCLikeAmount(
                sum(output.value for output in custom_outputs), is_sat=True
            )
        elif use_full_balance:
            amount = balance - fee
        elif not amount:
            raise ValueError("amount: BTCLikeAmount or custom_outputs: list[Output] or use_full_balance: bool is required")
        if balance < amount + fee:
            logger.warning(
                f"{self} | Not enough balance to send transaction. Transfer amount={amount}, balance={balance}"
            )
            return None
        change: BTCLikeAmount = balance - amount - fee
        tx = Transaction(
            network=self.network,
            outputs=[Output(amount.sat, to, network=self.network)]
            if to
            else custom_outputs,
        )
        for u in utxos:
            tx.add_input(
                prev_txid=u["txid"],
                output_n=u["vout"],
                value=u["value"],
                keys=[self.hk],
                witness_type="segwit",
            )
        if change > 0:
            tx.outputs.append(
                Output(change.sat, self.hk.address(), network=self.network)
            )
        tx.sign()
        return tx.as_hex()

    async def send_btc(
        self,
        to: Optional[str] = None,
        amount: Optional[BTCLikeAmount] = None,
        custom_outputs: Optional[list[Output]] = None,
        fee: Optional[BTCLikeAmount] = None,
        use_full_balance: Optional[bool] = False,
    ):
        sign_hash = await self.sign_tx(
            to=to, amount=amount, custom_outputs=custom_outputs, fee=fee
        )
        if not sign_hash:
            return None
        tx_hash = await self.send_raw_transaction(sign_hash)
        if to:
            logger.info(f"{self}) | Transfer {amount} to {to} sent. Tx: {tx_hash}")
        elif custom_outputs:
            logger.info(
                f"{self} | Transfer "
                f"{', '.join([f'{BTCLikeAmount(output.value, is_sat=True, token=Token(chain=self.network))} to {output._address}' for output in custom_outputs])}. "
                f"Tx: {tx_hash}"
            )
        return tx_hash


class LitecoinSpace(curl_cffiAsyncSession):
    def __init__(self, base_api_url: str = "https://litecoinspace.org"):
        super().__init__(base_url=base_api_url)

    async def get_utxo(self, address: str) -> list[dict]:
        resp, data = await self.get(f"api/address/{address}/utxo")
        return data
