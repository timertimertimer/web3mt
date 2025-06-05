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

from web3mt.onchain.tron.account import Account

public_node = 'https://tron-rpc.publicnode.com'
tron_rpcs = [
    'https://api.trongrid.io',
    public_node
]
private_rpc = 'http://92.53.84.170:8090'
USDT = Token(address='TR7NHqjeKQxGTCi8q8ZY4pL8otSzgjLj6t', symbol='USDT')
PRIVATE_USDT = Token(address='TPBxYYbRN1Y3Hejf9EWznTqdxovVWi4VQ4', symbol='USDT')


class Resource(str, enum.Enum):
    ENERGY = 'ENERGY'
    BANDWIDTH = 'BANDWIDTH'


class AccountData:
    def __init__(
            self,
            account: Account,
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

    def __init__(self, account: Account = None, http_rpc: str = public_node):
        self.account = account or Account.create()
        self.w3 = AsyncTron(
            AsyncHTTPProvider(http_rpc, api_key=env.TRONGRID_API_KEY if 'trongrid' in http_rpc else DEFAULT_API_KEY)
        )

    @property
    def account(self) -> Account:
        return self._account

    @account.setter
    def account(self, account: Account):
        self._account: Account = account
        self._update_log_info()

    def _update_log_info(self):
        self.log_info = f'{self._account.address} (Tron)'

    async def tx(
            self,
            name: str,
            builder: AsyncTransactionBuilder,
            from_: Account = None,
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
            self, amount: TokenAmount, to: str | Account, from_: Account = None
    ) -> str | None:
        from_ = from_ or self.account
        await self.tx(
            name=f'Transfer {amount} to {to}',
            builder=self.w3.trx.transfer(from_.address, to if isinstance(to, str) else to.address, amount.sun),
            from_=from_,
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
            amount = await contract.functions.balanceOf(owner_address)
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

    async def transfer_token(
            self,
            to: str | Account,
            amount: TokenAmount,
            use_full_balance: bool = False,
            **kwargs
    ):
        if isinstance(to, Account):
            to = to.address
        balance = await self.balance_of(token=amount.token)
        if use_full_balance:
            amount = balance
        if balance.sun < amount.sun:
            logger.warning(f'{self.log_info} | Balance - {balance} < amount - {amount}')
            return False, ''
        contract = AsyncContract(amount.token.address, abi=DefaultABIs.token, client=self.w3)
        return await self.tx(
            f'Transfer {amount} to {to}',
            builder=await contract.functions.transfer(to, amount.sun),
            **kwargs
        )


class PrivateBaseClient(BaseClient):
    def __init__(self, account: Account = None, http_rpc: str = private_rpc):
        super().__init__(account, http_rpc)
        self._ledger_account = Account(settings.TRON_LEDGER_PRIVATE_KEY)

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
    ledger_balance = await ledger_private_client.balance_of()
    await my_private_client.activate_account()
    my_account_data = await my_private_client.get_account()
    return my_account_data


async def deposit_from_ledger():
    await my_private_client.balance_of(echo=True)
    tx_id = await ledger_private_client.send_trx(TokenAmount(100), my_account)
    data = await ledger_private_client.w3.get_transaction(tx_id)
    await my_private_client.balance_of(echo=True)


async def freeze_balance():
    await my_private_client.get_account()
    amount = TokenAmount(1)
    resource_type = Resource.ENERGY
    await my_private_client.tx(
        f'Freeze {amount} for {resource_type}',
        my_private_client.w3.trx.freeze_balance(my_account.address, amount.sun, resource_type),
    )
    resource_type = Resource.BANDWIDTH
    await my_private_client.tx(
        f'Freeze {amount} for {resource_type}',
        my_private_client.w3.trx.freeze_balance(my_account.address, amount.sun, resource_type),
    )


async def get_usdt_balance():
    ledger_balance = await ledger_private_client.balance_of(token=PRIVATE_USDT)
    balance = await witness_private_client.balance_of(token=PRIVATE_USDT)
    print(balance)

async def transfer_usdt():
    await witness_private_client.transfer_token(to=my_private_client.account, amount=TokenAmount(100, token=PRIVATE_USDT))


if __name__ == '__main__':
    witness_account = Account.from_key(settings.TRON_WITNESS_PRIVATE_KEY)
    ledger_account = Account.from_key(settings.TRON_LEDGER_PRIVATE_KEY)
    my_account = Account.from_key(settings.TRON_PRIVATE_KEY)
    my_private_client = PrivateBaseClient(my_account)
    my_client = BaseClient(my_account)
    ledger_private_client = PrivateBaseClient(ledger_account)
    witness_private_client = PrivateBaseClient(witness_account)
    asyncio.run(get_usdt_balance())
