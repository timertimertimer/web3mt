import asyncio
import random
from abc import ABC
from decimal import Decimal
from eth_utils import to_checksum_address
from web3db import Profile

from web3mt.models import Coin
from web3mt.offchain.coingecko import CoinGecko
from web3mt.onchain.evm.client import ProfileClient, BaseClient
from web3mt.onchain.evm.models import *
from web3mt.utils import curl_cffiAsyncSession, Profilecurl_cffiAsyncSession, logger


class PriceImpactException(Exception):
    pass


class DEX(ABC):
    NAME = "DEX"
    SLIPPAGE = Decimal("0.5")
    MAX_FEE_IN_USD = Decimal(1)

    def __init__(
        self,
        session: curl_cffiAsyncSession = None,
        client: ProfileClient | BaseClient = None,
        profile: Profile = None,
    ):
        self.http_session = session or (
            Profilecurl_cffiAsyncSession(profile) if profile else curl_cffiAsyncSession()
        )
        self.evm_client = client or (
            ProfileClient(profile) if profile else BaseClient()
        )

    def __str__(self):
        return str(self.evm_client)

    def __repr__(self):
        return self.__str__()

    async def __aenter__(self):
        logger.debug(f"{self} | Session started")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.http_session.close()
        await self.evm_client.w3.provider.disconnect()

    async def close(self):
        return await self.__aexit__(None, None, None)

    async def get_weth_address(self, chain: Chain = None) -> str:
        chain = chain or self.evm_client.chain
        data = await CoinGecko().get_brief_coin_data(Coin("WETH", "WETH"))
        chain_name = {
            Optimism: "optimistic-ethereum",
            Arbitrum: "arbitrum-one",
            BSC: "binance-smart-chain",
        }.get(chain, chain.name.lower())
        return data["platforms"][chain_name]

    async def wrap_native(
        self,
        use_full_balance: bool = False,
        percentage: int = None,
        ether_amount: Decimal | float | int | str = None,
    ) -> Decimal:
        return await self._wrap_or_unwrap_native(
            use_full_balance, percentage, ether_amount
        )

    async def unwrap_native(
        self,
        use_full_balance: bool = True,
        percentage: int = None,
        ether_amount: Decimal | float | int | str = None,
    ):
        return await self._wrap_or_unwrap_native(
            use_full_balance, percentage, ether_amount, "Unwrap", "withdraw"
        )

    async def _wrap_or_unwrap_native(
        self,
        use_full_balance: bool = False,
        percentage: int = None,
        ether_amount: Decimal | float | int | str = None,
        method_name: str = "Wrap",
        abi_name: str = "deposit",
    ):
        balance = await self.evm_client.balance_of()
        if use_full_balance:
            amount = balance
        else:
            amount = ether_amount or balance * (
                percentage or random.randint(20, 30) / 100
            )
        contract = self.evm_client.w3.eth.contract(
            to_checksum_address(await self.get_weth_address()), abi=DefaultABIs.WETH
        )
        return await self.evm_client.tx(
            contract.address,
            f"{method_name} {balance.token}",
            contract.encodeABI(
                abi_name, args=[amount.wei] if abi_name == "Unwrap" else None
            ),
            value=amount if method_name == "Wrap" else TokenAmount(0),
            return_fee_in_usd=True,
            use_full_balance=use_full_balance if method_name == "Wrap" else False,
        )

    async def price_impact_defender(
        self, token_amount_in: TokenAmount, token_amount_out: TokenAmount
    ) -> Decimal:
        await asyncio.gather(
            *[
                CoinGecko().get_coin_price(token_amount_in.token),
                CoinGecko().get_coin_price(token_amount_out.token),
            ]
        )
        dex_slippage = (
            100 - (token_amount_out.amount_in_usd / token_amount_in.amount_in_usd) * 100
        )

        if dex_slippage > self.SLIPPAGE:
            raise PriceImpactException(
                f"{self.NAME} slippage: {dex_slippage:.3}% > Your slippage {self.SLIPPAGE}%"
            )

        return dex_slippage
