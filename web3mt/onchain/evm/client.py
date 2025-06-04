from _decimal import Decimal
from aiohttp import ClientHttpProxyError, ClientResponseError
from hexbytes import HexBytes
from web3 import AsyncWeb3, AsyncHTTPProvider
from web3.eth import AsyncEth
from web3.middleware import (
    ExtraDataToPOAMiddleware, AttributeDictMiddleware, ENSNameToAddressMiddleware,
    ValidationMiddleware, Web3Middleware
)
from web3.net import AsyncNet
from web3.types import _Hash32
from web3.contract import AsyncContract
from web3.exceptions import ContractLogicError, TimeExhausted
from eth_account import Account
from eth_account.messages import encode_defunct
from eth_account.signers.local import LocalAccount
from eth_utils import to_checksum_address, from_wei
from web3db import Profile
from web3db.utils import decrypt
from web3mt.onchain.evm.models import *
from web3mt.consts import env, DEV
from web3mt.utils import sleep, my_logger as logger

__all__ = [
    'TransactionParameters', 'ProfileClient', 'ClientConfig', 'BaseClient'
]


class TransactionParameters:
    gas_limit_multiplier = 1.3
    gas_price_multiplier = 1.1

    def __init__(
            self,
            to: str | None = env.DEFAULT_EVM_ADDRESS,
            from_: str | None = env.DEFAULT_EVM_ADDRESS,
            nonce: int | None = None,
            data: str | None = None,
            value: TokenAmount | int = TokenAmount(0),
            gas_limit: int | None = None,
            max_priority_fee_per_gas: int | None = None,
            max_fee_per_gas: int | None = None,
            gas_price: int | None = None,
            chain: Chain | None = None
    ):
        self.from_ = to_checksum_address(from_)
        self.to = to_checksum_address(to)
        self.nonce = nonce
        self.data = data
        self.value = TokenAmount(value, True, chain.native_token) if isinstance(value, int) else value
        self.max_fee_per_gas = max_fee_per_gas
        self.chain = chain
        self._gas_limit = gas_limit
        self._gas_price = gas_price
        self._max_priority_fee_per_gas = max_priority_fee_per_gas

    def __repr__(self):
        return (
                f'TransactionParameters(from={self.from_}, to={self.to}, nonce={self.nonce}, data={self.data}, '
                f'value={self.value}, chain_id={self.chain.chain_id}, gas_limit={self._gas_limit}, ' +
                (
                    f'gas_price={from_wei(self.gas_price, "gwei")}' if self.gas_price
                    else f'max_fee_per_gas={from_wei(self.max_fee_per_gas, "gwei")} GWEI, '
                         f'max_priority_fee_per_gas={from_wei(self.max_priority_fee_per_gas, "gwei")} GWEI'
                ) + ')'
        )

    def __str__(self):
        return self.__repr__()

    @property
    def gas_limit(self):
        return self._gas_limit

    @gas_limit.setter
    def gas_limit(self, gas_limit):
        self._gas_limit = int(gas_limit * self.gas_limit_multiplier)

    @property
    def gas_price(self):
        return self._gas_price

    @gas_price.setter
    def gas_price(self, gas_price):
        self._gas_price = int(gas_price * self.gas_price_multiplier)

    @property
    def max_priority_fee_per_gas(self):
        return self._max_priority_fee_per_gas

    @max_priority_fee_per_gas.setter
    def max_priority_fee_per_gas(self, max_priority_fee_per_gas):
        self._max_priority_fee_per_gas = int(max_priority_fee_per_gas * self.gas_price_multiplier)

    @property
    def fee(self) -> TokenAmount:
        return TokenAmount(
            self.gas_limit * self.max_fee_per_gas if self.chain.eip1559_tx else self.gas_limit * self.gas_price, True,
            self.chain.native_token
        )

    def to_dict(self):
        d = {
            'from': self.from_,
            'to': self.to,
            'nonce': self.nonce,
            'chainId': self.chain.chain_id,
        }
        if self.data:
            d['data'] = self.data
        if self.value:
            d['value'] = self.value.wei
        if self.max_priority_fee_per_gas is not None:
            d['maxPriorityFeePerGas'] = self.max_priority_fee_per_gas
        if self.max_fee_per_gas:
            d['maxFeePerGas'] = self.max_fee_per_gas
        if self.gas_price:
            d['gasPrice'] = self.gas_price
        if self.gas_limit:
            d['gas'] = self.gas_limit
        return d


