import asyncio
from abc import ABC, abstractmethod
from decimal import Decimal
from functools import partialmethod

from curl_cffi.requests import RequestsError
from web3db import Profile

from web3mt.cex.models import User, Asset, Account
from web3mt.consts import env
from web3mt.models import Coin
from web3mt.utils import CustomAsyncSession, my_logger, ProfileSession
from web3mt.utils.custom_sessions import SessionConfig

__all__ = ['CEX']


class CEX(ABC):
    API_VERSION = None
    URL = None
    NAME = ''

    def __init__(
            self, profile: Profile = None,
            config: SessionConfig = None
    ):
        config = config or SessionConfig()
        self.profile = profile
        if profile:
            self.session = ProfileSession(profile=profile, config=config)
        else:
            self.session = CustomAsyncSession(proxy=env.DEFAULT_PROXY, config=config)
        self.main_user = User(self)
        self.log_info = str(profile.id) if profile else 'Main'

    def __repr__(self):
        return f'{self.log_info} | {self.NAME}'

    @abstractmethod
    def get_headers(self, path: str, method: str = 'GET', **kwargs):
        pass

    async def request(self, method: str, path: str, **kwargs):
        without_headers = kwargs.pop('without_headers', False)
        try:
            return await self.session.request(
                method, f'{self.URL}/{path}',
                headers={} if without_headers else self.get_headers(path, method, **kwargs), **kwargs
            )
        except RequestsError as e:
            my_logger.error(e)
            raise e

    head = partialmethod(request, "HEAD")
    get = partialmethod(request, "GET")
    post = partialmethod(request, "POST")
    put = partialmethod(request, "PUT")
    patch = partialmethod(request, "PATCH")
    delete = partialmethod(request, "DELETE")
    options = partialmethod(request, "OPTIONS")

    @abstractmethod
    async def get_coin_price(self, coin: str | Coin = 'ETH') -> Decimal:
        pass

    @abstractmethod
    async def get_funding_balance(self, user: User = None, coins: list[Coin] = None) -> list[Asset]:
        pass

    @abstractmethod
    async def get_trading_balance(self, user: User = None, coins: list[Coin] = None) -> list[Asset]:
        pass

    @abstractmethod
    async def get_sub_account_list(self) -> list[User]:
        pass

    @abstractmethod
    async def transfer(self, from_account: Account, to_account: Account, asset: Asset):
        pass

    async def get_total_balance(self):
        users = [self.main_user, *(await self.get_sub_account_list())]
        total_balance = 0
        for user in users:
            await self.get_funding_balance(user)
            await self.get_trading_balance(user)
            total_balance += (
                    sum([el.available_balance * await self.get_coin_price(el.coin) for el in
                         user.funding_account.assets]) +
                    sum([el.available_balance * await self.get_coin_price(el.coin) for el in
                         user.trading_account.assets])
            )
            my_logger.info(user.funding_account)
            my_logger.info(user.trading_account)
        return total_balance

    async def collect_on_funding_master(self):
        await self.transfer_from_sub_accounts_to_master()

        if not self.main_user.trading_account.assets:
            await self.get_trading_balance()
        for asset in self.main_user.trading_account.assets:
            await self.transfer(self.main_user.trading_account, self.main_user.funding_account, asset)

    async def transfer_from_sub_accounts_to_master(self):
        async def process_sub_account(sub_user: User):
            await self.get_funding_balance(sub_user)
            await self.get_trading_balance(sub_user)

            await asyncio.gather(*[
                self.transfer(
                    from_account=sub_user.funding_account,
                    to_account=self.main_user.funding_account,
                    asset=asset
                ) for asset in sub_user.funding_account
            ])

        await asyncio.gather(
            *[process_sub_account(sub_user) for sub_user in await self.get_sub_account_list()]
        )
