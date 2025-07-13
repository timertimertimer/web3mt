import base64
import hashlib
import hmac
import json as json_lib
import time
from typing import Optional, Literal

from _decimal import Decimal
from urllib.parse import urlencode

from web3mt.cex import CEX, Account
from web3mt.cex.kucoin.models import chains
from web3mt.cex.models import Asset, User, ChainNotExistsInLocalChains
from web3mt.config import cex_env
from web3mt.models import Coin, TokenAmount
from web3mt.utils import logger


class Kucoin(CEX):
    URL = "https://api.kucoin.com"
    NAME = "Kucoin"

    async def make_request(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
        json: dict = None,
        api_passphrase: Optional[str] = cex_env.kucoin_api_passphrase,
        api_key: str = cex_env.kucoin_api_key,
        api_secret: str = cex_env.kucoin_api_secret,
        without_headers: bool = False,
        **kwargs,
    ):
        if without_headers:
            return await self._session.make_request(
                method, url, params=params, json=json, **kwargs
            )
        current_timestamp = (
            int((await self.get_server_timestamp())) or time.time() * 1000
        )
        payload = f"{str(current_timestamp)}{method}{url}{urlencode(params or {})}{json_lib.dumps(json) if json else ''}"
        signature = base64.b64encode(
            hmac.new(
                api_secret.encode("utf-8"), payload.encode("utf-8"), hashlib.sha256
            ).digest()
        )
        passphrase = base64.b64encode(
            hmac.new(
                api_secret.encode("utf-8"),
                api_passphrase.encode("utf-8"),
                hashlib.sha256,
            ).digest()
        )
        return await self._session.make_request(
            method,
            url,
            headers={
                "Content-Type": "application/json",
                "KC-API-SIGN": signature.decode("utf-8"),
                "KC-API-TIMESTAMP": str(current_timestamp),
                "KC-API-KEY": api_key,
                "KC-API-PASSPHRASE": passphrase.decode("utf-8"),
                "KC-API-KEY-VERSION": "2",
            },
            params=params,
            json=json,
            **kwargs,
        )

    async def get_server_timestamp(self) -> Optional[int]:
        _, data = await self.get("/api/v1/timestamp", without_headers=True)
        return int(data["data"])

    @CEX._get_coin_price_decorator
    async def get_coin_price(
        self, coin: str | Coin = "BTC", usd_ticker: str = "USDT"
    ) -> Optional[Decimal]:
        _, data = await self.get(
            "/api/v1/market/orderbook/level1",
            params={"symbol": f"{coin.symbol}-{usd_ticker}"},
            without_headers=True,
        )
        if data.get("code") != "200000":
            logger.warning(f"{self} | Could not get price for {coin}. {data}")
            return data
        data = data["data"]
        price = data.get("bestAsk")
        if price:
            return Decimal(price)
        else:
            logger.warning(f"{self} | {data['msg']}. {coin.symbol}-{usd_ticker}")
        return None

    async def get_all_accounts(self):
        _, data = await self.get("/api/v1/accounts")
        if data.get("code") != "200000":
            logger.warning(f"{self} | Couldn't get all user accounts. {data}")
            return data
        return data["data"]

    async def _get_account_detail(self, account_id: str):
        return await self.get(f"/api/v1/accounts/{account_id}")

    @CEX._get_funding_balance_decorator
    async def get_funding_balance(
        self, user: User = None, coins: list[Coin] = None
    ) -> list[Asset]:
        accounts = await self.get_all_accounts()
        for account in accounts:
            if account["type"] != "main":
                continue
            available = Decimal(account.get("available", 0))
            frozen = Decimal(account.get("holds", 0))
            total = Decimal(account.get("balance", 0))
            coin_symbol = account["currency"]
            user.funding_account.assets.append(
                Asset(
                    coin=Coin(coin_symbol),
                    available_balance=available,
                    frozen_balance=frozen,
                    total=total,
                )
            )
        return user.funding_account.assets

    @CEX._get_trading_balance_decorator
    async def get_trading_balance(
        self, user: User = None, coins: list[Coin] = None
    ) -> list[Asset]:
        accounts = await self.get_all_accounts()
        for account in accounts:
            if account["type"] != "trade":
                continue
            available = Decimal(account.get("available", 0))
            frozen = Decimal(account.get("holds", 0))
            total = Decimal(account.get("total", 0))
            coin_symbol = account["currency"]
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
        pass

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
        from_account: Optional[Account] = None,  # TODO
        update_balance: bool = True,
        withdraw_type: Literal["ADDRESS", "UID", "MAIL", "PHONE"] = "ADDRESS",
    ):
        chain = chains.get(amount.token.chain)
        if not chain:
            logger.warning(f"{self} | {amount.token.chain} not in {self.NAME}")
            raise ChainNotExistsInLocalChains(
                f"{self} | {amount.token.chain} not in {self.NAME}"
            )
        _, data = await self.post(
            "/api/v3/withdrawals",
            json={
                "currency": amount.token.symbol,
                "toAddress": to,
                "amount": str(amount.converted),
                "chain": chain,
                "withdrawType": withdraw_type,
            },
        )
        if not data.get("data"):
            return None, data
        data = data["data"]
        return data.get("withdrawalId"), data

    async def get_all_supported_coins_info(self, coin: Optional[Coin] = None):
        _, data = await self.get(
            f"/api/v3/currencies/{coin.symbol}",
            without_headers=True,
        )
        if data["code"] != "200000":
            logger.warning(f"{self} | Couldn't get all coins info. {data}")
        return data
