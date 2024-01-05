from eth_account import Account
from utils import read_txt

Account.enable_unaudited_hdwallet_features()


def generate(n: int) -> None:
    s = ''
    for _ in range(n):
        account = Account.create()
        s += f'{account.key.hex()}\n'
    with open('new_wallets.txt', mode='w', encoding='utf-8') as file:
        file.write(s)


def get_private_from_mnemonic():
    mnemonics = read_txt('mnemonics.txt', 'utf-8')
    for mnemonic in mnemonics:
        account = Account.from_mnemonic(mnemonic, account_path=f"m/44'/60'/0'/0/0")
        print(account.key.hex())


if __name__ == '__main__':
    get_private_from_mnemonic()
