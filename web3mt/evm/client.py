from typing import Optional
from hexbytes import HexBytes

from web3 import AsyncWeb3, Web3
from web3.eth import AsyncEth
from web3.net import AsyncNet
from web3.contract import AsyncContract
from web3.middleware import async_geth_poa_middleware
from web3.exceptions import ABIFunctionNotFound, ContractLogicError, TimeExhausted
from eth_account import Account
from eth_account.messages import encode_defunct
from okx.MarketData import MarketAPI

from web3db.utils import decrypt
from web3db.models import Profile

from web3mt.utils import logger, sleep
from web3mt.evm.models import TokenAmount, Chain, Ethereum, DefaultABIs


class Client:
    NATIVE_PRICE = None
    INCREASE_GWEI = 1
    INCREASE_GAS_LIMIT = 1.1

    def __init__(
            self,
            network: Chain = Ethereum,
            profile: Profile = None,
            account: Account = None,
            encryption_password: str = None,
            proxy: str = None,
            delay_between_requests: int = 0,
            sleep_echo: bool = False,
            do_no_matter_what: bool = False,
            wait_for_gwei: bool = True,
            okx_api_key: str = None,
            okx_api_secret: str = None,
            okx_passphrase: str = None,
    ):
        self.profile = profile
        self.account = Account.from_key(decrypt(profile.evm_private, encryption_password)) if profile else account
        self.network = network
        self.w3 = Web3(
            Web3.AsyncHTTPProvider(self.network.rpc, request_kwargs={
                'proxy': self.profile.proxy.proxy_string if self.profile else proxy}),
            modules={'eth': (AsyncEth,), 'net': (AsyncNet,)},
            middlewares=[async_geth_poa_middleware]
        )
        self.delay_between_requests = delay_between_requests
        self.sleep_echo = sleep_echo
        self.do_no_matter_what = do_no_matter_what
        self.wait_for_gwei = wait_for_gwei
        self.log_info = ''
        if self.account:
            self.log_info += f'{self.account.address} ({self.network.name})'
        if self.profile:
            self.log_info = f"{self.profile.id} | {self.log_info}"
        self.okx_api_key = okx_api_key
        self.okx_api_secret = okx_api_secret
        self.okx_passphrase = okx_passphrase

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.error(f'{self.log_info} | {exc_val}') if exc_type else logger.success(f'{self.log_info} | Tasks done')

    def sign(self, text) -> str:
        return self.w3.eth.account.sign_message(
            encode_defunct(text=text),
            private_key=self.account.key.hex()
        ).signature.hex()

    async def nonce(self) -> int:
        return await self.w3.eth.get_transaction_count(self.account.address)

    async def get_decimals(self, contract: AsyncContract = None, token_address: str = None) -> int:
        if not contract:
            contract = self.w3.eth.contract(
                address=AsyncWeb3.to_checksum_address(token_address),
                abi=DefaultABIs.Token
            )
        try:
            return int(await contract.functions.decimals().call())
        except (ABIFunctionNotFound, ContractLogicError) as e:
            return 0

    async def balance_of(
            self, contract: AsyncContract = None, token_address: str = None,
            address: Optional[str] = None, echo: bool = False
    ) -> TokenAmount:
        if not address:
            address = self.account.address
        if not contract:
            contract = self.w3.eth.contract(address=AsyncWeb3.to_checksum_address(token_address), abi=DefaultABIs.Token)
        amount = await contract.functions.balanceOf(address).call()
        await sleep(
            self.delay_between_requests,
            profile_id=self.profile.id if self.profile else None,
            echo=self.sleep_echo
        )
        decimals = await self.get_decimals(contract=contract)
        balance = TokenAmount(amount=amount, decimals=decimals, wei=True)
        token_name = await contract.functions.symbol().call()
        if echo:
            logger.info(f'{self.log_info} | Balance - {balance} {token_name}')
        return balance

    async def get_allowance(
            self, spender: str, contract: AsyncContract = None,
            token_address: str = None
    ) -> TokenAmount:
        if not contract:
            contract = self.w3.eth.contract(address=AsyncWeb3.to_checksum_address(token_address), abi=DefaultABIs.Token)
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
            except Exception:
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
            increase_gas_limit=None,
            value=None,
            max_priority_fee_per_gas: Optional[int] = None,
            max_fee_per_gas: Optional[int] = None
    ) -> tuple[bool, Exception | HexBytes | str]:
        if not from_:
            from_ = self.account.address
        if not increase_gas_limit:
            increase_gas_limit = self.INCREASE_GAS_LIMIT

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

        if self.network.max_gwei and self.wait_for_gwei:
            while True:
                gas_price = self.w3.from_wei(await self.w3.eth.gas_price, 'gwei')
                if gas_price > self.network.max_gwei:
                    logger.debug(
                        f'{self.log_info} | Current GWEI: {gas_price} > {self.network.max_gwei}. Waiting for gwei...'
                    )
                    await sleep(15, profile_id=self.profile.id if self.profile else None, echo=self.sleep_echo)
                else:
                    break

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
            tx_params['maxFeePerGas'] = max_fee_per_gas or last_block['baseFeePerGas'] + max_priority_fee_per_gas
            tx_params['maxFeePerGas'] = int(tx_params['maxFeePerGas'] * self.INCREASE_GWEI)

        else:
            tx_params['gasPrice'] = await self.w3.eth.gas_price

        try:
            estimated_gas_limit = await self.w3.eth.estimate_gas(tx_params)
            tx_params['gas'] = int(estimated_gas_limit * increase_gas_limit)
            await sleep(
                self.delay_between_requests,
                profile_id=self.profile.id if self.profile else None,
                echo=self.sleep_echo
            )
        except (ContractLogicError, ValueError) as err:
            logger.warning(f'{self.log_info} | Couldn\'t estimate gas. Transaction wasn\'t send - {err}')
            return False, err
        while True:
            sign = self.w3.eth.account.sign_transaction(tx_params, self.account.key.hex())

            try:
                tx_hash = (await self.w3.eth.send_raw_transaction(sign.rawTransaction)).hex()
                break
            except ValueError as e:
                if 'invalid nonce' in e.args[0]["message"] or 'nonce too low' in e.args[0]["message"]:
                    old_nonce = tx_params["nonce"]
                    tx_params["nonce"] = new_nonce = tx_params["nonce"] + 1
                    logger.warning(
                        f'{self.log_info} | {e.args[0]["message"]}. Increasing nonce from {old_nonce} to {new_nonce}'
                    )
                    continue
                elif 'replacement transaction underpriced' in e.args[0]["message"]:
                    old_priority_fee = tx_params['maxPriorityFeePerGas']
                    tx_params['maxPriorityFeePerGas'] = new_priority_fee = (
                        int(tx_params['maxPriorityFeePerGas'] * self.INCREASE_GWEI)
                    )
                    logger.warning(
                        f'{self.log_info} | {e.args[0]["message"]}. '
                        f'Increasing max priorty fee from {old_priority_fee} to {new_priority_fee}'
                    )
                    continue
                logger.error(f'{self.log_info} | {e.args[0]["message"]}')
                return False, e
            except Exception as e:
                logger.error(f'{self.log_info} | {e}')
                return False, e
        logger.info(f'{self.log_info} | Transaction {tx_hash} sent')
        return True, tx_hash

    async def verify_transaction(self, tx_hash: str, tx_name: str) -> bool:
        while True:
            try:
                data = await self.w3.eth.wait_for_transaction_receipt(tx_hash)
                if 'status' in data and data['status'] == 1:
                    logger.info(f'{self.log_info} | Transaction {tx_name} ({tx_hash}) was successful')
                    return True
                else:
                    logger.error(
                        f'{self.log_info} | Transaction {tx_name} ({tx_hash}) failed: {data["transactionHash"].hex()}'
                    )
                    return False
            except TimeExhausted as e:
                logger.warning(f'{self.log_info} | Transaction {tx_name} ({tx_hash}) failed: {e}')
                if not self.do_no_matter_what:
                    return False
            except Exception as err:
                logger.warning(f'{self.log_info} | Transaction {tx_name} ({tx_hash}) failed: {err}')
                return False

    async def tx(
            self,
            to: str,
            name: str,
            data: str = '0x1249c58b',
            value: TokenAmount | int = TokenAmount(0),
            max_priority_fee_per_gas: Optional[int] = None,
            max_fee_per_gas: Optional[int] = None,
            increase_gas_limit: Optional[int] = None,
            check_existing: bool = False
    ) -> bool:
        if isinstance(value, int):
            value = TokenAmount(value, wei=True)
        to = self.w3.to_checksum_address(to)
        if check_existing:
            if (await self.balance_of(token_address=to)).Ether > 0:
                logger.success(f'{self.log_info} | {name} already minted')
                return True
            await sleep(
                self.delay_between_requests,
                profile_id=self.profile.id if self.profile else None,
                echo=self.sleep_echo
            )
        ok, tx_hash_or_err = await self.send_transaction(
            to=to, data=data, value=value.Wei,
            max_priority_fee_per_gas=max_priority_fee_per_gas,
            max_fee_per_gas=max_fee_per_gas,
            increase_gas_limit=increase_gas_limit,
        )
        await sleep(
            self.delay_between_requests,
            profile_id=self.profile.id if self.profile else None,
            echo=self.sleep_echo
        )
        res = await self.verify_transaction(tx_hash_or_err, name)
        if res:
            logger.success(f'{self.log_info} | {name} done')
        return res

    async def approve(
            self, spender: str, contract: AsyncContract = None, token_address: str = None,
            amount: TokenAmount | int = None, abi: dict = None
    ) -> bool:
        if isinstance(amount, int):
            amount = TokenAmount(amount, wei=True)
        if not contract:
            contract = self.w3.eth.contract(
                address=AsyncWeb3.to_checksum_address(token_address),
                abi=abi or DefaultABIs.Token
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
            logger.warning(f'{self.log_info} | {balance.Wei} {token_symbol}. Can\'t approve zero balance')
            return False

        if not amount or amount.Wei > balance.Wei:
            amount = balance

        approved = await self.get_allowance(contract=contract, spender=spender)

        if amount.Wei <= approved.Wei:
            logger.info(f'{self.log_info} | Already approved {approved.Ether} {token_symbol}')
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

    async def transfer_token(
            self,
            to: str,
            amount: TokenAmount,
            contract: AsyncContract = None,
            token_address: str = None,
    ) -> tuple[bool, Exception | HexBytes | str]:
        if not contract:
            contract = self.w3.eth.contract(
                address=AsyncWeb3.to_checksum_address(token_address),
                abi=DefaultABIs.Token
            )
        balance = await self.balance_of(contract=contract)
        if balance.Wei >= amount.Wei > 0:
            return await self.send_transaction(to=contract.address, data=contract.encodeABI('transfer', args=[
                self.w3.to_checksum_address(to), amount.Wei
            ]))
        else:
            logger.warning(f'{self.log_info} | Amount is too high. Balance - {balance.Ether}, amount - {amount.Ether}')
            return False, ''

    async def get_token_price(self, token='ETH') -> float:
        ticker = token.upper()
        okx_market = MarketAPI(
            api_key=self.okx_api_key,
            api_secret_key=self.okx_api_secret,
            passphrase=self.okx_passphrase,
            flag='0',
            debug=False
        )
        price = float(okx_market.get_ticker(f'{ticker}-USDT')['data'][0]['askPx'])
        return price

    async def get_native_balance(
            self,
            address: str = None,
            echo: bool = False,
            get_usd_price: bool = False
    ) -> TokenAmount:
        balance = TokenAmount(
            amount=await self.w3.eth.get_balance(address or self.account.address),
            wei=True
        )
        if get_usd_price:
            Client.NATIVE_PRICE = Client.NATIVE_PRICE or await self.get_token_price(token=self.network.coin_symbol)
        if echo:
            logger.info(
                f'{self.log_info} | Balance - {float(balance.Ether)} {self.network.coin_symbol}'
                f'{f" {(Client.NATIVE_PRICE * float(balance.Ether)):2f}$" if get_usd_price else ""}',
            )
        return balance
