import asyncio
import random
from decimal import Decimal

from web3db import Profile

from web3mt.dex.bridges.base import BridgeInfo
from web3mt.dex.bridges.bungee import Bungee
from web3mt.dex.bridges.relay import Relay
from web3mt.dex.bridges.routernitro import RouterNitro
from web3mt.dex.models import DEX
from web3mt.onchain.evm.client import *
from web3mt.onchain.evm.models import *
from web3mt.local_db.core import DBHelper
from web3mt.cex import OKX
from web3mt.utils import my_logger, sleep, format_number, CustomAsyncSession
from eth_utils import to_checksum_address


class Warmup(DEX):
    """
    With bridges functions are using FULL balance OR random range from zero to full balance
    Percentage takes from full balance
    """

    CONTRACTS = {
        'Blur': '0x0000000000a39bb272e79075ade125fd351887ac'
    }

    def __init__(self, session: CustomAsyncSession = None, client: Client = None, profile: Profile = None):
        super().__init__(session=session, client=client, profile=profile)
        self.okx = OKX()
        self.total_fee = Decimal(0)
        TransactionParameters.gas_limit_multiplier = 1.1
        TransactionParameters.gas_price_multiplier = 1.2
        Ethereum.max_gwei = 3

    async def __aenter__(self):
        my_logger.info(f'{self} | Started')
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        my_logger.success(f'{self} | Warmed for {self.total_fee:.2f}$, GG')

    async def start_eth_warmup(self) -> Decimal | None:
        cheap_chains = [Base, Optimism]
        random_cheap_chain_1: Chain = random.choice(cheap_chains)
        cheap_chains.remove(random_cheap_chain_1)
        random_cheap_chain_2: Chain = random.choice(cheap_chains)
        paths = {
            f'From OKX to Ethereum -> Bridge full balance to {random_cheap_chain_1} -> Withdraw full balance '
            f'from {random_cheap_chain_1} to OKX. ~2.5$': (
                (
                    self.okx_withdraw, (
                        TokenAmount(
                            random.randrange(TokenAmount(0.01).wei, TokenAmount(0.011).wei), True, Ethereum.native_token
                        ),
                    )
                ),
                (
                    self.execute_bridge_with_chain_update,
                    Ethereum.native_token, random_cheap_chain_1.native_token, True, True
                )
            ),
            f'From OKX to {random_cheap_chain_1} -> Bridge full balance to Ethereum -> Bridge full balance from '
            f'Ethereum to {random_cheap_chain_2} -> Withdraw full balance from {random_cheap_chain_2} to OKX. ~1$': (
                (
                    self.okx_withdraw, (
                        TokenAmount(
                            random.randrange(TokenAmount(0.002).wei, TokenAmount(0.005).wei),
                            True,
                            random_cheap_chain_1.native_token
                        ),
                    )
                ),
                (
                    self.execute_bridge_with_chain_update, (
                        random_cheap_chain_1.native_token, Ethereum.native_token, True, True
                    )
                ),
                (
                    self.execute_bridge_with_chain_update, (
                        Ethereum.native_token, random_cheap_chain_2.native_token, True, True
                    )
                )
            ),
            f'From OKX to {random_cheap_chain_1} -> Bridge full balance to Ethereum -> Withdraw full balance from '
            f'Ethereum to OKX. <1$': (
                (
                    self.okx_withdraw, (
                        TokenAmount(
                            random.randrange(TokenAmount(0.002).wei, TokenAmount(0.005).wei),
                            True,
                            random_cheap_chain_1.native_token
                        ),
                    )
                ),
                (
                    self.execute_bridge_with_chain_update,
                    (random_cheap_chain_1.native_token, Ethereum.native_token, True, True)
                )

            )
        }
        for i in range(5):
            path_log, funcs_and_params = random.choice(list(paths.items()))
            my_logger.info(f'{self.client.account.address} | {path_log}')
            for k, func_and_params in enumerate(funcs_and_params, start=1):
                func = func_and_params[0]
                params = func_and_params[1]
                my_logger.info(f'{self.client.account.address} | {k}. {func.__name__}')
                fee = await func(*params)
                if not fee:
                    break
                self.total_fee += fee
            else:
                self.total_fee += await self.deposit_to_okx()
                my_logger.success(f'{self.client.account.address} | Warmed for {self.total_fee:.2f}$, GG')
                return self.total_fee
        my_logger.warning(f'Tried 5 times. Sorry, unluck :(')

    async def deposit_to_okx(self):
        return await self.client.tx(
            self.client.profile.okx_evm_address, f'Deposit to OKX', use_full_balance=True,
            return_fee_in_usd=True
        )

    async def okx_withdraw(
            self,
            token_amount: TokenAmount,
            max_fee_in_usd: int | float | str | Decimal = Decimal('0.5')
    ) -> Decimal | None:
        if not token_amount.token.price:
            await self.okx.get_coin_price(token_amount.token)
        while True:
            okx_balance = (await self.okx.get_funding_balance(coins=token_amount.token))[0]
            if okx_balance > token_amount:
                await self.okx.collect_on_funding_master()
                break
            my_logger.warning(
                f'Not enough balance on OKX. Balance - {okx_balance}, withdraw amount - {token_amount}. Waiting...'
            )
            await sleep(5, 10, log_info=str(self))
        self.client.chain = token_amount.token.chain
        evm_balance = await self.client.balance_of(token=token_amount.token)
        fee_in_usd = await self.okx.withdraw(self.client.account.address, token_amount, max_fee_in_usd)
        if not fee_in_usd:
            return
        await self.wait_for_chain_arrival(evm_balance, token_amount)
        return fee_in_usd

    async def execute_bridge_with_chain_update(
            self,
            token_amount_in: TokenAmount,
            token_out: Token,
            wait_for_arrival: bool = False
    ) -> Decimal | None:
        self.client.chain = token_out.chain
        destination_token_balance_before_bridge = await self.client.balance_of(token=token_out)
        self.client.chain = token_amount_in.token.chain
        bridge_info = await self.execute_bridge(token_amount_in, token_out)
        if not bridge_info:
            return
        if wait_for_arrival:
            await self.wait_for_chain_arrival(
                destination_token_balance_before_bridge, bridge_info.token_amount_out - bridge_info.bridge_fee
            )
        self.client.chain = token_out.chain
        return bridge_info.bridge_fee.amount_in_usd

    async def wait_for_chain_arrival(
            self, before_balance_amount: TokenAmount, destination_token_amount: TokenAmount
    ) -> bool:
        self.client.chain = before_balance_amount.token.chain
        my_logger.info(f'{self.client} | Waiting for +{destination_token_amount}')
        while True:
            after_balance_amount = await self.client.balance_of(token=before_balance_amount.token)
            if after_balance_amount * 1.01 > before_balance_amount + destination_token_amount:
                my_logger.debug(
                    f'{self.client} | +{destination_token_amount}. Current balance - {after_balance_amount}'
                )
                return True
            await sleep(5, 10, log_info=str(self))

    async def execute_bridge(self, token_amount_in: TokenAmount, token_out: Token) -> BridgeInfo | None:
        token_amount_in.token.chain.eip1559_tx = False
        if not token_amount_in.token.price:
            await token_amount_in.token.update_price()
        if not token_out.price:
            await token_out.update_price()
        self.client.chain = token_amount_in.token.chain
        balance: TokenAmount = await self.client.balance_of(token=token_amount_in.token)
        my_logger.info(f'{self.client} | Balance: {balance}')
        user = recipient = self.client.account.address
        if balance < token_amount_in:
            my_logger.warning(
                f'{self.client} | Not enough balance to bridge {token_amount_in}. Balance - {balance}'
            )
            return None
        my_logger.info(
            f'{self.client} | Trying to bridge {token_amount_in} '
            f'from {token_amount_in.token.chain} to {token_out.chain}...'
        )
        bridges = {
            'Relay bridge': Relay(client=self.client).bridge,
            'Router bridge': RouterNitro(client=self.client).bridge,
            'Bungee refuel': Bungee(client=self.client).refuel
        }
        bridges_info = await asyncio.gather(*[
            func(BridgeInfo(
                name=name, user=user, recipient=recipient, log_info=self.client.log_info,
                token_amount_in=token_amount_in, token_out=token_out,
            ))
            for name, func in bridges.items()
        ])
        bridges_info = [el for el in bridges_info if el]
        if not bridges_info:
            return

        cheapest_bridge: BridgeInfo = min(bridges_info, key=lambda x: x.bridge_fee)
        my_logger.info(f'Cheapest bridge - {cheapest_bridge.name}')
        my_logger.info(cheapest_bridge)
        if cheapest_bridge:
            await self.client.tx_with_params(
                name=f'Bridge from {token_amount_in.token.chain} to {token_out.chain} with {cheapest_bridge.name}',
                tx_params=cheapest_bridge.tx_params
            )
        return cheapest_bridge

    async def blur_deposit(self, token_amount_in: TokenAmount):
        self.client.chain = Ethereum
        balance = await self.client.balance_of()
        if balance < token_amount_in:
            my_logger.warning(
                f'{self.client} | Not enough balance to deposit {token_amount_in} to Blur. Balance - {balance}'
            )
            return None
        contract = self.client.w3.eth.contract(
            to_checksum_address(self.CONTRACTS['Blur']), abi=DefaultABIs.WETH
        )
        return await self.client.tx(
            contract.address, 'Blur deposit', contract.encodeABI('deposit'),
            value=token_amount_in
        )

    async def blur_withdraw(self, token_amount_out: TokenAmount):
        self.client.chain = Ethereum
        balance = await self.client.balance_of(token=Token(chain=Ethereum, address=self.CONTRACTS['Blur']))
        if balance < token_amount_out:
            my_logger.warning(
                f'{self.client} | Not enough balance to withdraw {token_amount_out} from Blur. Balance - {balance}'
            )
            return None
        contract = self.client.w3.eth.contract(
            to_checksum_address(self.CONTRACTS['Blur']), abi=DefaultABIs.WETH
        )
        return await self.client.tx(
            contract.address, 'Blur withdraw', contract.encodeABI('withdraw', args=[token_amount_out.wei]),
        )


async def start(profile: Profile) -> Decimal | None:
    async with Warmup(profile=profile) as wu:
        try:
            return await wu.start_eth_warmup()
        except KeyboardInterrupt:
            return wu.total_fee


async def bridge(profile: Profile):
    async with Warmup(profile=profile) as wu:
        await wu.execute_bridge_with_chain_update(Optimism.native_token, Ethereum.native_token, True)


async def check_nonce(profile: Profile) -> Profile | None:
    client = Client(profile=profile)
    nonce = await client.nonce()
    if nonce == 0:
        return profile


async def get_profiles_without_nonce(profiles: list[Profile]) -> list[Profile]:
    tasks = []
    for profile in profiles:
        tasks.append(asyncio.create_task(check_nonce(profile)))
    return [profile for profile in await asyncio.gather(*tasks) if profile]


async def main():
    db = DBHelper()
    profiles: list[Profile] = await db.get_all_from_table(Profile)
    fees = await asyncio.gather(*[asyncio.create_task(test(profile)) for profile in profiles[:3]])
    my_logger.success(f'Total fee - {format_number(sum([fee or 0 for fee in fees]))}$')


if __name__ == '__main__':
    asyncio.run(main())
