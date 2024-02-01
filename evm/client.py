from aiohttp import ClientSession
from eth_account import Account
from web3 import Web3
from typing import Optional
from web3.eth import AsyncEth
from web3.exceptions import ABIFunctionNotFound
from web3.middleware import geth_poa_middleware

from models import TokenAmount
from models import Network
from logger import logger


class Client:
    default_abi = None

    def __init__(
            self,
            account: Account,
            network: Network
    ):
        self.account = account
        self.network = network
        self.w3 = Web3(Web3.AsyncHTTPProvider(
            endpoint_uri=self.network.rpc),
            modules={'eth': (AsyncEth,)},
            middlewares=[]
        )

    async def get_decimals(self, contract_address: str) -> int:
        try:
            return int(await (self.w3.eth.contract(
                address=Web3.to_checksum_address(contract_address),
                abi=self.default_abi
            )).functions.decimals().call())
        except ABIFunctionNotFound as e:
            return 0

    async def balance_of(self, contract_address: str, address: Optional[str] = None) -> TokenAmount:
        if not address:
            address = self.account.address
        contract = self.w3.eth.contract(address=Web3.to_checksum_address(contract_address), abi=self.default_abi)
        amount = await contract.functions.balanceOf(address).call()
        decimals = await self.get_decimals(contract_address=contract_address)
        return TokenAmount(
            amount=amount,
            decimals=decimals,
            wei=True
        )

    async def get_allowance(self, token_address: str, spender: str) -> TokenAmount:
        contract = self.w3.eth.contract(address=Web3.to_checksum_address(token_address), abi=self.default_abi)
        return TokenAmount(
            amount=await contract.functions.allowance(self.account.address, spender).call(),
            decimals=await self.get_decimals(contract_address=token_address),
            wei=True
        )

    async def check_balance_interface(self, token_address, min_value) -> bool:
        logger.info(f'{self.account.address[:6]} | balanceOf | check balance of {token_address}')
        balance = await self.balance_of(contract_address=token_address)
        decimal = await self.get_decimals(contract_address=token_address)
        if balance < min_value * 10 ** decimal:
            logger.error(f'{self.account.address[:6]} | balanceOf | not enough {token_address}')
            return False
        return True

    @staticmethod
    async def get_max_priority_fee_per_gas(w3: Web3, block: dict) -> int:
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
            increase_gas=1.,
            value=None,
            max_priority_fee_per_gas: Optional[int] = None,
            max_fee_per_gas: Optional[int] = None
    ):
        if not from_:
            from_ = self.account.address

        tx_params = {
            'chainId': self.network.chain_id,
            'nonce': await self.w3.eth.get_transaction_count(self.account.address),
            'from': Web3.to_checksum_address(from_),
            'to': Web3.to_checksum_address(to),
        }
        if data:
            tx_params['data'] = data

        if self.network.eip1559_tx:
            w3 = Web3(provider=Web3.HTTPProvider(endpoint_uri=self.network.rpc))
            w3.middleware_onion.inject(geth_poa_middleware, layer=0)

            last_block = w3.eth.get_block('latest')
            if not max_priority_fee_per_gas:
                # max_priority_fee_per_gas = await Client.get_max_priority_fee_per_gas(w3=w3, block=last_block)
                max_priority_fee_per_gas = await self.w3.eth.max_priority_fee
            if not max_fee_per_gas:
                base_fee = int(last_block['baseFeePerGas'] * increase_gas)
                max_fee_per_gas = base_fee + max_priority_fee_per_gas
            tx_params['maxPriorityFeePerGas'] = max_priority_fee_per_gas
            tx_params['maxFeePerGas'] = max_fee_per_gas

        else:
            tx_params['gasPrice'] = self.w3.eth.gas_price

        if value:
            tx_params['value'] = value

        try:
            tx_params['gas'] = int(await self.w3.eth.estimate_gas(tx_params) * increase_gas)
        except Exception as err:
            logger.error(f'{self.account.address[:6]} | Transaction failed | {err}')
            return
        sign = self.w3.eth.account.sign_transaction(tx_params, self.account.key.hex())
        try:
            tx_hash = await self.w3.eth.send_raw_transaction(sign.rawTransaction)
        except ValueError as e:
            logger.error(f'{self.account.address[:6]} | {e}')
            return
        logger.success(f'{self.account.address[:6]} | Transaction {tx_hash.hex()} sent')
        return tx_hash.hex()

    async def verif_tx(self, tx_hash) -> bool:
        try:
            data = await self.w3.eth.wait_for_transaction_receipt(tx_hash, timeout=200)
            if 'status' in data and data['status'] == 1:
                logger.success(f'{self.account.address[:6]} | transaction was successful: {tx_hash.hex()}')
                return True
            else:
                logger.error(f'{self.account.address[:6]} | transaction failed {data["transactionHash"].hex()}')
                return False
        except Exception as err:
            logger.error(f'{self.account.address[:6]} | unexpected error in <verif_tx> function: {err}')
            return False

    async def approve(self, token_address, spender, amount: Optional[TokenAmount] = None):
        contract = self.w3.eth.contract(
            address=Web3.to_checksum_address(token_address),
            abi=self.default_abi
        )
        return await self.send_transaction(
            to=token_address,
            data=contract.encodeABI('approve',
                                    args=(
                                        spender,
                                        amount.Wei
                                    ))
        )

    async def approve_interface(self, token_address: str, spender: str, amount: Optional[TokenAmount] = None) -> bool:
        decimals = await self.get_decimals(contract_address=token_address)
        balance = await self.balance_of(contract_address=token_address)

        if balance.Wei <= 0:
            logger.error(f'{self.account.address[:6]} | approve | zero balance')
            return False

        if not amount or amount.Wei > balance.Wei:
            amount = balance

        approved = await self.get_allowance(token_address=token_address, spender=spender)
        if amount.Wei <= approved.Wei:
            logger.success(f'{self.account.address[:6]} | approve | already approved')
            return True

        tx_hash = await self.approve(token_address=token_address, spender=spender, amount=amount)
        if not await self.verif_tx(tx_hash=tx_hash):
            logger.error(f'{self.account.address[:6]} | approve | {token_address} for spender {spender}')
            return False
        logger.success(f'{self.account.address[:6]} | approve | approved')
        return True

    async def get_eth_price(self, token='ETH'):
        token = token.upper()
        async with ClientSession() as session:
            response = await session.get(f'https://api.binance.com/api/v3/depth?limit=1&symbol={token}USDT')
            if response.status != 200:
                logger.info(f'code: {response.status} | json: {response.json()}')
                return None
            result_dict = await response.json()
            if 'asks' not in result_dict:
                logger.info(f'code: {response.status} | json: {response.json()}')
                return None
            return float(result_dict['asks'][0][0])

    async def get_native_balance(self, address: str = None) -> TokenAmount:
        balance = TokenAmount(
            amount=await self.w3.eth.get_balance(address or self.account.address),
            wei=True
        )
        logger.info(f'{address or self.account.address} | Balance - {float(balance.Ether)} {self.network.coin_symbol}')
        return balance
