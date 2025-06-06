import asyncio
import enum
from typing import Optional
from datetime import datetime

from tronpy import AsyncTron, AsyncContract
from tronpy.providers import AsyncHTTPProvider
from tronpy.providers.async_http import DEFAULT_API_KEY
from tronpy.async_tron import AsyncTransactionBuilder
from tronpy.exceptions import AddressNotFound

from web3mt.consts import env, DEV, settings
from web3mt.onchain.evm.models import DefaultABIs
from web3mt.onchain.tron.models import Token, tron_symbol, TokenAmount
from web3mt.utils.logger import my_logger as logger

from web3mt.onchain.tron.account import TronAccount

public_node = 'https://tron-rpc.publicnode.com'
tron_rpcs = [
    'https://api.trongrid.io',
    public_node
]
private_rpc = 'http://92.53.84.170:8090'
USDT = Token(address='TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', symbol='USDT')


class Resource(str, enum.Enum):
    ENERGY = 'ENERGY'
    BANDWIDTH = 'BANDWIDTH'


class AccountData:
    def __init__(
            self,
            account: TronAccount,
            balance: TokenAmount,
            create_time: datetime,
            latest_operation_time: datetime,
            free_net_usage: int,
            latest_consume_free_time: datetime,
            net_window_size: int,
            net_window_optimized: bool,
    ):
        self.account = account


class BaseClient:
    native_tron = Token()

    def __init__(self, account: TronAccount = None, http_rpc: str = public_node):
        self.account = account or TronAccount.create()
        self.w3 = AsyncTron(
            AsyncHTTPProvider(http_rpc, api_key=env.TRONGRID_API_KEY if 'trongrid' in http_rpc else DEFAULT_API_KEY)
        )

    @property
    def account(self) -> TronAccount:
        return self._account

    @account.setter
    def account(self, account: TronAccount):
        self._account: TronAccount = account
        self._update_log_info()

    def _update_log_info(self):
        self.log_info = f'{self._account.address} (Tron)'

    async def tx(
            self,
            name: str,
            builder: AsyncTransactionBuilder,
            from_: TronAccount = None,
            wait: bool = True
    ) -> dict | None:
        from_ = from_ or self.account
        tx = await (await builder.build()).sign(from_.key).broadcast()
        if wait:
            tx_data = await tx.wait()
            if tx_id := tx_data['id']:
                logger.debug(f'{self.log_info} | {name} done. Tx: {tx_id}')
                return tx_data
            else:
                logger.warning(f'Transaction {name} failed. Data: {tx_data}')
                return None
        else:
            if tx['result']:
                logger.debug(f'{self.log_info} | {name} done')
                return tx
            logger.warning(f'Transaction {name} failed. Data: {tx}')
            return None

    async def send_trx(
            self, amount: TokenAmount, to: str | TronAccount, from_: TronAccount = None
    ) -> str | None:
        from_ = from_ or self.account
        await self.tx(
            to=to,
            name=f'Transfer {amount} to {to}',
            builder=self.w3.trx.transfer(from_.address, to if isinstance(to, str) else to.address, amount.sun),
            from_=from_,
            amount=amount.sun,
        )

    async def get_account(self) -> Optional[dict]:
        try:
            data = await self.w3.get_account(self.account.address)
            return data
        except AddressNotFound as e:
            logger.warning(f'Account {self.account.address} not found on-chain. Deposit some TRX to activate')
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
            self, contract: AsyncContract = None, token: Token = native_tron, owner_address: str = None,
            echo: bool = DEV,
            remove_zero_from_echo: bool = DEV
    ) -> TokenAmount | None:
        owner_address = owner_address or self.account.address
        if token.symbol != tron_symbol:
            token = await self.get_onchain_token_info(contract=contract, token=token)
            contract = contract or AsyncContract(token.address, abi=DefaultABIs.token, client=self.w3)
            amount = await contract.functions.balanceOf(owner_address).call()
            balance = TokenAmount(amount, True, token)
        else:
            try:
                balance = TokenAmount(await self.w3.get_account_balance(owner_address))
            except AddressNotFound as e:
                logger.warning(f'Account {self.account.address} not found on-chain. Deposit some TRX to activate')
                return None
        if echo:
            if not remove_zero_from_echo:
                logger.debug(f'{self.log_info} | Balance - {balance}')
            elif balance:
                logger.debug(f'{self.log_info} | Balance - {balance}')
        return balance


class PrivateBaseClient(BaseClient):
    def __init__(self, account: TronAccount = None, http_rpc: str = private_rpc):
        super().__init__(account, http_rpc)
        self._ledger_account = TronAccount(settings.TRON_LEDGER_PRIVATE_KEY)

    async def activate_account(self) -> bool:
        if await self.balance_of():
            logger.debug(f'{self.log_info} | Account {self.account.address} is already activated')
            return True
        await self.send_trx(to=self.account.address, from_=self._ledger_account, amount=TokenAmount(100))


async def main():
    client = BaseClient(my_account)

    # data = await client.get_account()
    # data = await client.get_onchain_token_info(token=USDT)

    balance = await client.balance_of()

    return balance


async def main_private():
    ledger_balance = await ledger_client.balance_of()
    await my_client.activate_account()
    my_account_data = await my_client.get_account()
    return my_account_data


async def deposit_from_ledger():
    await my_client.balance_of(echo=True)
    tx_id = await ledger_client.send_trx(TokenAmount(100), my_account)
    data = await ledger_client.w3.get_transaction(tx_id)
    await my_client.balance_of(echo=True)


async def freeze_balance():
    await my_client.get_account()
    amount = TokenAmount(1)
    resource_type = Resource.ENERGY
    await my_client.tx(
        f'Freeze {amount} for {resource_type}',
        my_client.w3.trx.freeze_balance(my_account.address, amount.sun, resource_type),
    )
    resource_type = Resource.BANDWIDTH
    await my_client.tx(
        f'Freeze {amount} for {resource_type}',
        my_client.w3.trx.freeze_balance(my_account.address, amount.sun, resource_type),
    )


if __name__ == '__main__':
    ledger_account = TronAccount.from_key(settings.TRON_LEDGER_PRIVATE_KEY)
    my_account = TronAccount.from_key(settings.TRON_PRIVATE_KEY)
    my_client = PrivateBaseClient(my_account)
    ledger_client = PrivateBaseClient(ledger_account)
    asyncio.run(freeze_balance())
