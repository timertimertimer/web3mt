from decimal import Decimal, InvalidOperation

from web3mt.models import Coin
from web3mt.utils import format_number
from web3mt.utils.logger import logger

tron_default_decimals = 6
tron_symbol = 'TRX'


class Token(Coin):
    _instances = {}

    def __new__(cls, *, symbol = tron_symbol, decimals=tron_default_decimals, address=None, token_id=None, **kwargs):
        key = (symbol, decimals, address, token_id)
        if key not in cls._instances:
            cls._instances[key] = super().__new__(cls, symbol)
        return cls._instances[key]

    def __init__(
            self, *,
            symbol: str = tron_symbol,
            decimals: int = tron_default_decimals,
            address: str = None,
            token_id: int = None,
            price: Decimal | float = None,
            **kwargs
    ):
        self.symbol = symbol
        self.decimals = decimals
        self.address = address  # TRC20
        self.token_id = token_id  # TRC10
        super().__init__(symbol, price)

    def __repr__(self):
        if self.token_id is not None:
            return f"Token(symbol={self.symbol}, token_id={self.token_id}, decimals={self.decimals})"
        else:
            return f"Token(symbol={self.symbol}, address={self.address}, decimals={self.decimals})"

    def __eq__(self, other):
        if not isinstance(other, Token):
            return False
        return (
                self.symbol == other.symbol and
                self.decimals == other.decimals and
                self.address == other.address and
                self.token_id == other.token_id
        )

    def __str__(self):
        return self.symbol

    def __getitem__(self, token):
        return self._instances[(token.chain, token.symbol, token.address, token.decimals)]

    @property
    def price(self) -> Decimal | None:
        return self._prices.get(self.get_unwrapped_symbol())

    @price.setter
    def price(self, value: int | float | str | Decimal):
        self._prices[self.get_unwrapped_symbol()] = Decimal(str(value))

    def get_unwrapped_symbol(self) -> str:
        symbol = self.symbol
        if self.symbol == 'W' + tron_symbol:
            symbol = tron_symbol
        return symbol

    async def get_token_info(self) -> 'Token':
        from web3mt.onchain.tron.client import BaseClient
        return await BaseClient().get_onchain_token_info(token=self)


class TokenAmount:
    def __init__(
            self,
            amount: int | float | str | Decimal,
            is_sun: bool = False,
            token: Token = None,
            **kwargs
    ) -> None:
        self.token = token or Token()
        if is_sun:
            self._sun: int = int(amount)
            self._trx: Decimal = self._convert_sun_to_trx(amount)
        else:
            self._sun: int = self._convert_trx_to_sun(amount)
            self._trx: Decimal = Decimal(str(amount))

    def __str__(self) -> str:
        return (
                f'{self.format_trx()} {self.token.symbol}' +
                (f' ({self.amount_in_usd:.2f}$)' if self.amount_in_usd else '')
        )

    def __repr__(self):
        return (
                f'TokenAmount(sun={self.sun}, trx={self.format_trx()}, symbol={self.token.symbol}, '
                f'chain=Tron' + (f', amount_in_usd={self.amount_in_usd}' if self.amount_in_usd else '') +
                ')'
        )

    def __eq__(self, other):
        if other == 0:
            return self.sun == 0
        from web3mt.cex.models import Asset
        if isinstance(other, Asset):
            return self.token == other.coin
        return self.token == other.token and self.sun == other.sat

    def __gt__(self, other):
        if not isinstance(other, TokenAmount):
            raise TypeError(f'Cannot compare {other} with {repr(self)}')
        return self.sun > other.sun

    def __bool__(self):
        return bool(self.sun)

    def __add__(self, other):
        if other == 0:
            return self
        if isinstance(other, TokenAmount) and self.token == other.token:
            return TokenAmount(self.sun + other.sun, True, self.token)
        raise TypeError(f'Cannot add {other} to {repr(self)}')

    def __radd__(self, other):
        if other == 0:
            return self
        if not isinstance(other, (TokenAmount, int)):
            raise TypeError(f'Cannot add {other} to {repr(self)}')
        if other == 0:
            return self
        return self.__add__(other)

    def __sub__(self, other):
        if other == 0:
            return self
        if isinstance(other, TokenAmount) and self.token == other.token:
            return TokenAmount(self.sun - other.sun, True, self.token)
        raise TypeError(f'Cannot add {other} to {repr(self)}')

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return TokenAmount(int(self.sun * other), True, self.token)
        return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

    @property
    def sun(self):
        return self._sun

    @sun.setter
    def sun(self, value):
        self._sun = value
        self._trx = self._convert_sun_to_trx(value)

    @property
    def trx(self):
        return self._trx

    @trx.setter
    def trx(self, value):
        self._trx = value
        self._sun = self._convert_trx_to_sun(value)

    @property
    def amount_in_usd(self) -> Decimal | None:
        if self.token.price:
            return self.token.price * self.trx
        return None

    def format_trx(self) -> str:
        return format_number(self._trx)

    def _convert_sun_to_trx(self, amount: int | float | str | Decimal) -> Decimal:
        try:
            return Decimal(str(amount)) / 10 ** self.token.decimals
        except InvalidOperation as e:
            logger.error(f'Couldn\'t convert {amount} sun to trx: {e}')
            raise e

    def _convert_trx_to_sun(self, amount: int | float | str | Decimal) -> int:
        try:
            return int(Decimal(str(amount)) * 10 ** self.token.decimals)
        except InvalidOperation as e:
            logger.error(f'Couldn\'t convert {amount} trx to sun: {e}')
            raise e
