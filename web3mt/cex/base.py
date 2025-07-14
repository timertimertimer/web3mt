import asyncio
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import Callable, Any, Optional

from web3db import Profile

from web3mt.cex.models import User, Asset, Account
from web3mt.config import env, DEV
from web3mt.models import Coin, TokenAmount
from web3mt.utils import logger
from web3mt.utils.http_sessions import (
    SessionConfig,
    httpxAsyncClient,
)

__all__ = ["CEX", "ProfileCEX", "Account"]
usd_tickers = ["USDT", "USDC"]


class CEX(ABC):
    API_VERSION = None
    URL = None
    NAME = ""

    def __init__(
        self,
        api_key: Optional[str] = None,
        api_secret: Optional[str] = None,
        api_passphrase: Optional[str] = None,
        proxy: str = env.default_proxy,
        config: SessionConfig = None,
        **session_kwargs,
    ):
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        self._session = httpxAsyncClient(
            base_url=self.URL, proxy=proxy, config=config, **session_kwargs
        )
        self.main_user = User(self)

    def __repr__(self):
        return f"{self.NAME}"

    @abstractmethod
    async def make_request(self, *args, **kwargs):
        pass

    async def head(self, *a, **kw):
        return await self.make_request("HEAD", *a, **kw)

    async def get(self, *a, **kw):
        return await self.make_request("GET", *a, **kw)

    async def post(self, *a, **kw):
        return await self.make_request("POST", *a, **kw)

    async def put(self, *a, **kw):
        return await self.make_request("PUT", *a, **kw)

    async def patch(self, *a, **kw):
        return await self.make_request("PATCH", *a, **kw)

    async def delete(self, *a, **kw):
        return await self.make_request("DELETE", *a, **kw)

    async def options(self, *a, **kw):
        return await self.make_request("OPTIONS", *a, **kw)

    @abstractmethod
    async def get_server_timestamp(self):
        pass

    @abstractmethod
    async def get_coin_price(
        self, coin: str | Coin = "ETH", usd_ticker: str = "USDT"
    ) -> Optional[Decimal]:
        pass

    @abstractmethod
    async def get_funding_balance(
        self, user: User = None, coins: list[Coin] = None
    ) -> list[Asset]:
        pass

    @abstractmethod
    async def get_trading_balance(
        self, user: User = None, coins: list[Coin] = None
    ) -> list[Asset]:
        pass

    @abstractmethod
    async def get_sub_account_list(self) -> list[User]:
        pass

    @abstractmethod
    async def transfer(
        self,
        from_account: Account,
        to_account: Account,
        asset: Asset,
        amount: Optional[Decimal] = None,
    ):
        pass

    @abstractmethod
    async def withdraw(
        self,
        to: str,
        amount: TokenAmount,
        from_account: Optional[Account] = None,
        update_balance: bool = True,
    ):
        pass

    @abstractmethod
    async def get_all_supported_coins_info(self):
        pass

    async def update_balances(self, user: User = None):
        await self.get_funding_balance(user)
        await self.get_trading_balance(user)

    async def get_total_balance(self):
        users = [self.main_user, *(await self.get_sub_account_list())]
        total_balance = 0
        for user in users:
            await self.update_balances(user)
            total_balance += sum(
                [
                    el.available_balance * await self.get_coin_price(el.coin)
                    for el in user.funding_account.assets
                ]
            ) + sum(
                [
                    el.available_balance * await self.get_coin_price(el.coin)
                    for el in user.trading_account.assets
                ]
            )
            logger.info(user.funding_account)
            logger.info(user.trading_account)
        return total_balance

    async def collect_on_funding_master(self):
        await self.transfer_from_sub_accounts_to_master()

        if not self.main_user.trading_account.assets:
            await self.get_trading_balance()
        for asset in self.main_user.trading_account.assets:
            await self.transfer(
                self.main_user.trading_account, self.main_user.funding_account, asset
            )

    async def transfer_from_sub_accounts_to_master(self):
        async def process_sub_account(sub_user: User):
            await self.update_balances(sub_user)
            await asyncio.gather(
                *[
                    self.transfer(
                        from_account=sub_user.funding_account,
                        to_account=self.main_user.funding_account,
                        asset=asset,
                    )
                    for asset in sub_user.funding_account
                ]
            )

        await asyncio.gather(
            *[
                process_sub_account(sub_user)
                for sub_user in await self.get_sub_account_list()
            ]
        )

    def _get_coin_price_decorator(func: Callable) -> Callable:
        async def wrapper(self, coin: str | Coin = "ETH"):
            if isinstance(coin, Coin):
                if coin.price:
                    return coin.price
            else:
                coin = Coin(coin)

            for usd_ticker in usd_tickers:
                price = await func(self, coin=coin, usd_ticker=usd_ticker)
                if price is not None:
                    return price

            return Decimal("0")

        return wrapper

    def _get_funding_balance_decorator(func: Callable) -> Callable:
        async def wrapper(
            self, user: User = None, coins: list[Coin] = None
        ) -> list[Asset]:
            user = user or self.main_user
            assets = await func(self, user, coins)
            if DEV:
                logger.info(user.funding_account)
            return assets

        return wrapper

    def _get_trading_balance_decorator(func: Callable) -> Callable:
        async def wrapper(self, user: User = None) -> list[Asset]:
            user = user or self.main_user
            assets = await func(self, user)
            if DEV:
                logger.info(user.trading_account)
            return assets

        return wrapper

    def _withdraw_decorator(func: Callable) -> Callable:
        async def wrapper(
            self,
            to: str,
            amount: TokenAmount,
            from_account: Account = None,
            update_balance: bool = True,
            **kwargs,
        ) -> Any:
            # TODO: get commissions and withdrawable status
            if not from_account:
                user = self.main_user
            else:
                user = from_account.user
            if update_balance:
                await self.update_balances(user)
            if not from_account:
                trading_account_asset = (
                    user.trading_account.get(amount.token)
                    if user.trading_account
                    else None
                )
                funding_account_asset = (
                    user.funding_account.get(amount.token)
                    if user.funding_account
                    else None
                )
                total_available_balance = (
                    trading_account_asset.available_balance
                    if trading_account_asset
                    else 0 + funding_account_asset.available_balance
                    if funding_account_asset
                    else 0
                )
                if (
                    trading_account_asset
                    and trading_account_asset.available_balance >= amount.converted
                ):
                    from_account = user.trading_account
                elif (
                    funding_account_asset
                    and funding_account_asset.available_balance >= amount.converted
                ):
                    from_account = user.funding_account
                elif total_available_balance >= amount.converted:
                    transfer_id = await self.transfer_from_trading_to_funding(
                        user, trading_account_asset
                    )
                    if not transfer_id:
                        return None
                    from_account = user.trading_account
                else:
                    logger.warning(
                        f"Not enough balance to withdraw {amount.token}. Total available: {total_available_balance}. Funding: {user.funding_account.assets[amount.token].available_balance}, Spot: {user.funding_account.assets[amount.token].available_balance}"
                    )
                    return None

            withdraw_id, error_message_or_data = await func(
                self,
                to=to,
                amount=amount,
                from_account=from_account,
                update_balance=update_balance,
                **kwargs,
            )
            if not withdraw_id:
                logger.warning(
                    f"{self} | Could not withdraw {amount.token} to {to}. Error: {error_message_or_data}"
                )
            else:
                logger.success(f"{self} | Withdrew {amount} {amount.token} to {to}")
                if update_balance:
                    await self.update_balances(user)
                else:
                    from_account[amount.token].available_balance -= amount.converted
            return withdraw_id

        return wrapper

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


class ProfileCEX(CEX, ABC):
    def __init__(
        self,
        profile: Profile,
        config: SessionConfig = None,
        session_kwargs: dict = None,
    ):
        super().__init__(
            proxy=profile.proxy.proxy_string,
            config=config,
            session_kwargs=session_kwargs,
        )
        self.profile = profile

    def __repr__(self):
        return f"{self.profile.id} | {self.NAME}"
