from decimal import Decimal, InvalidOperation
from typing import Literal

from web3mt.models import Coin
from web3mt.utils import format_number
from web3mt.utils.logger import logger

btc_symbol = "BTC"
default_decimals = 8


class Token(Coin):
    _instances = {}

    def __new__(
        cls,
        *,
        symbol: str = btc_symbol,
        decimals: int = default_decimals,
        chain: Literal["bitcoin", "litecoin"] = "bitcoin",
        **kwargs,
    ):
        key = (symbol, decimals, chain)
        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls, symbol, decimals, chain)
        return cls._instances[key]

    def __init__(
        self,
        *,
        symbol: str = btc_symbol,
        decimals: int = default_decimals,
        chain: Literal["bitcoin", "litecoin"] = "bitcoin",
        price: Decimal | float = None,
        **kwargs,
    ):
        if chain == "litecoin":
            symbol = "LTC"
        self.symbol = symbol
        self.decimals = decimals
        self.chain = chain
        super().__init__(symbol, price)

    def __repr__(self):
        return f"Token(symbol={self.symbol}, decimals={self.decimals})"

    def __eq__(self, other):
        if not isinstance(other, Token):
            return False
        return self.symbol == other.symbol and self.decimals == other.decimals

    def __str__(self):
        return self.symbol

    def __getitem__(self, token):
        return self._instances[
            (token.chain, token.symbol, token.address, token.decimals)
        ]

    @property
    def price(self) -> Decimal | None:
        return self._prices.get(self.get_unwrapped_symbol())

    @price.setter
    def price(self, value: int | float | str | Decimal):
        self._prices[self.get_unwrapped_symbol()] = Decimal(str(value))

    def get_unwrapped_symbol(self) -> str:
        symbol = self.symbol
        if self.symbol == "W" + btc_symbol:
            symbol = btc_symbol
        return symbol

    async def get_token_info(self) -> "Token":
        from web3mt.onchain.tron.client import BaseClient

        return await BaseClient().get_onchain_token_info(token=self)


class BTCLikeAmount:
    def __init__(
        self,
        amount: int | float | str | Decimal,
        is_sat: bool = False,
        token: Token = Token(),
        **kwargs,
    ) -> None:
        self.token = token
        if is_sat:
            self._sat: int = int(amount)
            self._btc: Decimal = self._convert_sat_to_btc(amount)
        else:
            self._sat: int = self._convert_btc_to_sat(amount)
            self._btc: Decimal = Decimal(str(amount))

    def __str__(self) -> str:
        return f"{self.format_btc()} {self.token.symbol}" + (
            f" ({self.amount_in_usd:.2f}$)" if self.amount_in_usd else ""
        )

    def __repr__(self):
        return (
            f"BTCLikeAmount(sat={self.sat}, btc={self.format_btc()}, symbol={self.token.symbol}, "
            f"chain={self.token.chain}"
            + (f", amount_in_usd={self.amount_in_usd}" if self.amount_in_usd else "")
            + ")"
        )

    def __eq__(self, other):
        if other == 0:
            return self.sat == 0
        return self.token == other.token and self.sat == other.sat

    def __gt__(self, other):
        if other == 0:
            return self.sat > 0
        if not isinstance(other, BTCLikeAmount):
            raise TypeError(f"Cannot compare {other} with {repr(self)}")
        return self.sat > other.sat

    def __ge__(self, other):
        if other == 0:
            return self.sat >= 0
        if not isinstance(other, BTCLikeAmount):
            raise TypeError(f"Cannot compare {other} with {repr(self)}")
        return self.sat >= other.sat

    def __lt__(self, other):
        if other == 0:
            return self.sat < 0
        if not isinstance(other, BTCLikeAmount):
            raise TypeError(f"Cannot compare {other} with {repr(self)}")
        return self.sat < other.sat

    def __le__(self, other):
        if other == 0:
            return self.sat <= 0
        if not isinstance(other, BTCLikeAmount):
            raise TypeError(f"Cannot compare {other} with {repr(self)}")
        return self.sat <= other.sat

    def __bool__(self):
        return bool(self.sat)

    def __add__(self, other):
        if other == 0:
            return self
        if isinstance(other, BTCLikeAmount) and self.token == other.token:
            return BTCLikeAmount(self.sat + other.sat, True, self.token)
        raise TypeError(f"Cannot add {other} to {repr(self)}")

    def __radd__(self, other):
        if other == 0:
            return self
        if not isinstance(other, (BTCLikeAmount, int)):
            raise TypeError(f"Cannot add {other} to {repr(self)}")
        if other == 0:
            return self
        return self.__add__(other)

    def __sub__(self, other):
        if other == 0:
            return self
        if isinstance(other, BTCLikeAmount) and self.token == other.token:
            return BTCLikeAmount(self.sat - other.sat, True, self.token)
        raise TypeError(f"Cannot add {other} to {repr(self)}")

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return BTCLikeAmount(int(self.sat * other), True, self.token)
        return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

    @property
    def sat(self):
        return self._sat

    @sat.setter
    def sat(self, value):
        self._sat = value
        self._btc = self._convert_sat_to_btc(value)

    @property
    def btc(self):
        return self._btc

    @btc.setter
    def btc(self, value):
        self._btc = value
        self._sat = self._convert_btc_to_sat(value)

    @property
    def amount_in_usd(self) -> Decimal | None:
        if self.token.price:
            return self.token.price * self.btc
        return None

    def format_btc(self) -> str:
        return format_number(self._btc)

    def _convert_sat_to_btc(self, amount: int | float | str | Decimal) -> Decimal:
        try:
            return Decimal(str(amount)) / 10**self.token.decimals
        except InvalidOperation as e:
            logger.error(f"Couldn't convert {amount} sat to btc: {e}")
            raise e

    def _convert_btc_to_sat(self, amount: int | float | str | Decimal) -> int:
        try:
            return int(Decimal(str(amount)) * 10**self.token.decimals)
        except InvalidOperation as e:
            logger.error(f'Couldn\'t convert {amount} sat to btc: {e}')
            raise e