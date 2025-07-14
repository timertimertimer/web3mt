import hmac
import time
import hashlib
from decimal import Decimal
from typing import Optional
from urllib.parse import urlencode

from web3mt.cex.base import CEX, ProfileCEX
from web3mt.cex.models import Asset, User, Account
from web3mt.config import cex_env, env
from web3mt.models import Coin
from web3mt.onchain.evm.models import TokenAmount
from web3mt.utils import logger


__all__ = ["Binance", "ProfileBinance"]

from web3mt.utils.http_sessions import SessionConfig


class Binance(CEX):
    API_VERSION = 3
    URL = "https://api.binance.com"
    NAME = "Binance"

    def __init__(
        self,
        api_key: str = cex_env.binance_api_key,
        api_secret: str = cex_env.binance_api_secret,
        proxy: str = env.default_proxy,
        config: SessionConfig = None,
    ):
        super().__init__(api_key, api_secret, proxy=proxy, config=config)

    async def make_request(
        self,
        method: str,
        url: str,
        **kwargs,
    ):
        if kwargs.get("without_headers"):
            return await self._session.make_request(method, url, **kwargs)
        params = kwargs.pop("params", {}) | {
            "timestamp": await self.get_server_timestamp()
            or str(int(time.time() * 10**3)),
            "recvWindow": 10000,
        }
        data = kwargs.pop("json", {})
        signature = hmac.new(
            self.api_secret.encode(),
            urlencode(params | data).encode(),
            hashlib.sha256,
        ).hexdigest()
        return await self._session.make_request(
            method,
            url,
            headers={
                "Content-Type": "application/json",
                "X-MBX-APIKEY": self.api_key,
            },
            params=params | {"signature": signature},
            json=data or None,
            **kwargs,
        )

    async def get_server_timestamp(self) -> int:
        _, data = await self._session.get("/api/v3/time", without_headers=True)
        return int(data["serverTime"])

    @CEX._get_coin_price_decorator
    async def get_coin_price(
        self, coin: str | Coin = "ETH", usd_ticker: str = "USDT"
    ) -> Decimal:
        _, data = await self._session.get(
            "api/v3/ticker/price",
            params={"symbol": f"{coin.symbol}{usd_ticker}"},
            without_headers=True,
        )
        if price := data.get("price"):
            return Decimal(price)

        msg = data.get("msg")
        if msg == "Invalid symbol.":
            logger.info(f"{self} | {msg}. {coin.symbol}{usd_ticker}")
        else:
            logger.warning(f"{self} | {msg}. {coin.symbol}-{usd_ticker}")
        return Decimal(0)

    @CEX._get_funding_balance_decorator
    async def get_funding_balance(self, user: User = None) -> list[Asset]:
        _, data = await self._session.post(url="/sapi/v1/asset/get-funding-asset")
        user.funding_account.assets = [
            Asset(
                Coin(
                    asset["asset"],
                ),
                available_balance=asset["free"],
                frozen_balance=asset["freeze"],
                total=sum(
                    [
                        Decimal(asset["free"]),
                        Decimal(asset["freeze"]),
                        Decimal(asset["locked"]),
                        Decimal(asset["withdrawing"]),
                    ]
                ),
            )
            for asset in data
        ]
        return user.funding_account.assets

    @CEX._get_trading_balance_decorator
    async def get_trading_balance(
        self, user: User = None, omit_zero_balances: bool = False
    ) -> list[Asset]:
        _, data = await self._session.post(url=f"/sapi/v3/asset/getUserAsset")
        user.trading_account.assets = [
            Asset(
                Coin(
                    asset["asset"],
                ),
                available_balance=asset["free"],
                frozen_balance=asset["freeze"],
                total=sum(
                    [
                        Decimal(asset["free"]),
                        Decimal(asset["freeze"]),
                        Decimal(asset["locked"]),
                        Decimal(asset["withdrawing"]),
                    ]
                ),
            )
            for asset in data
        ]
        return user.trading_account.assets

    async def get_sub_account_list(self) -> list[User]:
        _, data = await self._session.get(url="/sapi/v1/sub-account/list")
        return [
            User(self, sub_account["subUserId"]) for sub_account in data["subAccounts"]
        ]

    async def transfer(
        self,
        from_account: Account,
        to_account: Account,
        asset: Asset,
        amount: Optional[Decimal] = None,
    ):
        if from_account.ACCOUNT_ID == "SPOT" and to_account.ACCOUNT_ID == "FUNDING":
            type_ = "MAIN_FUNDING"
        elif from_account.ACCOUNT_ID == "FUNDING" and to_account.ACCOUNT_ID == "SPOT":
            type_ = "FUNDING_MAIN"
        else:
            raise NotImplementedError  # TODO
        _, data = await self._session.post(
            "/sapi/v1/asset/transfer",
            params=dict(
                type=type_,
                asset=asset.coin.symbol,
                amount=float(
                    amount or asset.total
                ),  # TODO: test on total/available/freeze
            ),
        )
        if not (transfer_id := data.get("tranId")):
            logger.warning(
                f"Could not transfer asset from {from_account.NAME} to {to_account.NAME}. Error: {data.get('msg') or data}"
            )
        return transfer_id

    @CEX._withdraw_decorator
    async def withdraw(
        self,
        to: str,
        amount: TokenAmount,
        chain_name: str,
        from_account: Account = None,
        update_balance: bool = True,
    ):
        _, data = await self.post(
            url=f"sapi/v1/capital/withdraw/apply",
            params=dict(
                coin=amount.token.symbol,
                network=chain_name,
                address=to,
                amount=str(amount),
                walletType={"Spot": 0, "Funding": 1}.get(from_account.NAME),
            ),
        )
        return data.get("id"), data

    async def get_all_supported_coins_info(self):
        _, data = await self.get("sapi/v1/capital/config/getall")
        return data


class ProfileBinance(ProfileCEX, Binance):
    async def make_request(self, method: str, url: str, **kwargs):
        return await Binance.make_request(
            self=self,
            method=method,
            url=url,
            api_key=self.profile.binance.api_key,
            api_secret=self.profile.binance.api_secret,
            **kwargs,
        )
