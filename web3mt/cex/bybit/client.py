# FIXME
# FIXME
# FIXME
import asyncio
import hmac
import json
import time
import uuid
from decimal import Decimal
from functools import partialmethod
from hashlib import sha256
from urllib.parse import urlencode

from web3db import Profile, DBHelper

from web3mt.cex.base import CEX
from web3mt.cex.models import Asset, Account, User
from web3mt.config import DEV, env
from web3mt.models import Coin
from web3mt.utils import logger

__all__ = ["Bybit"]


def create_currencies_with_comma_string(coins: list[Asset | Coin | str]) -> str:
    coins_string = ""
    for coin in coins:
        match coin:
            case Asset():
                coin = coin.coin.symbol
            case Coin():
                coin = coin.symbol
            case str():
                coin = coin.upper()
            case _:
                ...
        coins_string += coin + ","
    return coins_string[:-1]


class Bybit(CEX):
    API_VERSION = 5
    MAIN_ENDPOINT = "https://api.bybit.com"
    URL = f"{MAIN_ENDPOINT}/v{API_VERSION}"
    NAME = "Bybit"

    async def get_server_timestamp(self) -> str:
        _, data = await self.session.get(f"{self.URL}/market/time")
        return str(data["time"])

    async def get_headers(
        self, path: str, method: str = "GET", recv_window: int = 10000, **kwargs
    ):
        timestamp = await self.get_server_timestamp() or str(int(time.time() * 10**3))
        params = urlencode(kwargs.get("params", {}))
        params = urlencode(params)
        prehash_string = (
            timestamp
            + self.profile.bybit.api_key
            + str(recv_window)
            + str(params)
            + kwargs.get("data", "")
        )
        signature = hmac.new(
            self.profile.bybit.api_secret.encode("utf-8"),
            prehash_string.encode("utf-8"),
            sha256,
        ).hexdigest()
        return {
            "Content-Type": "application/json",
            "X-BAPI-API-KEY": self.profile.bybit.api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": str(recv_window),
        }

    async def make_request(self, method: str, path: str, **kwargs):
        without_headers = kwargs.pop("without_headers", False)
        response, data = await self.session.make_request(
            method,
            f"{self.URL}/{path}",
            headers={}
            if without_headers
            else await self.get_headers(path, method, **kwargs),
            **kwargs,
        )
        if not data["result"]:
            logger.error(f"{self.log_info} | {data['retMsg']}")
            raise KeyError
        return response, data["result"]

    head = partialmethod(make_request, "HEAD")
    get = partialmethod(make_request, "GET")
    post = partialmethod(make_request, "POST")
    put = partialmethod(make_request, "PUT")
    patch = partialmethod(make_request, "PATCH")
    delete = partialmethod(make_request, "DELETE")
    options = partialmethod(make_request, "OPTIONS")

    async def get_coin_price(self, coin: str | Coin = "ETH") -> Decimal:
        if coin.price:
            return coin.price
        coin = Coin(coin) if isinstance(coin, str) else coin
        _, data = await self.get(
            "market/tickers",
            params={"category": "spot", "symbol": f"{coin.symbol}USDT"},
        )
        coin.price = data["list"][0]["ask1Price"]
        return coin.price

    async def get_funding_balance(
        self, user: User = None, coins: list[Asset | Coin | str] = None
    ) -> list[Asset]:
        funding_account = user.funding_account or self.main_user.funding_account
        return await self._get_balance(funding_account, coins)

    async def get_trading_balance(
        self, user: User = None, coins: list[Asset | Coin | str] = None
    ) -> list[Asset] | None:
        trading_account = user.trading_account or self.main_user.trading_account
        account_type = await self.get_uid_wallet_type(user)
        if "SPOT" in account_type or "UNIFIED" in account_type:
            return await self._get_balance(trading_account, coins)
        return None

    async def _get_balance(
        self, account: Account, coins: list[Asset | Coin | str] = None
    ) -> list[Asset]:
        _, data = await self.get(
            "account/wallet-balance"
            if account.ACCOUNT_ID == "UNIFIED"
            else "asset/transfer/query-account-coins-balance",
            params=(
                {"accountType": account.ACCOUNT_ID}
                | (
                    {"coin": create_currencies_with_comma_string(coins)}
                    if coins
                    else {}
                )
                | ({"memberId": account.user.user_id} if account.user.user_id else {})
            ),
        )
        assets = data["balance"]
        account.assets = [
            Asset(
                Coin(asset["coin"]),
                available_balance=asset["transferBalance"],
                total=asset["walletBalance"],
                frozen_balance=Decimal(asset["walletBalance"])
                - Decimal(asset["transferBalance"]),
            )
            for asset in assets
            if Decimal(asset["walletBalance"])
        ]
        if DEV:
            logger.info(account)
        return account.assets

    async def get_main_uid(self) -> int:
        if not self.main_user.user_id:
            _, data = await self.get("user/query-api")
            self.main_user.user_id = data["userID"]
        return self.main_user.user_id

    async def get_account_info(self):
        _, data = await self.get("account/info")
        return data

    async def get_uid_wallet_type(self, user: User) -> list[str]:
        _, data = await self.get(
            "user/get-member-type",
            params={"memberIds": user.user_id} if user.user_id else {},
        )
        for account in data["accounts"]:
            if account["uid"] == user.user_id:
                return account["accountType"]
        return data["accounts"][0]["accountType"]

    async def get_sub_account_list(self) -> list[User]:
        _, data = await self.get("user/query-sub-members")
        return [User(self, sub_account["uid"]) for sub_account in data["subMembers"]]

    async def transfer(
        self,
        from_account: Account,
        to_account: Account,
        asset: Asset | Coin | str = "ETH",
    ):
        if isinstance(asset, (Coin, str)):
            from web3mt.cex.bybit.models import Spot

            balance_func = (
                self.get_trading_balance
                if isinstance(from_account, Spot)
                else self.get_funding_balance
            )
            assets = await balance_func(from_account, [asset])
            if not assets:
                logger.info(f"No balance of {asset}")
                return
            asset: Asset = assets[0]
        amount = asset.format_available_balance(
            int((await self.get_coin_info(asset))[0]["minAccuracy"])
        )
        data = dict(
            transferId=str(uuid.uuid4()),
            coin=asset.coin.symbol,
            amount=amount,
            fromAccountType=from_account.ACCOUNT_ID,
            toAccountType=to_account.ACCOUNT_ID,
        )
        from_account.user.user_id = (
            from_account.user.user_id or await self.get_main_uid()
        )
        to_account.user.user_id = to_account.user.user_id or await self.get_main_uid()
        if from_account.user.user_id == to_account.user.user_id:
            url = "asset/transfer/inter-transfer"
        else:
            url = "asset/transfer/universal-transfer"
            data = data | dict(
                fromMemberId=from_account.user.user_id,
                toMemberId=to_account.user.user_id,
            )
        _, data = await self.post(url, data=json.dumps(data))
        if data and data["status"] == "SUCCESS":
            logger.success(
                f"Transferred {asset} from {from_account.user.user_id} {from_account.NAME} to "
                f"{to_account.user.user_id} {to_account.NAME}. ID - {data['result']['transferId']}"
            )
        else:
            logger.warning(f"Couldn't transfer {asset}. {data['retMsg']}")

    async def get_coin_info(self, asset: Asset | Coin | str = None):
        match asset:
            case Asset():
                coin = asset.coin.symbol
            case Coin():
                coin = asset.symbol
            case _:
                coin = asset
        _, data = await self.get(
            "asset/coin/query-info", params={"coin": coin} if coin else {}
        )
        info_by_chains = data["rows"][0]["chains"]
        return info_by_chains


async def main():
    db = DBHelper(env.LOCAL_CONNECTION_STRING)
    profile = await db.get_row_by_id(1, Profile)
    bybit = Bybit(profile)
    # await bybit.get_funding_balance(coins=['SOL'])
    print(await bybit.get_sub_account_list())


if __name__ == "__main__":
    asyncio.run(main())
