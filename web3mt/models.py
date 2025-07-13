from decimal import Decimal, InvalidOperation

from web3mt.utils import format_number, logger


class Coin:
    _instances = {}
    _prices = {}

    def __new__(cls, symbol: str, *args, **kwargs):
        symbol = symbol.upper()
        if symbol not in cls._instances:
            cls._instances[symbol] = super().__new__(cls)
        return cls._instances[symbol]

    def __init__(
        self, symbol: str, name: str = None, price: int | float | str | Decimal = None
    ):
        self.symbol = symbol.upper()
        self.name = name
        if price:
            self.price = price
        elif self.symbol in ["USDT", "USDC", "USD1"]:
            self.price = Decimal("1")

    def __eq__(self, other):
        return self.symbol == other.symbol

    def __repr__(self):
        return self.symbol

    @property
    def price(self) -> Decimal | None:
        return self._prices.get(self.symbol) or self._prices.get(
            self.symbol.removeprefix("W")
        )

    @price.setter
    def price(self, value: int | float | str | Decimal):
        self._prices[self.symbol] = Decimal(str(value))

    @classmethod
    def from_instance(cls, instance):
        return cls(**instance.__dict__)

    @classmethod
    def instances(cls):
        return cls._instances

    async def update_price(self) -> Decimal:
        from web3mt.cex import OKX

        self.price = await OKX().get_coin_price(self)
        return self.price


class Chain:
    _instances = {}

    def __new__(
        cls,
        name: str,
        rpc: str,
        explorer: str,
        native_token: "Token" = None,
    ):
        if name in cls._instances:
            raise ValueError(f'Instance "{name}" of Chain already exists.')
        instance = super().__new__(cls)
        cls._instances[name] = instance
        return instance

    def __init__(
        self,
        name: str,
        rpc: str,
        explorer: str,
        native_token: "Token" = None,
    ):
        self.name = name
        self.rpc = rpc
        self.explorer = explorer.rstrip("/")
        self.native_token = native_token

    def __str__(self):
        return self.name

    def __repr__(self):
        return (
            f"Chain(name={self.name}, rpc={self.rpc}, explorer={self.explorer}, "
            f"native_token={self.native_token.symbol if self.native_token else None})"
        )

    @classmethod
    def get_by_name(cls, name: str) -> "Chain":
        for instance in cls._instances.values():
            if instance.name == name:
                return instance
        raise ValueError(f"No instance found with name {name}")


class Token(Coin):
    _instances = {}

    def __new__(
        cls,
        *,
        symbol: str,
        decimals: int,
        chain: Chain,
        **kwargs,
    ):
        key = (symbol, decimals, chain)
        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls, symbol, decimals, chain)
        return cls._instances[key]

    def __init__(
        self,
        symbol: str,
        decimals: int,
        chain: Chain,
        price: Decimal | float = None,
    ):
        self.symbol = symbol
        self.decimals = decimals
        self.chain = chain
        super().__init__(symbol, price)

    def __repr__(self):
        return f"Token(symbol={self.symbol}, decimals={self.decimals})"

    def __eq__(self, other):
        if not isinstance(other, Coin):
            return False
        return self.symbol == other.symbol and self.decimals == other.decimals

    def __str__(self):
        return self.symbol

    def __getitem__(self, token):
        return self._instances[(token.chain, token.symbol, token.decimals)]


class TokenAmount:
    def __init__(
        self,
        token: Token,
        amount: int | float | str | Decimal,
        is_sats: bool = False,
    ) -> None:
        self.token = token
        if is_sats:
            self._sats: int = int(amount)
            self._converted: Decimal = self._convert_sat_to_converted(amount)
        else:
            self._sats: int = self._convert_converted_to_sat(amount)
            self._converted: Decimal = Decimal(str(amount))

    def __str__(self) -> str:
        return f"{self.format_converted()} {self.token.symbol}" + (
            f" ({self.amount_in_usd:.2f}$)" if self.amount_in_usd else ""
        )

    def __repr__(self):
        return (
            f"TokenAmount(sats={self.sats}, converted={self.format_converted()}, symbol={self.token.symbol}, "
            f"chain={self.token.chain}"
            + (f", amount_in_usd={self.amount_in_usd}" if self.amount_in_usd else "")
            + ")"
        )

    def __eq__(self, other):
        if other == 0:
            return self.sats == 0
        return self.token == other.token and self.sats == other.sats

    def __gt__(self, other):
        if other == 0:
            return self.sats > 0
        if not isinstance(other, TokenAmount):
            raise TypeError(f"Cannot compare {other} with {repr(self)}")
        return self.sats > other.sats

    def __ge__(self, other):
        if other == 0:
            return self.sats >= 0
        if not isinstance(other, TokenAmount):
            raise TypeError(f"Cannot compare {other} with {repr(self)}")
        return self.sats >= other.sats

    def __lt__(self, other):
        if other == 0:
            return self.sats < 0
        if not isinstance(other, TokenAmount):
            raise TypeError(f"Cannot compare {other} with {repr(self)}")
        return self.sats < other.sats

    def __le__(self, other):
        if other == 0:
            return self.sats <= 0
        if not isinstance(other, TokenAmount):
            raise TypeError(f"Cannot compare {other} with {repr(self)}")
        return self.sats <= other.sats

    def __bool__(self):
        return bool(self.sats)

    def __add__(self, other):
        if other == 0:
            return self
        if isinstance(other, TokenAmount) and self.token == other.token:
            return TokenAmount(self.token, self.sats + other.sats, True)
        raise TypeError(f"Cannot add {other} to {repr(self)}")

    def __radd__(self, other):
        if other == 0:
            return self
        if not isinstance(other, (TokenAmount, int)):
            raise TypeError(f"Cannot add {other} to {repr(self)}")
        if other == 0:
            return self
        return self.__add__(other)

    def __sub__(self, other):
        if other == 0:
            return self
        if isinstance(other, TokenAmount) and self.token == other.token:
            return TokenAmount(self.token, self.sats - other.sats, True)
        raise TypeError(f"Cannot add {other} to {repr(self)}")

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return TokenAmount(self.token, int(self.sats * other), True)
        return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

    @property
    def sats(self):
        return self._sats

    @sats.setter
    def sats(self, value):
        self._sats = value
        self._converted = self._convert_sat_to_converted(value)

    @property
    def converted(self):
        return self._converted

    @converted.setter
    def converted(self, value):
        self._converted = value
        self._sats = self._convert_converted_to_sat(value)

    @property
    def amount_in_usd(self) -> Decimal | None:
        if self.token.price:
            return self.token.price * self.converted
        return None

    def format_converted(self) -> str:
        return format_number(self._converted)

    def _convert_sat_to_converted(self, amount: int | float | str | Decimal) -> Decimal:
        try:
            return Decimal(str(amount)) / 10**self.token.decimals
        except InvalidOperation as e:
            logger.error(f"Couldn't convert {amount} sat to converted: {e}")
            raise e

    def _convert_converted_to_sat(self, amount: int | float | str | Decimal) -> int:
        try:
            return int(Decimal(str(amount)) * 10**self.token.decimals)
        except InvalidOperation as e:
            logger.error(f"Couldn't convert {amount} sat to converted: {e}")
            raise e
