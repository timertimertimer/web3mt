import asyncio
from abc import ABC, abstractmethod
from decimal import Decimal

from web3db import Profile

from web3mt.cex.models import User, Asset, Account
from web3mt.config import env
from web3mt.models import Coin
from web3mt.utils import logger
from web3mt.utils.http_sessions import (
    SessionConfig,
    httpxAsyncClient,
)

__all__ = ["CEX", "ProfileCEX"]


class CEX(httpxAsyncClient, ABC):
    API_VERSION = None
    URL = None
    NAME = ""

    def __init__(
        self, proxy: str = env.default_proxy, config: SessionConfig = None, **kwargs
    ):
        httpxAsyncClient.__init__(
            self, base_url=self.URL, proxy=proxy, config=config, **kwargs
        )
        self.main_user = User(self)

    def __repr__(self):
        return f"{self.config.log_info} | {self.NAME}"

    async def make_request(self, method: str, url: str = None, **kwargs):
        without_headers = kwargs.pop("without_headers", False)
        try:
            return await super().make_request(
                method=method,
                url=url,
                headers={} if without_headers else kwargs.pop("headers", {}),
                **kwargs,
            )
        except Exception as e:
            logger.error(e)
            raise e

    @abstractmethod
    async def get_coin_price(self, coin: str | Coin = "ETH") -> Decimal:
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
    async def transfer(self, from_account: Account, to_account: Account, asset: Asset):
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


class ProfileCEX(CEX, ABC):
    def __init__(self, profile: Profile, config: SessionConfig = None, **kwargs):
        config = config or SessionConfig()
        config.log_info = f"{profile.id}"
        super().__init__(
            proxy=profile.proxy.proxy_string,
            config=config,
            **kwargs,
        )
        self.profile = profile
