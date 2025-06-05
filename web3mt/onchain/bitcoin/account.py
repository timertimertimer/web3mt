from bitcoinlib.keys import HDKey


class Account:
    def __init__(self, seed: str):
        self._hd_key = HDKey.from_seed(seed)

    def __str__(self):
        return self._hd_key.address()

    def __repr__(self):
        return self.__str__()

    @classmethod
    def create(cls):
        return HDKey()

    @classmethod
    def from_wif(cls, key: str):
        return HDKey.from_wif(key)

    @property
    def key(self):
        return self._hd_key.wif_key()
