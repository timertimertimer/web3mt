from decimal import Decimal

from web3mt.onchain.evm.models import TokenAmount as TA
from web3mt.models import Coin


class Token(Coin):
    _instances = {}

    def __new__(
            cls,
            symbol: str = 'APT',
            asset_type: str = '0x1::aptos_coin::AptosCoin',
            name: str = 'Aptos Coin',
            decimals: int = 8,
            token_standard: int | str = 1,
            **kwargs
    ):
        key = (symbol, decimals)
        if key not in cls._instances:
            cls._instances[key] = object.__new__(cls)
        return cls._instances[key]

    def __init__(
            self,
            symbol: str = 'APT',
            asset_type: str = '0x1::aptos_coin::AptosCoin',  # ??? naming
            name: str = 'Aptos Coin',
            decimals: int = 8,
            token_standard: int | str = 1,
            price: Decimal = None,
            **kwargs
    ):
        self.asset_type = asset_type
        self.name = name
        self.decimals = decimals
        if isinstance(token_standard, int):
            self.token_standard = token_standard
        else:
            self.token_standard = 1 if token_standard == 'v1' else 2
        super().__init__(symbol, price)

    def __eq__(self, token):
        return (
                self.symbol == token.symbol and
                self.asset_type == token.asset_type and
                self.decimals == token.decimals and
                self.token_standard == token.token_standard
        )

    def __repr__(self):
        return (
            f"Token(symbol={self.symbol}, asset_type={self.asset_type}, name={self.name}, decimals={self.decimals}, "
            f"token_standard={self.token_standard}, price="
            f"{self.prices[self.symbol] if self.symbol in self.prices else None})"
        )

    def __str__(self):
        return self.__repr__()

    def __getitem__(self, token):
        return self._instances[(token.symbol, token.decimals)]


class TokenAmount(TA):
    def __init__(
            self,
            amount: int | float | str | Decimal = 0,
            is_wei: bool = False,
            token: Token = Token(),
            **kwargs
    ):
        super().__init__(amount, is_wei, token)

    def __repr__(self):
        return (
            f'TokenAmount(wei={self.wei}, ether={self.format_ether()}, symbol={self.token.symbol}' +
            (f', amount_in_usd={self.amount_in_usd}' if self.amount_in_usd else '') + ')'
        )


class NFT:
    def __init__(
            self,
            token_name: str,
            storage_id: str,
            token_data_id: str,
            collection_id: str,
            token_uri: str,
            amount: int = 1,
            description: str = None,
            token_standard: int | str = 1,
            **kwargs
    ):
        self.name = token_name
        self.description = description
        self.storage_id = storage_id
        self.token_data_id = token_data_id
        self.collection_id = collection_id
        self.uri = token_uri
        self.amount = amount
        if isinstance(token_standard, int):
            self.token_standard = token_standard
        else:
            self.token_standard = 1 if token_standard == 'v1' else 2

    def __repr__(self):
        return (
            f"NFT(name=\"{self.name}\", description=\"{self.description}\", storage_id={self.storage_id}, "
            f"token_data_id={self.token_data_id}, collection_id={self.collection_id}, uri=\"{self.uri}\", "
            f"amount={self.amount}, token_standart={self.token_standard})"
        )

    def __str__(self):
        return self.__repr__()