class SleepAfterRequestMiddleware(Web3Middleware):
    delay_between_requests = 0
    log_info = 'BaseClient'
    sleep_echo = True

    async def async_wrap_make_request(self, make_request):
        async def middleware(method, params):
            response = await make_request(method, params)
            await sleep(self.delay_between_requests, log_info=self.log_info, echo=self.sleep_echo)
            return response

        return middleware


class ClientConfig:
    def __init__(
            self,
            delay_between_requests: int = 0,
            sleep_echo: bool = DEV,
            do_no_matter_what: bool = False,
            wait_for_gwei: bool = True
    ):
        self.delay_between_requests = delay_between_requests
        self.sleep_echo = sleep_echo
        self.do_no_matter_what = do_no_matter_what
        self.wait_for_gwei = wait_for_gwei


class BaseClient:
    def __init__(
            self,
            account: LocalAccount = None,
            chain: Chain = Ethereum,
            proxy: str = env.DEFAULT_PROXY,
            config: ClientConfig = ClientConfig(),
    ):
        self._chain = chain
        self.config = config
        self.account = account or Account.create()
        self.proxy = proxy

    def __str__(self):
        return self.log_info

    async def __aenter__(self):
        logger.info(f'{self.log_info} | Started')
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f'{self.log_info} | {exc_val}')
        else:
            logger.success(f'{self.log_info} | Tasks done')

    @property
    def proxy(self) -> str:
        return self._proxy

    @proxy.setter
    def proxy(self, proxy):
        self._proxy = proxy
        self._update_web3()

    @property
    def account(self) -> LocalAccount:
        return self._account

    @account.setter
    def account(self, account: LocalAccount):
        self._account: LocalAccount = account
        self._update_log_info()

    @property
    def chain(self) -> Chain:
        return self._chain

    @chain.setter
    def chain(self, chain: Chain):
        self._chain = chain
        self._update_log_info()
        self._update_web3()

    @staticmethod
    async def get_max_priority_fee_per_gas(w3: AsyncWeb3, block: dict) -> int:
        block_number = block['number']
        latest_block_transaction_count = w3.eth.get_block_transaction_count(block_number)
        max_priority_fee_per_gas_lst = []
        for i in range(latest_block_transaction_count):
            try:
                transaction = w3.eth.get_transaction_by_block(block_number, i)
                if 'maxPriorityFeePerGas' in transaction:
                    max_priority_fee_per_gas_lst.append(transaction.max_priority_fee_per_gas)
            except Exception as e:
                continue

        if not max_priority_fee_per_gas_lst:
            max_priority_fee_per_gas = w3.eth.max_priority_fee
        else:
            max_priority_fee_per_gas_lst.sort()
            max_priority_fee_per_gas = max_priority_fee_per_gas_lst[len(max_priority_fee_per_gas_lst) // 2]
        return max_priority_fee_per_gas

    def _update_log_info(self):
        self.log_info = f'{self._account.address} ({self._chain.name})'

    def _update_web3(self):
        SleepAfterRequestMiddleware.delay_between_requests = self.config.delay_between_requests
        SleepAfterRequestMiddleware.log_info = self.log_info
        SleepAfterRequestMiddleware.echo = self.config.sleep_echo
        self.w3 = AsyncWeb3(
            # TODO: If rpc sends exception try to get another rpc from self._chain.rpc list
            AsyncHTTPProvider(self._chain.rpc, request_kwargs={'timeout': 5, 'proxy': self._proxy}),
            modules={'eth': (AsyncEth,), 'net': (AsyncNet,)},
            middleware=[
                AttributeDictMiddleware, ENSNameToAddressMiddleware,
                ValidationMiddleware, SleepAfterRequestMiddleware
            ]
        )
        self.w3.middleware_onion.inject(ExtraDataToPOAMiddleware, layer=0)

    def sign(self, text) -> str:
        return self.w3.eth.account.sign_message(
            encode_defunct(text=text), private_key=self.account.key.hex()
        ).signature.hex()

    async def nonce(self, owner_address: str = None) -> int:
        owner_address = owner_address or self.account.address
        return await self.w3.eth.get_transaction_count(owner_address)

    async def get_onchain_token_info(self, contract: AsyncContract = None, token: Token = None) -> Token | None:
        if token == self.chain.native_token:
            logger.warning(f'{self.log_info} | Can\'t get native token info')
            return None
        contract = contract or self.w3.eth.contract(to_checksum_address(token.address), abi=DefaultABIs.token)
        token = token or Token(self.chain, address=contract.address)
        async with self.w3.batch_requests() as batch:
            batch.add(contract.functions.decimals())
            batch.add(contract.functions.name())
            batch.add(contract.functions.symbol())
            token.decimals, token.name, token.symbol = await batch.async_execute()
        return token

    async def get_allowance(
            self, spender_contract: AsyncContract, token: Token, owner_address: str = None
    ) -> TokenAmount:
        contract = self.w3.eth.contract(to_checksum_address(token.address), abi=DefaultABIs.token)
        amount = await contract.functions.allowance(owner_address, spender_contract.address).call()
        token = await self.get_onchain_token_info(contract, token)
        return TokenAmount(amount, True, token)

    async def update_token_price(self, token: Token = None) -> None:
        token = token or self.chain.native_token
        await token.update_price()
        return token.price

    async def balance_of(
            self, contract: AsyncContract = None, token: Token = None, owner_address: str = None, echo: bool = DEV,
            remove_zero_from_echo: bool = DEV
    ) -> TokenAmount:
        owner_address = owner_address or self.account.address
        token = token or self.chain.native_token
        if token != self.chain.native_token:
            token = await self.get_onchain_token_info(contract=contract, token=token)
            contract = contract or self.w3.eth.contract(to_checksum_address(token.address), abi=DefaultABIs.token)
            amount = await contract.functions.balanceOf(owner_address).call()
            balance = TokenAmount(amount, True, token)
        else:
            balance = await self._native_balance(owner_address)
        if echo:
            if not remove_zero_from_echo:
                logger.debug(f'{self.log_info} | Balance - {balance}')
            elif balance:
                logger.debug(f'{self.log_info} | Balance - {balance}')
        return balance

    async def _native_balance(self, owner_address: str) -> TokenAmount:
        try:
            balance = await self.w3.eth.get_balance(to_checksum_address(owner_address))
        except (ClientHttpProxyError, ClientResponseError) as e:
            logger.error(
                f'{self.log_info} | Couldn\'t fetch {self.chain.native_token.symbol} balance. {e.message or type(e)}'
            )
            balance = 0
        except TimeoutError:
            logger.warning(f'{self.log_info} | Timeout. Maybe bad proxy: {self.proxy}')
            balance = 0
        except Exception as e:
            pass
        return TokenAmount(amount=balance, is_wei=True, token=Token(chain=self.chain))

    async def wait_for_gwei(self):
        if self.chain.max_gwei and self.config.wait_for_gwei:
            while True:
                gas_price = from_wei(await self.w3.eth.gas_price, 'gwei')
                if gas_price > self.chain.max_gwei:
                    logger.debug(
                        f'{self.log_info} | Current GWEI: {gas_price} > {self.chain.max_gwei}. Waiting for gwei...'
                    )
                    await sleep(15, log_info=self.log_info, echo=self.config.sleep_echo)
                else:
                    break

    async def tx(
            self,
            to: str,
            name: str,
            data: str = None,
            value: TokenAmount = TokenAmount(0),
            gas_limit: int = None,
            max_priority_fee_per_gas: int = None,
            max_fee_per_gas: int = None,
            use_full_balance: bool = False,
            return_fee_in_usd: bool = False,
            **kwargs
    ) -> tuple[bool, str | Exception | HexBytes] | Decimal:
        tx_params = await self.create_tx_params(
            to=to, data=data, value=value, gas_limit=gas_limit, max_priority_fee_per_gas=max_priority_fee_per_gas,
            max_fee_per_gas=max_fee_per_gas, use_full_balance=use_full_balance, **kwargs
        )
        if isinstance(tx_params, tuple) and not tx_params[0]:
            return tx_params
        res = await self.tx_with_params(name, tx_params)
        if return_fee_in_usd and res:
            return tx_params.fee.amount_in_usd
        return res

    async def create_tx_params(
            self,
            to: str = None,
            data: str = None,
            gas_limit: int = None,
            value: TokenAmount | int = TokenAmount(0),
            max_priority_fee_per_gas: int = None,
            max_fee_per_gas: int = None,
            use_full_balance: bool = False,
            tx_params: TransactionParameters = None,
            **kwargs
    ) -> TransactionParameters | tuple[bool, str]:
        nonce = kwargs.get('nonce', await self.nonce())
        tx_params = tx_params or TransactionParameters(
            from_=self.account.address, to=to, nonce=nonce, data=data, value=value,
            gas_limit=gas_limit, max_priority_fee_per_gas=max_priority_fee_per_gas, max_fee_per_gas=max_fee_per_gas,
            chain=self.chain
        )
        await self.wait_for_gwei()
        if not tx_params.gas_limit:
            try:
                tx_p_d = tx_params.to_dict()
                tx_params.gas_limit = await self.w3.eth.estimate_gas(tx_p_d)
            except (ContractLogicError, ValueError) as err:
                logger.warning(f'{self.log_info} | Couldn\'t estimate gas. Transaction wasn\'t send - {err}')
                return False, err
        if self.chain.eip1559_tx:
            if not tx_params.max_priority_fee_per_gas:
                tx_params.max_priority_fee_per_gas = await self.w3.eth.max_priority_fee
            latest_block = await self.w3.eth.get_block('latest')
            base_fee_per_gas = latest_block.get('baseFeePerGas', 0)
            if not tx_params.max_fee_per_gas:
                tx_params.max_fee_per_gas = base_fee_per_gas + tx_params.max_priority_fee_per_gas
        else:
            tx_params.gas_price = await self.w3.eth.gas_price
        if value.token == self.chain.native_token and use_full_balance:
            tx_params.value = await self.balance_of() - tx_params.fee - TokenAmount(0.0001,
                                                                                    token=self.chain.native_token)
        return tx_params

    async def tx_with_params(
            self, name: str, tx_params: TransactionParameters
    ) -> tuple[bool, Exception | HexBytes | str]:
        while True:
            ok, tx_hash_or_err = await self._send_transaction(tx_params)
            try:
                res = await self.verify_transaction(tx_hash_or_err, name)
                break
            except TimeExhausted:
                if self.config.do_no_matter_what:
                    tx_params = await self.create_tx_params(tx_params=tx_params)
                else:
                    return ok, tx_hash_or_err
        if res:
            logger.debug(f'{self.log_info} | {name} done. Cost - {tx_params.value}. Fee - {tx_params.fee}')
        return res, tx_hash_or_err

    async def _send_transaction(self, tx_params: TransactionParameters) -> tuple[bool, Exception | HexBytes | str]:
        while True:
            try:
                sign = self.w3.eth.account.sign_transaction(tx_params.to_dict(), self.account.key.hex())
            except Exception as e:
                input()
            try:
                tx_hash = (await self.w3.eth.send_raw_transaction(sign.raw_transaction)).hex()
                break
            except ValueError as e:
                error_message = e.args[0]["message"]
                if 'invalid nonce' in error_message or 'nonce too low' in error_message:
                    tx_params.nonce += 1
                elif 'replacement transaction underpriced' in error_message:
                    last_block = await self.w3.eth.get_block('latest')
                    tx_params.max_priority_fee_per_gas = tx_params.max_priority_fee_per_gas
                    tx_params.max_fee_per_gas = last_block['baseFeePerGas'] + tx_params.max_priority_fee_per_gas
                elif 'overshot' in error_message:
                    overshot = TokenAmount(int(error_message.split('overshot ')[1]), True, self.chain.native_token)
                    ratio = overshot.wei / tx_params.value.wei
                    if ratio < 0.1:
                        logger.debug(f'{self.log_info} | Some overshot. Reducing tx value to -{overshot}')
                        tx_params.value -= overshot
                    else:
                        logger.warning(
                            f'{self.log_info} | {error_message}. Ratio of tx value and overshot: {ratio}%')
                        return False, e
                else:
                    logger.warning(f'{self.log_info} | {error_message}')
                    return False, e
            except Exception as e:
                logger.error(f'{self.log_info} | {e}')
                return False, e
        if not tx_hash.startswith('0x'):
            tx_hash = '0x' + tx_hash
        logger.info(f'{self.log_info} | Transaction {self.chain.explorer}/tx/{tx_hash} with {tx_params} sent')
        return True, tx_hash

    async def verify_transaction(self, tx_hash: _Hash32, tx_name: str) -> bool:
        explorer_link = f'{self.chain.explorer}/tx/{tx_hash}'
        while True:
            try:
                data = await self.w3.eth.wait_for_transaction_receipt(tx_hash, 240)
                if 'status' in data and data['status'] == 1:
                    logger.debug(
                        f'{self.log_info} | Transaction {tx_name} ({explorer_link}) was successful'
                    )
                    return True
                else:
                    logger.error(
                        f'{self.log_info} | Transaction {tx_name} ({explorer_link}) failed: '
                        f'{data["transactionHash"].hex()}'
                    )
                    return False
            except TimeExhausted as e:
                logger.warning(f'{self.log_info} | Transaction {tx_name} ({explorer_link}) failed: {e}')
                if self.config.do_no_matter_what:
                    raise e
                return False
            except Exception as err:
                logger.warning(f'{self.log_info} | Transaction {tx_name} ({tx_hash}) failed: {err}')
                return False


class ProfileClient(BaseClient):

    def __init__(
            self,
            profile: Profile,
            chain: Chain = Ethereum,
            encryption_password: str = env.PASSPHRASE,
            config: ClientConfig = ClientConfig(),
    ):
        self.profile = profile
        self._encryption_password = encryption_password
        super().__init__(
            Account.from_key(decrypt(self.profile.evm_private, self._encryption_password))
            if self.profile.evm_private.startswith('-----BEGIN PGP MESSAGE-----')
            else Account.from_key(self.profile.evm_private),
            chain,
            profile.proxy.proxy_string,
            config
        )

    def _update_log_info(self):
        self.log_info = f'{self._account.address} ({self._chain.name})'
        if self.profile:
            self.log_info = f"{self.profile.id} | {self.log_info}"

    async def get_allowance(
            self, spender_contract: AsyncContract, token: Token, owner_address: str = None
    ) -> TokenAmount:
        owner_address = owner_address or self.account.address
        return await super().get_allowance(spender_contract, token, owner_address)

    async def mint(
            self,
            to: str,
            name: str,
            data: str = None,
            value: TokenAmount = TokenAmount(0),
            gas_limit: int = None,
            max_priority_fee_per_gas: int = None,
            max_fee_per_gas: int = None,
            use_full_balance: bool = False,
            return_fee_in_usd: bool = False,
            check_existing: bool = True,
            **kwargs
    ):
        if (await self.balance_of(token=Token(self.chain, address=to))).ether > 0:
            ...

    async def approve(
            self, spender_contract: AsyncContract, amount: TokenAmount
    ) -> tuple[bool, str | Exception | HexBytes] | Decimal | None:
        balance = await self.balance_of(token=amount.token)
        amount.token = balance.token
        if balance.wei <= 0:
            logger.warning(f'{self.log_info} | {balance}. Can\'t approve zero balance')
            return
        if not amount or amount.wei > balance.wei:
            amount = balance
        approved = await self.get_allowance(spender_contract, amount.token)
        if amount.wei <= approved.wei:
            logger.info(f'{self.log_info} | Already approved {approved}')
            return
        return await self.tx(
            amount.token.address,
            f'Approve {amount}',
            self.w3.eth.contract(
                to_checksum_address(amount.token.address),
                abi=DefaultABIs.token
            ).encode_abi("approve", args=(spender_contract.address, amount.wei)),
        )

    async def transfer_token(
            self,
            to: str,
            name: str,
            amount: TokenAmount,
            use_full_balance: bool = False,
            **kwargs
    ) -> tuple[bool, Exception | HexBytes | str]:
        to = to_checksum_address(to)
        balance = await self.balance_of(token=amount.token)
        if use_full_balance:
            amount = balance
        if balance.wei < amount.wei:
            logger.warning(f'{self.log_info} | Balance - {balance} < amount - {amount}')
            return False, ''
        contract = self.w3.eth.contract(amount.token.address, abi=DefaultABIs.token)
        return await self.tx(
            contract.address, name or f'Transfer {amount} to {to}',
            data=contract.encode_abi('transfer', args=[to, amount.wei]),
            **kwargs
        )
