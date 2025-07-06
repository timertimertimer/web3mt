import hmac
import time
import hashlib
from decimal import Decimal
from typing import Optional
from urllib.parse import urlencode

from web3mt.cex import Account
from web3mt.cex.base import CEX, ProfileCEX
from web3mt.cex.models import Asset, User
from web3mt.config import DEV, cex_env
from web3mt.models import Coin
from web3mt.utils import logger


class Binance(CEX):
    API_VERSION = 3
    MAIN_ENDPOINT = "https://api.binance.com"
    NAME = "Binance"

    async def make_request(
        self,
        method: str,
        url: str,
        api_key: str = cex_env.binance_api_key,
        api_secret: str = cex_env.binance_api_secret,
        **kwargs,
    ):
        if kwargs.get("without_headers"):
            return await super().make_request(method, url, **kwargs)
        params = kwargs.pop("params", {}) | {
            "timestamp": await self.get_server_timestamp()
            or str(int(time.time() * 10**3)),
            "recvWindow": 10000,
        }
        data = kwargs.pop("json", {})
        signature = hmac.new(
            api_secret.encode(),
            urlencode(params | data).encode(),
            hashlib.sha256,
        ).hexdigest()
        return await super().make_request(
            method,
            url,
            headers={
                "Content-Type": "application/json",
                "X-MBX-APIKEY": api_key,
            },
            params=params | {"signature": signature},
            json=data or None,
            **kwargs,
        )

    async def get_server_timestamp(self) -> int:
        _, data = await CEX.get(self, "/api/v3/time", without_headers=True)
        return int(data["serverTime"])

    async def get_coin_price(self, coin: str | Coin = "ETH") -> Decimal:
        if isinstance(coin, Coin):
            if coin.price:
                return coin.price
        else:
            coin = Coin(coin)
        usd_tickers = ["USDT", "USDC"]
        for usd_ticker in usd_tickers:
            _, data = await self.get(
                "api/v3/ticker/price",
                params={"symbol": f"{coin.symbol}{usd_ticker}"},
                without_headers=True,
            )
            if price := data.get("price"):
                return Decimal(price)
            elif data.get("msg") == "Invalid symbol.":
                logger.info(f"{self} | {data['msg']}. {coin.symbol}{usd_ticker}")
            else:
                logger.warning(f"{self} | {data['msg']}. {coin.symbol}-{usd_ticker}")
                return Decimal("0")
        return Decimal(0)

    async def get_funding_balance(
        self, user: User = None, coins: list[Coin] = None
    ) -> list[Asset]:
        user = user or self.main_user
        _, data = await self.post(url="/sapi/v1/asset/get-funding-asset")
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
        if DEV:
            logger.info(user.funding_account)
        return user.funding_account.assets

    async def get_trading_balance(
        self, user: User = None, omit_zero_balances: bool = False
    ) -> list[Asset]:
        user = user or self.main_user
        _, data = await self.post(url=f"/sapi/v3/asset/getUserAsset")
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
        if DEV:
            logger.info(user.trading_account)
        return user.trading_account.assets

    async def get_sub_account_list(self) -> list[User]:
        _, data = await self.get(url="/sapi/v1/sub-account/list")
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
            raise NotImplementedError
        _, data = await self.post(
            "/sapi/v1/asset/transfer",
            params=dict(
                type=type_,
                asset=asset.coin.symbol,
                amount=float(
                    amount or asset.total
                ),  # TODO: test on total/available/freeze
            ),
        )
        return data["tranId"]

    async def transfer_from_trading_to_funding(
        self, user: User, asset: Asset, amount: Optional[Decimal] = None
    ):
        return await self.transfer(
            user.trading_account, user.funding_account, asset, amount
        )

    async def transfer_from_spot_to_funding(
        self, user: User, asset: Asset, amount: Optional[Decimal] = None
    ):
        return await self.transfer_from_trading_to_funding(user, asset, amount)

    async def transfer_from_funding_to_trading(
        self, user: User, asset: Asset, amount: Optional[Decimal] = None
    ):
        return await self.transfer(
            user.trading_account, user.funding_account, asset, amount
        )

    async def transfer_from_funding_to_spot(
        self, user: User, asset: Asset, amount: Optional[Decimal] = None
    ):
        return await self.transfer_from_funding_to_trading(user, asset, amount)

    async def withdraw(
        self, coin: Coin, account: Account, chain_name: str, to: str, amount: Decimal
    ):
        # get total balance
        # transfer from spot to funding or vica versa
        # check if amount <= balance
        # withdraw
        # update balances
        _, data = await self.post(
            url=f"{self.MAIN_ENDPOINT}/sapi/v1/capital/withdraw/apply",
            json=dict(coin=coin.symbol),
        )


class ProfileBinance(ProfileCEX, Binance):
    async def make_request(self, method: str, url: str, **kwargs):
        return await super().make_request(
            method=method,
            url=url,
            api_key=self.profile.binance.api_key,
            api_secret=self.profile.binance.api_secret,
            **kwargs,
        )