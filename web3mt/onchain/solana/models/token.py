from solders.pubkey import Pubkey


class Token:
    _instances = {}

    def __new__(
            cls,
            symbol: str,
            address: str,
            decimals: int = 9,
            **kwargs
    ):
        key = (symbol, address, decimals,)
        if key not in cls._instances:
            cls._instances[key] = object.__new__(cls)
        return cls._instances[key]

    def __init__(self, address: Pubkey, decimals: int):
        self.address = address
        self.decimals = decimals
