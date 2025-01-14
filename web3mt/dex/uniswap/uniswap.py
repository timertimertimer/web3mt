import asyncio
import time
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import AsyncIterable
from web3db import Profile
from web3mt.dex.models import DEX, PriceImpactException
from web3mt.onchain.evm.client import Client
from web3mt.onchain.evm.models import *
from web3mt.onchain.evm.models import Sepolia
from web3mt.utils import FileManager, my_logger, CustomAsyncSession


class Contracts:
    def __init__(self, factory_address: str, quoter_address: str, router_address: str):
        self.factory = factory_address
        self.quoter = quoter_address
        self.router = router_address


class Fee(Enum):
    TIER_100 = 100
    TIER_500 = 500
    TIER_3000 = 3000
    TIER_10000 = 10000


ONE_HOUR = 10 * 60
ABI = FileManager.read_json(Path(__file__).parent / './abi.json')


class Uniswap(DEX):
    NAME = 'Uniswap'
    SLIPPAGE = Decimal('3')
    CONTRACTS = {
        Arbitrum: Contracts(
            factory_address='0x1F98431c8aD98523631AE4a59f267346ea31F984',
            quoter_address='0xb27308f9F90D607463bb33eA1BeBb41C27CE5AB6',
            router_address='0x68b3465833fb72A70ecDF485E0e4C7bD8665Fc45'
        ),
        Sepolia: Contracts(
            factory_address='0x0227628f3F023bb0B980b67D528571c95c6DaC1c',
            quoter_address='0xEd1f6473345F45b75F8179591dd5bA1888cf2FB3',
            router_address='0x3bFA4769FB09eefC5a80d6E87c3B9C650f7Ae48E'
        )
    }

    def __init__(self, client: Client = None, session: CustomAsyncSession = None, profile: Profile = None):
        self._weth_address = None
        super().__init__(session, client, profile)

    @property
    async def weth_address(self):
        if not self._weth_address:
            contract = self.client.w3.eth.contract(self.CONTRACTS[self.client.chain].quoter, abi=ABI['quoter'])
            self.weth_address = await contract.functions.WETH9().call()
        return self._weth_address

    @weth_address.setter
    def weth_address(self, address):
        self._weth_address = address

    async def get_weth_address(self, chain: Chain = None) -> str:
        return await self.weth_address

    async def swap(self, token_amount_in: TokenAmount, token_out: Token):
        is_native_token_in = token_amount_in.token.address == self.client.chain.native_token.address
        is_native_token_out = token_out.address == self.client.chain.native_token.address

        contract = self.client.w3.eth.contract(self.CONTRACTS[self.client.chain].router, abi=ABI['router'])
        if is_native_token_in or is_native_token_out:
            self.weth_address = await contract.functions.WETH9().call()

        async for fee in self.get_pool_fee(token_amount_in.token, token_out):
            token_amount_out = await self.quote(token_amount_in, token_out, fee)
            try:
                dex_slippage = await self.price_impact_defender(token_amount_in, token_amount_out)
                my_logger.debug(f'{self.client.log_info} | Found pool with fee {fee.value}')
                break
            except PriceImpactException as e:
                my_logger.warning(f'{self.client.log_info} | {e}')
        else:
            raise KeyError(f'No pool found for {token_amount_in.token} and {token_out}')
        token_amount_out.wei = int(token_amount_out.wei * (1 - ((self.SLIPPAGE - dex_slippage) / 100)))
        swap_args = (
            await self.weth_address if is_native_token_in else token_amount_in.token.address,
            await self.weth_address if is_native_token_out else token_amount_out.token.address,
            fee.value,
            str(self.client.account.address) if not is_native_token_out
            else '0x0000000000000000000000000000000000000002',
            token_amount_in.wei,
            token_amount_out.wei,
            0
        )
        swap_data = contract.encodeABI('exactInputSingle', args=[swap_args])
        data = [swap_data]
        if is_native_token_out:
            unwrap_args = token_amount_out.wei, str(self.client.account.address)
            unwrap_data = contract.encodeABI('unwrapWETH9', args=unwrap_args)
            data.append(unwrap_data)
            await self.client.approve(contract, token_amount_in)
        await self.client.tx(
            contract.address, f'Swap {token_amount_in} to {token_amount_out}',
            contract.encodeABI('multicall', args=[int(time.time()) + ONE_HOUR, data]),
            token_amount_in if is_native_token_in else TokenAmount(0, token=token_amount_in.token)
        )

    async def quote(self, token_amount_in: TokenAmount, token_out: Token, fee: Fee = Fee.TIER_100):
        contract = self.client.w3.eth.contract(self.CONTRACTS[self.client.chain].quoter, abi=ABI['quoter'])
        args = (
            token_amount_in.token.address if token_amount_in.token.address != self.client.chain.native_token.address
            else await self.weth_address,
            token_out.address if token_out.address != self.client.chain.native_token.address
            else await self.weth_address, fee.value, token_amount_in.wei, 0
        )
        res = await contract.functions.quoteExactInputSingle(*args).call()
        if token_out != self.client.chain.native_token:
            await token_out.get_token_info()
        token_amount_out = TokenAmount(res, True, token_out)
        return token_amount_out

    async def get_pool_fee(self, token_in: Token, token_out: Token) -> AsyncIterable[Fee]:
        contract = self.client.w3.eth.contract(self.CONTRACTS[self.client.chain].factory, abi=ABI['factory'])
        for fee in Fee:
            pool_address = await contract.functions.getPool(
                token_in.address if token_in.address != self.client.chain.native_token.address
                else await self.weth_address,
                token_out.address if token_out.address != self.client.chain.native_token.address else
                await self.weth_address,
                fee.value
            ).call()
            if pool_address != '0x0000000000000000000000000000000000000000':
                yield fee

    async def create_pool(self, token_in: Token, token_out: Token, fee: int = Fee.TIER_100):
        ...
