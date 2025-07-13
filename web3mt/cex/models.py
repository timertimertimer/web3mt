from decimal import Decimal
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from web3mt.cex import CEX
from web3mt.models import Coin, Token
from web3mt.onchain.evm.models import TokenAmount
from web3mt.utils import format_number

__all__ = ["Asset", "User", "Account", "WithdrawInfo", "ChainNotExistsInLocalChains"]


class Asset:
    def __init__(
        self,
        coin: Coin,
        available_balance: int | float | str | Decimal,
        frozen_balance: int | float | str | Decimal,
        total: int | float | str | Decimal,
    ) -> None:
        self.coin = coin
        self.available_balance = Decimal(available_balance)
        self.frozen_balance = Decimal(frozen_balance)
        self.total = Decimal(total)

    def __str__(self) -> str:
        return (
            f"{self.format_total()} {self.coin.symbol} = "
            f"{self.coin.price * self.total if self.coin.price else 0:.2f}$"
        )

    def __repr__(self):
        return self.__str__()

    def __eq__(self, asset):
        return self.coin == asset.coin and self.total == asset.total

    def __gt__(self, other):
        if isinstance(other, TokenAmount) and self.coin == other.token:
            return self.total > other.ether
        if (
            not isinstance(other, (Asset, TokenAmount))
            or self.coin.symbol != other.token.symbol
        ):
            raise TypeError(f"Cannot compare {other} with {repr(self)}")
        return self.total > other.total

    def __lt__(self, other):
        return not self.__gt__(other)

    def __bool__(self):
        return bool(self.total)

    def __add__(self, other):
        if other == 0:
            return self
        if isinstance(other, Asset) and self.coin == other.coin:
            return Asset(
                coin=other.coin,
                available_balance=self.available_balance + other.available_balance,
                frozen_balance=self.frozen_balance + other.frozen_balance,
                total=self.total + other.total,
            )
        raise TypeError(f"Cannot add {other} to {repr(self)}")

    def __radd__(self, other):
        if other == 0:
            return self
        if not isinstance(other, (Asset, Decimal)):
            raise TypeError(f"Cannot add {other} to {repr(self)}")
        if other == 0:
            return self
        return self.__add__(other)

    def __sub__(self, other):
        if other == 0:
            return self
        if isinstance(other, Asset) and self.coin == other.coin:
            return Asset(
                coin=other.coin,
                available_balance=self.available_balance - other.available_balance,
                frozen_balance=self.frozen_balance - other.frozen_balance,
                total=self.total - other.total,
            )
        raise TypeError(f"Cannot add {other} to {repr(self)}")

    def format_total(self) -> str:
        return format_number(self.total)

    def format_available_balance(self, accuracy: int = None) -> str:
        return format_number(self.available_balance, accuracy)


class Account:
    NAME = None
    ACCOUNT_ID = None

    def __init__(self, user: "User", assets: list[Asset] = None) -> None:
        self.user = user
        self.assets = assets or []  # FIXME: list -> dict

    def __getitem__(self, coin: Coin | str) -> Asset | None:
        for asset in self.assets:
            if isinstance(coin, Token) and coin.symbol == asset.coin.symbol:
                return asset
            if isinstance(coin, Coin) and coin == asset.coin:
                return asset
            elif isinstance(coin, str) and coin == asset.coin.symbol:
                return asset
        raise KeyError(f"No asset with coin {coin} in {self!r}")

    def __iter__(self):
        return iter(self.assets)

    def __str__(self):
        return f"{self.user} {self.NAME} balance: {self.balance:.2f}$" + (
            "\n" + "\n".join(map(str, self.assets)) if self.assets else ""
        )

    def __repr__(self):
        return self.__str__()

    def __contains__(self, item):
        if not isinstance(item, Coin):
            raise TypeError(
                f"'in' expects a Coin instance, got {type(item).__name__!r}"
            )
        return any(asset.coin == item for asset in self.assets)

    def get(self, coin: Coin, default: Asset | None = None) -> Asset | None:
        try:
            return self[coin]
        except KeyError:
            return default

    @property
    def balance(self) -> int | float | str | Decimal:
        return sum(
            asset.total * asset.coin.price if asset.coin.price else Decimal(0)
            for asset in self.assets
        )


class User:
    def __init__(self, cex: "CEX", user_id: str = None):
        self.cex = cex
        trading_account_class = account_factory(cex, "Trading")
        funding_account_class = account_factory(cex, "Funding")
        self.trading_account = (
            trading_account_class(self) if trading_account_class else None
        )
        self.funding_account = (
            funding_account_class(self) if funding_account_class else None
        )
        self.user_id = user_id

    def __repr__(self):
        return f"{self.cex} User {self.user_id or 'Main'}"


def account_factory(cex: "CEX", account_type: str) -> type(Account):
    from web3mt.cex.bybit.models import Funding as BybitFunding, Spot as BybitTrading
    from web3mt.cex.okx.models import Funding as OKXFunding, Trading as OKXTrading
    from web3mt.cex.binance.models import (
        Funding as BinanceFunding,
        Spot as BinanceTrading,
    )
    from web3mt.cex.htx.models import Spot as HTXSpot
    from web3mt.cex.kucoin.models import (
        Funding as KucoinFunding,
        Trading as KucoinTrading,
    )
    from web3mt.cex.mexc.models import Trading as MexcTrading

    cex_accounts_mapping = {
        "OKX": {
            "trading": OKXTrading,
            "funding": OKXFunding,
        },
        "Bybit": {
            "trading": BybitTrading,
            "funding": BybitFunding,
        },
        "Binance": {
            "trading": BinanceTrading,
            "funding": BinanceFunding,
        },
        "HTX": {
            "trading": HTXSpot,
            "funding": None,
        },
        "Kucoin": {
            "trading": KucoinTrading,
            "funding": KucoinFunding,
        },
        "MEXC": {"trading": MexcTrading, "funding": None},
    }
    return cex_accounts_mapping.get(cex.NAME, {}).get(account_type.lower())


class WithdrawInfo:
    def __init__(
        self,
        coin: Coin,
        chain: str,
        fee: int | float | str | Decimal,
        minimum_withdrawal: int | float | str | Decimal,
        maximum_withdrawal: int | float | str | Decimal,
        need_tag: bool = False,
        internal: bool = False,
    ):
        self.coin = coin
        self.chain = chain
        self.fee = Decimal(fee)
        self.minimum_withdrawal = Decimal(minimum_withdrawal)
        self.maximum_withdrawal = Decimal(maximum_withdrawal)
        self.need_tag = need_tag
        self.internal = internal

    def __repr__(self):
        return (
            f"WithdrawInfo(chain={self.coin.symbol}-{self.chain}, fee={self.fee} {self.coin.symbol} "
            f"({(self.fee * self.coin.price):.2f}$), minimum={self.minimum_withdrawal} {self.coin.symbol} "
            f"({(self.minimum_withdrawal * self.coin.price):.2f}$), maximum={self.maximum_withdrawal} "
            f"{self.coin.symbol} ({(self.maximum_withdrawal * self.coin.price):.2f}$), need tag={self.need_tag}, "
            f"internal={self.internal})"
        )

    def __str__(self):
        return self.__repr__()


class ChainNotExistsInLocalChains(Exception):
    pass
