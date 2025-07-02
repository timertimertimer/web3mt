from tronpy.keys import PrivateKey, Signature
from bip_utils import (
    Bip44Coins,
    Bip44,
)

from web3mt.utils.seeds import get_private_key_from_mnemonic


class TronAccount:
    def __init__(self, private_key: PrivateKey | str):
        if isinstance(private_key, str):
            self._private_key = PrivateKey.fromhex(private_key)
        else:
            self._private_key = private_key
        self.address = self._private_key.public_key.to_base58check_address()

    def __str__(self):
        return self.address

    def __repr__(self):
        return

    @classmethod
    def create(cls):
        return cls(PrivateKey.random())

    @classmethod
    def from_key(cls, key: str):
        if isinstance(key, str):
            key = bytes.fromhex(key)
        return cls(PrivateKey(key))

    @classmethod
    def from_mnemonic(cls, mnemonic: str):
        key = get_private_key_from_mnemonic(Bip44, Bip44Coins.TRON, mnemonic)
        return cls.from_key(key)

    @property
    def key(self):
        return self._private_key

    def sign_message(self, message: bytes) -> Signature:
        return self._private_key.sign_msg(message)

    def sign_transaction(self, txn):
        return txn.sign(self._private_key)
