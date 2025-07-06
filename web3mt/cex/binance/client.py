import hmac
import time
import hashlib
from decimal import Decimal
from typing import Optional
from urllib.parse import urlencode

from web3mt.cex import Account, Trading
from web3mt.cex.base import CEX, ProfileCEX
from web3mt.cex.binance.models import Funding
from web3mt.cex.models import Asset, User
from web3mt.config import DEV, cex_env
from web3mt.models import Coin
from web3mt.utils import logger


class Binance(CEX):
    API_VERSION = 3
    URL = "https://api.binance.com"
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
            raise NotImplementedError  # TODO
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
        if not (transfer_id := data.get("tranId")):
            logger.warning(
                f"Could not transfer asset from {from_account.NAME} to {to_account.NAME}. Error: {data.get('msg') or data}"
            )
        return transfer_id

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
        self,
        coin: Coin,
        to: str,
        amount: Decimal,
        chain_name: str,
        from_account: type[Funding, Trading] = None,
        update_balance: bool = True,
    ):
        # TODO: get commissions and withdrawable status
        if not from_account:
            user = self.main_user
        else:
            user = from_account.user
        if update_balance:
            await self.update_balances(user)
        if not from_account:
            trading_account_asset = user.trading_account.get(coin)
            funding_account_asset = user.funding_account.get(coin)
            total_available_balance = (
                trading_account_asset.available_balance
                if trading_account_asset
                else 0 + funding_account_asset.available_balance
                if funding_account_asset
                else 0
            )
            if (
                trading_account_asset
                and trading_account_asset.available_balance > amount
            ):
                from_account = user.trading_account
            elif (
                funding_account_asset
                and funding_account_asset.available_balance > amount
            ):
                from_account = user.funding_account
            elif total_available_balance > amount:
                transfer_id = await self.transfer_from_trading_to_funding(user, trading_account_asset)
                if not transfer_id:
                    return None
                from_account = user.trading_account
            else:
                logger.warning(
                    f"Not enough balance to withdraw {coin}. Total available: {total_available_balance}. Funding: {user.funding_account.assets[coin].available_balance}, Spot: {user.funding_account.assets[coin].available_balance}"
                )
                return None
        _, data = await self.post(
            url=f"sapi/v1/capital/withdraw/apply",
            params=dict(
                coin=coin.symbol,
                network=chain_name,
                address=to,
                amount=str(amount),
                walletType={"Spot": 0, "Funding": 1}.get(from_account.NAME),
            ),
        )
        if not (withdraw_id := data.get("id")):
            logger.warning(f'{self} | Could not withdraw {coin} to {to}. Error: {data.get('msg') or data}')
        else:
            logger.success(f"{self} | Withdrew {amount} {coin} to {to}")
            if update_balance:
                await self.update_balances(user)
            else:
                from_account[coin].available_balance -= amount
        return withdraw_id

    async def get_all_supported_coins_info(self):
        _, data = await self.get('sapi/v1/capital/config/getall')
        return data


class ProfileBinance(ProfileCEX, Binance):
    async def make_request(self, method: str, url: str, **kwargs):
        return await super().make_request(
            method=method,
            url=url,
            api_key=self.profile.binance.api_key,
            api_secret=self.profile.binance.api_secret,
            **kwargs,
        )