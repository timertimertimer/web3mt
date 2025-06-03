from tronpy.keys import PrivateKey, Signature


class TronAccount:
    def __init__(self, private_key: PrivateKey | str):
        if isinstance(private_key, str):
            self.private_key = PrivateKey.fromhex(private_key)
        else:
            self.private_key = private_key
        self.address = self.private_key.public_key.to_base58check_address()

    @classmethod
    def create(cls):
        return cls(PrivateKey.random())

    @classmethod
    def from_key(cls, key: str):
        if isinstance(key, str):
            key = bytes.fromhex(key)
        return cls(PrivateKey(key))

    def sign_message(self, message: bytes) -> Signature:
        return self.private_key.sign_msg(message)

    def sign_transaction(self, txn):
        return txn.sign(self.private_key)


if __name__ == '__main__':
    new_account = TronAccount.create()
    print(f'{new_account.address=}')
    print(f'{new_account.private_key=}')
    my_account = TronAccount.from_key('851ba5ebaf3daad7168ca75e6fbe7a939cd1ef5a8e2fa8f6a45ed2fc0514d82b')
    print(f'{my_account.address=}')
    print(f'{my_account.private_key=}')
