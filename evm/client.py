import os

from hexbytes import HexBytes
from dotenv import load_dotenv
from typing import Optional

from web3 import AsyncWeb3, Web3
from web3.eth import AsyncEth
from web3.net import AsyncNet
from web3.contract import AsyncContract
from web3.exceptions import ABIFunctionNotFound, ContractLogicError
from web3.middleware import async_geth_poa_middleware
from eth_account import Account
from okx.MarketData import MarketAPI

from web3db.models import Profile
from web3db.utils import decrypt

from evm.config import TOKEN_ABI
from evm.models import TokenAmount, Network
from utils import logger, sleep

load_dotenv()
okx_api_key = os.getenv('OKX_API_KEY')
okx_api_secret = os.getenv('OKX_API_SECRET')
okx_passphrase = os.getenv('OKX_API_PASSPHRASE')


class Client:
    default_abi = None
    token_abi = TOKEN_ABI

    def __init__(
            self,
            network: Network,
            profile: Profile = None,
            account: Account = None,
            proxy: str = None,
            delay_between_requests: int = 0,
            sleep_echo: bool = False
    ):
        self.profile = profile
        self.account = Account.from_key(decrypt(profile.evm_private, os.getenv('PASSPHRASE'))) if profile else account
        self.network = network
        self.w3 = Web3(
            Web3.AsyncHTTPProvider(self.network.rpc, request_kwargs={'proxy': proxy}),
            modules={'eth': (AsyncEth,), 'net': (AsyncNet,)},
            middlewares=[async_geth_poa_middleware]
        )
        self.delay_between_requests = delay_between_requests
        self.sleep_echo = sleep_echo

    async def nonce(self):
        return await self.w3.eth.get_transaction_count(self.account.address)

    async def get_decimals(self, contract: AsyncContract = None, token_address: str = None) -> int:
        if not contract:
            contract = self.w3.eth.contract(
                address=AsyncWeb3.to_checksum_address(token_address),
                abi=self.token_abi
            )
        try:
            return int(await contract.functions.decimals().call())
        except (ABIFunctionNotFound, ContractLogicError) as e:
            return 0

    async def balance_of(self, contract: AsyncContract = None, token_address: str = None,
                         address: Optional[str] = None) -> TokenAmount:
        if not address:
            address = self.account.address
        if not contract:
            contract = self.w3.eth.contract(address=AsyncWeb3.to_checksum_address(token_address), abi=self.token_abi)
        amount = await contract.functions.balanceOf(address).call()
        await sleep(
            self.delay_between_requests,
            profile_id=self.profile.id if self.profile else None,
            echo=self.sleep_echo
        )
        decimals = await self.get_decimals(contract=contract)
        return TokenAmount(
            amount=amount,
            decimals=decimals,
            wei=True
        )

    async def get_allowance(
            self, spender: str, contract: AsyncContract = None,
            token_address: str = None
    ) -> TokenAmount:
        if not contract:
            contract = self.w3.eth.contract(address=AsyncWeb3.to_checksum_address(token_address), abi=self.token_abi)
        amount = await contract.functions.allowance(self.account.address, spender).call()
        await sleep(
            self.delay_between_requests,
            profile_id=self.profile.id if self.profile else None,
            echo=self.sleep_echo
        )
        decimals = await self.get_decimals(contract=contract)
        await sleep(
            self.delay_between_requests,
            profile_id=self.profile.id if self.profile else None,
            echo=self.sleep_echo
        )
        return TokenAmount(amount=amount, decimals=decimals, wei=True)

    @staticmethod
    async def get_max_priority_fee_per_gas(w3: AsyncWeb3, block: dict) -> int:
        block_number = block['number']
        latest_block_transaction_count = w3.eth.get_block_transaction_count(block_number)
        max_priority_fee_per_gas_lst = []
        for i in range(latest_block_transaction_count):
            try:
                transaction = w3.eth.get_transaction_by_block(block_number, i)
                if 'maxPriorityFeePerGas' in transaction:
                    max_priority_fee_per_gas_lst.append(transaction['maxPriorityFeePerGas'])
            except Exception as e:
                continue

        if not max_priority_fee_per_gas_lst:
            max_priority_fee_per_gas = w3.eth.max_priority_fee
        else:
            max_priority_fee_per_gas_lst.sort()
            max_priority_fee_per_gas = max_priority_fee_per_gas_lst[len(max_priority_fee_per_gas_lst) // 2]
        return max_priority_fee_per_gas

    async def send_transaction(
            self,
            to,
            data=None,
            from_=None,
            increase_gas=1.1,
            value=None,
            max_priority_fee_per_gas: Optional[int] = None,
            max_fee_per_gas: Optional[int] = None
    ) -> tuple[bool, Exception | HexBytes | str]:
        if not from_:
            from_ = self.account.address

        tx_params = {
            'chainId': self.network.chain_id,
            'nonce': await self.nonce(),
            'from': AsyncWeb3.to_checksum_address(from_),
            'to': AsyncWeb3.to_checksum_address(to),
        }
        await sleep(
            self.delay_between_requests,
            profile_id=self.profile.id if self.profile else None,
            echo=self.sleep_echo
        )
        if data:
            tx_params['data'] = data
        if value:
            tx_params['value'] = value

        if self.network.eip1559_tx:
            last_block = await self.w3.eth.get_block('latest')
            await sleep(
                self.delay_between_requests,
                profile_id=self.profile.id if self.profile else None,
                echo=self.sleep_echo
            )
            if max_priority_fee_per_gas is None:
                # max_priority_fee_per_gas = await Client.get_max_priority_fee_per_gas(w3=w3, block=last_block)
                max_priority_fee_per_gas = await self.w3.eth.max_priority_fee
                await sleep(
                    self.delay_between_requests,
                    profile_id=self.profile.id if self.profile else None,
                    echo=self.sleep_echo
                )
            tx_params['maxPriorityFeePerGas'] = max_priority_fee_per_gas
            if max_fee_per_gas is None:
                base_fee = int(last_block['baseFeePerGas'] * increase_gas)
                max_fee_per_gas = base_fee + max_priority_fee_per_gas
            tx_params['maxFeePerGas'] = max_fee_per_gas

        else:
            tx_params['gasPrice'] = self.w3.eth.gas_price

        try:
            tx_params['gas'] = int(await self.w3.eth.estimate_gas(tx_params) * increase_gas)
            await sleep(
                self.delay_between_requests,
                profile_id=self.profile.id if self.profile else None,
                echo=self.sleep_echo
            )
        except (ContractLogicError, ValueError) as err:
            logger.error(
                f'{f"{self.profile.id} | " if self.profile else ""}{self.account.address} | Transaction failed | {err}'
            )
            return False, err
        while True:
            sign = self.w3.eth.account.sign_transaction(tx_params, self.account.key.hex())

            try:
                tx_hash = (await self.w3.eth.send_raw_transaction(sign.rawTransaction)).hex()
                break
            except ValueError as e:
                if 'invalid nonce' in e.args[0]["message"]:
                    tx_params['nonce'] += 1
                    continue
                logger.error(
                    f'{f"{self.profile.id} | " if self.profile else ""}{self.account.address} | {e.args[0]["message"]}'
                )
                return False, e
            except Exception as e:
                logger.error(f'{f"{self.profile.id} | " if self.profile else ""}{self.account.address} | {e}')
                return False, e
        logger.info(
            f'{f"{self.profile.id} | " if self.profile else ""}{self.account.address} | '
            f'Transaction {tx_hash} sent'
        )
        return True, tx_hash

    async def verify_transaction(self, tx_hash: str, tx_name: str) -> bool:
        try:
            data = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=200)
            if 'status' in data and data['status'] == 1:
                logger.info(
                    f'{f"{self.profile.id} | " if self.profile else ""}{self.account.address} | '
                    f'Transaction {tx_name} ({tx_hash}) was successful')
                return True
            else:
                logger.error(
                    f'{f"{self.profile.id} | " if self.profile else ""}{self.account.address} | '
                    f'Transaction {tx_name} ({tx_hash}) failed: {data["transactionHash"].hex()}'
                )
                return False
        except Exception as err:
            logger.error(
                f'{f"{self.profile.id} | " if self.profile else ""}{self.account.address} | '
                f'Transaction {tx_name} ({tx_hash}) failed: {err}'
            )
            return False

    async def approve(
            self, spender: str, contract: AsyncContract = None, token_address: str = None,
            amount: TokenAmount | int = None, abi: dict = None
    ) -> bool:
        if isinstance(amount, int):
            amount = TokenAmount(amount, wei=True)
        if not contract:
            contract = self.w3.eth.contract(
                address=AsyncWeb3.to_checksum_address(token_address),
                abi=abi or self.token_abi
            )
        balance = await self.balance_of(contract=contract)
        await sleep(
            self.delay_between_requests,
            profile_id=self.profile.id if self.profile else None,
            echo=self.sleep_echo
        )
        token_symbol = await contract.functions.symbol().call()
        await sleep(
            self.delay_between_requests,
            profile_id=self.profile.id if self.profile else None,
            echo=self.sleep_echo
        )

        if balance.Wei <= 0:
            logger.warning(
                f'{f"{self.profile.id} | " if self.profile else ""}{self.account.address} | '
                f'{balance.Wei} {token_symbol}. Can\'t approve zero balance'
            )
            return False

        if not amount or amount.Wei > balance.Wei:
            amount = balance

        approved = await self.get_allowance(contract=contract, spender=spender)

        if amount.Wei <= approved.Wei:
            logger.info(
                f'{f"{self.profile.id} | " if self.profile else ""}{self.account.address} | '
                f'Already approved {approved.Ether} {token_symbol}'
            )
            return True

        await sleep(
            self.delay_between_requests,
            profile_id=self.profile.id if self.profile else None,
            echo=self.sleep_echo
        )
        ok, tx_hash = await self.send_transaction(
            to=token_address,
            data=contract.encodeABI('approve',
                                    args=(
                                        spender,
                                        amount.Wei
                                    ))
        )
        await sleep(
            self.delay_between_requests,
            profile_id=self.profile.id if self.profile else None,
            echo=self.sleep_echo
        )
        return await self.verify_transaction(tx_hash, f'Approve {token_symbol}')

    @staticmethod
    async def get_token_price(token='ETH'):
        ticker = token.upper()
        okx_market = MarketAPI(
            api_key=okx_api_key,
            api_secret_key=okx_api_secret,
            passphrase=okx_passphrase,
            flag='0',
            debug=False
        )
        price = float(okx_market.get_ticker(f'{ticker}-USDT')['data'][0]['askPx'])
        return price

    async def get_native_balance(self, address: str = None, echo: bool = False) -> TokenAmount:
        balance = TokenAmount(
            amount=await self.w3.eth.get_balance(address or self.account.address),
            wei=True
        )
        if echo:
            logger.info(
                f'{f"{self.profile.id} | " if self.profile else ""}{address or self.account.address} | '
                f'Balance - {float(balance.Ether)} {self.network.coin_symbol} ({self.network.name})',
            )
        return balance
