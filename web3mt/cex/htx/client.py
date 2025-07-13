import base64
import hashlib
import hmac
import time
from typing import Optional
from urllib.parse import urlencode
from datetime import datetime, UTC

from _decimal import Decimal

from web3mt.cex.base import CEX
from web3mt.cex.htx.models import chains
from web3mt.cex.models import User, Asset, Account, ChainNotExistsInLocalChains
from web3mt.config import cex_env, DEV
from web3mt.models import Coin, TokenAmount
from web3mt.utils import logger


class HTX(CEX):
    URL = "https://api.huobi.pro"
    NAME = "HTX"

    async def make_request(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
        api_key: str = cex_env.htx_api_key,
        api_secret: str = cex_env.htx_api_secret,
        without_headers: bool = False,
        **kwargs,
    ):
        if without_headers:
            return await self._session.make_request(
                method, url, params=params, **kwargs
            )
        current_timestamp = (
            int((await self.get_server_timestamp()) / 1000) or time.time()
        )
        params = (params or {}) | {
            "AccessKeyId": api_key,
            "SignatureMethod": "HmacSHA256",
            "SignatureVersion": "2",
            "Timestamp": datetime.fromtimestamp(current_timestamp, UTC).strftime(
                "%Y-%m-%dT%H:%M:%S"
            ),
        }
        params_string = urlencode(sorted(params.items()))
        payload = f"{method}\n{self.URL.lstrip('https://')}\n{url}\n{params_string}"
        signature = base64.b64encode(
            hmac.new(api_secret.encode(), payload.encode(), hashlib.sha256).digest()
        ).decode()
        return await self._session.make_request(
            method,
            url,
            params=params | {"Signature": signature},
            **kwargs,
        )

    async def get_server_timestamp(self) -> int:
        _, data = await self.get("/v1/common/timestamp", without_headers=True)
        return int(data["data"])

    @CEX._get_coin_price_decorator
    async def get_coin_price(
        self, coin: str | Coin = "ETH", usd_ticker: str = "USDT"
    ) -> Optional[Decimal]:
        _, data = await self.get(
            "/market/detail/merged",
            params={"symbol": f"{coin.symbol.lower()}{usd_ticker.lower()}"},
            without_headers=True,
        )
        tick = data.get("tick", {})
        price = tick.get("ask", [])[0]
        if price:
            return Decimal(price)
        else:
            logger.warning(f"{self} | {data['msg']}. {coin.symbol}-{usd_ticker}")
        return None

    async def get_all_accounts(self):
        _, data = await self.get("/v1/account/accounts")
        if data["status"] != "ok":
            logger.warning(
                f"{self} | Couldn't get all user accounts. {data['err-msg']}"
            )
            return None
        return data["data"]

    @CEX._get_funding_balance_decorator
    async def get_funding_balance(
        self, user: User = None, coins: list[Coin] = None
    ) -> Optional[list[Asset]]:
        logger.warning(f"{self} | Exchange doesn't have Funding account")
        return None

    @CEX._get_trading_balance_decorator
    async def get_trading_balance(self, user: User = None) -> Optional[list[Asset]]:
        accounts = await self.get_all_accounts()
        main_spot = accounts[0]
        _, data = await self.get(f"/v1/account/accounts/{main_spot['id']}/balance")
        if data["status"] != "ok":
            logger.warning(f"{self} | Couldn't get Spot balance. {data['err-msg']}")
            return None
        currencies = data["data"]["list"]
        for currency in currencies:
            available = Decimal(currency.get("available", 0))
            frozen = Decimal(currency.get("frozen", 0))
            total = Decimal(currency.get("balance", 0))
            coin_symbol = currency["currency"].upper()
            if total == 0:
                continue
            existing_asset = user.trading_account.get(coin_symbol)
            if existing_asset:
                existing_asset.available_balance = (
                    available or existing_asset.available_balance
                )
                existing_asset.frozen_balance = frozen or existing_asset.frozen_balance
                existing_asset.total = (
                    existing_asset.available_balance + existing_asset.frozen_balance
                )
            else:
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
        # fee: TokenAmount,
        from_account: Optional[Account] = None,  # TODO
        update_balance: bool = True,
    ):
        chain = chains.get(amount.token.chain)
        if not chain:
            logger.warning(f"{self} | {amount.token.chain} not in {self.NAME}")
            raise ChainNotExistsInLocalChains(
                f"{self} | {amount.token.chain} not in {self.NAME}"
            )
        _, data = await self.post(
            "/v1/dw/withdraw/api/create",
            json=dict(
                address=to,
                currency=amount.token.symbol.lower(),
                amount=str(amount.converted),
                chain=chain,
                # fee=str(fee.converted)
            ),
        )
        return data.get("data"), data

    async def get_all_supported_coins_info(
        self, currency: Optional[str] = None, authorized_user: bool = True
    ):
        _, data = await self.get(
            "/v2/reference/currencies",
            params={"currency": currency, "authorizedUser": authorized_user},
            without_headers=not authorized_user,
        )
        if data.get("code") != 200:
            logger.warning(f"{self} | Couldn't get all coins info. {data}")
            return None
        return data
