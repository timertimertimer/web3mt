from typing import List, Optional, Union, Dict

from bitcoinrpc.bitcoin_rpc import BitcoinRPC
from bitcoinlib.keys import HDKey
from bitcoinlib.transactions import Transaction, Output
from httpx import AsyncClient

from web3mt.utils import httpxAsyncClient
from web3mt.utils.logger import logger
from web3mt.config import btc_env, DEV
from web3mt.onchain.btclike.models import Litecoin, Bitcoin
from web3mt.models import TokenAmount, Chain


class BitcoindRPCError(Exception):
    def __init__(self, code, message):
        self.code = code
        self.message = message


class _Space(httpxAsyncClient):
    def __init__(self, base_api_url: str):
        super().__init__(base_url=base_api_url)

    async def get_utxo(self, address: str) -> list[dict]:
        resp, data = await self.get(f"address/{address}/utxo")
        return data


class LitecoinSpace(_Space):
    def __init__(self):
        super().__init__(Litecoin.explorer.rstrip("/") + "/api")


class MempoolSpace(_Space):
    def __init__(self):
        super().__init__(Bitcoin.explorer.rstrip("/") + "/api")


# m / purpose' / coin_type' / account' / change / address_index
native_segwit_derivation_path = "m/84'/2'/0'/0/{i}"
space_api_map = {
    Bitcoin: MempoolSpace,
    Litecoin: LitecoinSpace,
}


class BaseClient(BitcoinRPC):
    def __init__(
        self,
        chain: Chain = Bitcoin,
        **kwargs,
    ):
        self.chain = chain
        client = kwargs.pop("client", AsyncClient(timeout=15))
        super().__init__(chain.rpc, client=client, **kwargs)

    def __str__(self):
        return f"{self.chain.name.capitalize()} BaseClient"

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

    async def get_block(self, hexstring: str):
        return await self.getblock(hexstring)


class Client(BaseClient):
    def __init__(
        self,
        chain: Chain = Bitcoin,
        mnemonic: str = btc_env.bitcoin_mnemonic,
        derivation_path: str = native_segwit_derivation_path.format(i=0),
        **kwargs,
    ):
        super().__init__(chain)
        self.master_key = HDKey.from_passphrase(
            mnemonic, network=self.chain.name.lower()
        )
        self.hk = self.master_key.subkey_for_path(
            path=derivation_path, network=self.chain.name.lower()
        )

    def __str__(self):
        return f"{self.hk.address()} ({self.chain.name.capitalize()})"

    async def get_balance(
        self, address_index: int = None, echo: bool = DEV
    ) -> tuple[TokenAmount, list[dict]]:
        if address_index:
            hk = self.master_key.subkey_for_path(
                path=native_segwit_derivation_path.format(i=address_index),
                network=self.chain.name.lower(),
            )
        else:
            hk = self.hk
        utxos = await space_api_map[self.chain]().get_utxo(hk.address())
        total = TokenAmount(token=self.chain.native_token, amount=0)
        for u in utxos:
            total.sats += u["value"]
        if echo:
            logger.info(
                f"{hk.address()}, index={self.hk.child_index} ({self.chain.name.capitalize()}) | Balance: {total}"
            )
        return total, utxos

    async def sign_tx(
        self,
        to: Optional[str] = None,
        amount: Optional[TokenAmount] = None,
        custom_outputs: Optional[list[Output]] = None,
        fee: Optional[TokenAmount] = None,
        use_full_balance: Optional[bool] = False,
    ):
        fee = fee or TokenAmount(token=self.chain.native_token, amount=0.0001)
        balance, utxos = await self.get_balance()

        if custom_outputs:
            amount = TokenAmount(
                token=self.chain.native_token,
                amount=sum(output.value for output in custom_outputs),
                is_sats=True,
            )
        elif use_full_balance:
            amount = balance - fee
        elif not amount:
            raise ValueError(
                "amount: BTCLikeAmount or custom_outputs: list[Output] or use_full_balance: bool is required"
            )
        if balance < amount + fee:
            logger.warning(
                f"{self} | Not enough balance to send transaction. Transfer amount={amount}, balance={balance}"
            )
            return None
        change: TokenAmount = balance - amount - fee
        tx = Transaction(
            network=self.chain.name.lower(),
            outputs=[Output(amount.sats, to, network=self.chain.name.lower())]
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
                Output(change.sats, self.hk.address(), network=self.chain.name.lower())
            )
        tx.sign()
        return tx.as_hex()

    async def transfer(
        self,
        to: Optional[str] = None,
        amount: Optional[TokenAmount] = None,
        custom_outputs: Optional[list[Output]] = None,
        fee: Optional[TokenAmount] = None,
        use_full_balance: Optional[bool] = False,
    ):
        sign_hash = await self.sign_tx(
            to=to,
            amount=amount,
            custom_outputs=custom_outputs,
            fee=fee,
            use_full_balance=use_full_balance,
        )
        if not sign_hash:
            return None
        tx_hash = await self.send_raw_transaction(sign_hash)
        if to:
            logger.debug(
                f"{self} | Transfer {amount} to {to} sent. Tx: {self.chain.explorer.rstrip('/')}/tx/{tx_hash}"
            )
        elif custom_outputs:
            logger.debug(
                f"{self} | Transfer "
                f"{', '.join([f'{TokenAmount(amount=output.value, is_sats=True, token=self.chain.native_token)} to {output._address}' for output in custom_outputs])}. "
                f"Tx: {self.chain.explorer.rstrip('/')}/tx/{tx_hash}"
            )
        return tx_hash
