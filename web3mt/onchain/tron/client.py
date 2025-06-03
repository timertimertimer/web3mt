import asyncio
from typing import Optional

from tronpy import AsyncTron, AsyncContract
from tronpy.providers import AsyncHTTPProvider
from tronpy.exceptions import AddressNotFound

from web3mt.consts import Web3mtENV, DEV
from web3mt.onchain.evm.models import DefaultABIs
from web3mt.onchain.tron.models import Token, tron_symbol, TokenAmount
from web3mt.utils.logger import my_logger as logger

from web3mt.onchain.tron.account import TronAccount

default_rpc = 'https://api.trongrid.io'
private_rpc = 'http://92.53.84.170:8090'
USDT = Token(address='TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', symbol='USDT')


class BaseClient:
    native_tron = Token()

    def __init__(self, account: TronAccount = None, http_rpc: str = default_rpc):
        self.account = account or TronAccount.create()
        self.w3 = AsyncTron(AsyncHTTPProvider(http_rpc, api_key=Web3mtENV.TRONGRID_API_KEY))

    @property
    def account(self) -> TronAccount:
        return self._account

    @account.setter
    def account(self, account: TronAccount):
        self._account: TronAccount = account
        self._update_log_info()

    def _update_log_info(self):
        self.log_info = f'{self._account.address} (Tron)'

    async def send_trx(
            self, amount: TokenAmount, to: str | TronAccount, from_: str | TronAccount = None
    ) -> AsyncContract:
        txn = (
            (await self.w3.trx.transfer(from_ or self.account.address, to, amount.sun).build())
            .sign(self.account.private_key)
        )
        return txn

    async def get_account(self) -> Optional[dict]:
        try:
            return await self.w3.get_account(self.account.address)
        except AddressNotFound as e:
            logger.warning(f'Account {self.account.address} not found on-chain')
        return None

    async def get_onchain_token_info(self, contract=None, token: Token = None) -> Token | None:
        if token.symbol == tron_symbol:
            logger.warning(f'{self.log_info} | Can\'t get native token info')
            return None
        contract = contract or AsyncContract(token.address, abi=DefaultABIs.token, client=self.w3)
        token = token or Token(address=contract.address)
        token.decimals, token.name, token.symbol = (await asyncio.gather(*[
            contract.functions.decimals(),
            contract.functions.name(),
            contract.functions.symbol()
        ]))
        # FIXME: use multicall
        return token

    async def balance_of(
            self, contract: AsyncContract = None, token: Token = native_tron, owner_address: str = None, echo: bool = DEV,
            remove_zero_from_echo: bool = DEV
    ) -> TokenAmount:
        owner_address = owner_address or self.account.address
        if token.symbol != tron_symbol:
            token = await self.get_onchain_token_info(contract=contract, token=token)
            contract = contract or AsyncContract(token.address, abi=DefaultABIs.token, client=self.w3)
            amount = await contract.functions.balanceOf(owner_address).call()
            balance = TokenAmount(amount, True, token)
        else:
            balance = await self.w3.get_account_balance(owner_address)
        if echo:
            if not remove_zero_from_echo:
                logger.debug(f'{self.log_info} | Balance - {balance}')
            elif balance:
                logger.debug(f'{self.log_info} | Balance - {balance}')
        return balance


class PrivateBaseClient(BaseClient):

    def __init__(self, account: TronAccount = None, http_rpc: str = private_rpc):
        super().__init__(account, http_rpc)
        self._ledger_account = TronAccount('0000000000000000000000000000000000000000000000000000000000000002')

    async def activate_account(self):
        await self.send_trx(to=self.account.address, from_=self._ledger_account, amount=TokenAmount(100))


async def main():
    my_account = TronAccount.from_key('851ba5ebaf3daad7168ca75e6fbe7a939cd1ef5a8e2fa8f6a45ed2fc0514d82b')

    client = BaseClient(my_account)

    # data = await client.get_account()
    # data = await client.get_onchain_token_info(token=USDT)
    data = await client.balance_of()
    return data


async def main_private():
    my_account = TronAccount.from_key('851ba5ebaf3daad7168ca75e6fbe7a939cd1ef5a8e2fa8f6a45ed2fc0514d82b')
    client = PrivateBaseClient(my_account)
    # data = await client.w3.get_account_balance()
    return data


# my_key = PrivateKey.fromhex("eed6e4548e8ecf0fac1dc8aabef2c390590983e05566d5e161869f8e78b1ad5e")
#
# witness_priv_key = PrivateKey.fromhex("00000000000000000
# 00000000000000000000000000000000000000000000001")
# ledger_priv_key = PrivateKey.fromhex("0000000000000000000000000000000000000000000000000000000000000002")

if __name__ == '__main__':
    asyncio.run(main())
