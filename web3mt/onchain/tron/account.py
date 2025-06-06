from tronpy.keys import PrivateKey, Signature

from web3mt.consts import settings


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

    @property
    def key(self):
        return self._private_key

    def sign_message(self, message: bytes) -> Signature:
        return self._private_key.sign_msg(message)

    def sign_transaction(self, txn):
        return txn.sign(self._private_key)


if __name__ == '__main__':
    new_account = TronAccount.create()
    print(f'{new_account.address=}')
    print(f'{new_account._private_key=}')
    my_account = TronAccount.from_key(settings.TRON_PRIVATE_KEY)
    print(f'{my_account.address=}')
    print(f'{my_account._private_key=}')
