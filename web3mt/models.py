from decimal import Decimal


class Coin:
    _instances = {}
    _prices = {}

    def __new__(cls, symbol: str, *args, **kwargs):
        symbol = symbol.upper()
        if symbol not in cls._instances:
            cls._instances[symbol] = super().__new__(cls)
        return cls._instances[symbol]

    def __init__(self, symbol: str, name: str = None, price: int | float | str | Decimal = None):
        self.symbol = symbol.upper()
        self.name = name
        if price:
            self.price = price
        elif self.symbol in ['USDT', 'USDC']:
            self.price = Decimal("1")

    def __eq__(self, other):
        return self.symbol == other.symbol

    def __repr__(self):
        return self.symbol

    @property
    def price(self) -> Decimal | None:
        return self._prices.get(self.symbol) or self._prices.get(self.symbol.removeprefix('W'))

    @price.setter
    def price(self, value: int | float | str | Decimal):
        self._prices[self.symbol] = Decimal(str(value))

    @classmethod
    def from_instance(cls, instance):
        return cls(**instance.__dict__)

    async def update_price(self) -> Decimal:
        from web3mt.cex import OKX
        self.price = await OKX().get_coin_price(self)
        return self.price
