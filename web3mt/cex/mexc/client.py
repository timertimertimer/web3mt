import hashlib
import hmac
import time
from typing import Optional

from _decimal import Decimal
from urllib.parse import urlencode

from web3mt.cex import CEX
from web3mt.cex.mexc.models import chains
from web3mt.cex.models import Asset, User, ChainNotExistsInLocalChains, Account
from web3mt.config import cex_env, env
from web3mt.models import Coin, TokenAmount
from web3mt.utils import logger


__all__ = ["MEXC"]

from web3mt.utils.http_sessions import SessionConfig


class MEXC(CEX):
    URL = "https://api.mexc.com"
    NAME = "MEXC"

    def __init__(
        self,
        api_key: str = cex_env.mexc_api_key,
        api_secret: str = cex_env.mexc_api_secret,
        proxy: str = env.default_proxy,
        config: SessionConfig = None,
    ):
        super().__init__(api_key, api_secret, proxy=proxy, config=config)

    async def make_request(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
        without_headers: bool = False,
        **kwargs,
    ):
        if without_headers:
            return await self._session.make_request(
                method, url, params=params, **kwargs
            )
        current_timestamp = int(await self.get_server_timestamp()) or time.time() * 1000
        params = (params or {}) | {
            "timestamp": current_timestamp,
        }
        signature = hmac.new(
            self.api_secret.encode(),
            urlencode(params).encode(),
            hashlib.sha256,
        ).hexdigest()
        return await self._session.make_request(
            method,
            url,
            headers={"Content-Type": "application/json", "X-MEXC-APIKEY": self.api_key},
            params=params | {"signature": signature},
            **kwargs,
        )

    async def get_server_timestamp(self):
        _, data = await self.get("/api/v3/time", without_headers=True)
        return data["serverTime"]

    @CEX._get_coin_price_decorator
    async def get_coin_price(
        self, coin: str | Coin = "ETH", usd_ticker: str = "USDT"
    ) -> Optional[Decimal]:
        _, data = await self.get(
            "/api/v3/ticker/bookTicker",
            params={"symbol": f"{coin.symbol}{usd_ticker}"},
            without_headers=True,
        )
        price = data.get("askPrice")
        if price:
            return Decimal(price)
        else:
            logger.warning(f"{self} | {data['msg']}. {coin.symbol}-{usd_ticker}")
        return None

    @CEX._get_funding_balance_decorator
    async def get_funding_balance(
        self, user: User = None, coins: list[Coin] = None
    ) -> Optional[list[Asset]]:
        logger.warning(f"{self} | Exchange doesn't have Funding account")
        return None

    @CEX._get_trading_balance_decorator
    async def get_trading_balance(
        self, user: User = None, coins: list[Coin] = None
    ) -> list[Asset]:
        _, data = await self.get("/api/v3/account")
        currencies = data["balances"]
        for currency in currencies:
            available = Decimal(currency.get("free", 0))
            frozen = Decimal(currency.get("locked", 0))
            total = available + frozen
            coin_symbol = currency["asset"]
            user.trading_account.assets.append(
                Asset(
                    coin=Coin(coin_symbol),
                    available_balance=available,
                    frozen_balance=frozen,
                    total=total,
                )
            )
        return user.trading_account.assets

    async def get_sub_account_list(self) -> list[User]:
        raise NotImplementedError

    async def transfer(
        self,
        from_account: Account,
        to_account: Account,
        asset: Asset,
        amount: Optional[Decimal] = None,
    ):
        raise NotImplementedError

    @CEX._withdraw_decorator
    async def withdraw(
        self,
        to: str,
        amount: TokenAmount,
        from_account: Optional[Account] = None,
        update_balance: bool = True,
    ):
        chain = chains.get(amount.token.chain)
        if not chain:
            logger.warning(f"{self} | {amount.token.chain} not in {self.NAME}")
            raise ChainNotExistsInLocalChains(
                f"{self} | {amount.token.chain} not in {self.NAME}"
            )
        _, data = await self.post(
            "/api/v3/capital/withdraw",
            params={
                "coin": amount.token.symbol,
                "address": to,
                "amount": str(amount.converted),
                "netWork": chain,
            },
        )
        return data.get("id"), data

    async def get_all_supported_coins_info(self, coin: Optional[Coin] = None):
        response, data = await self.get("/api/v3/capital/config/getall")
        if not data:
            logger.warning(
                f"{self} | Could not get all supported coins info. {response.text}"
            )
        if coin:
            for currency in data:
                if currency["coin"] == coin.symbol:
                    return currency
        return data
