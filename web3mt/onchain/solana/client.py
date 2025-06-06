import asyncio

from solana.rpc.async_api import AsyncClient

from solana.rpc.providers.async_http import AsyncHTTPProvider
from solders.pubkey import Pubkey
from solders.rpc.requests import GetBalance, GetTransactionCount
from solders.rpc.responses import GetBalanceResp, GetTransactionCountResp, RpcConfirmedTransactionStatusWithSignature
from solders.keypair import Keypair

from web3db.core import DBHelper
from web3db.models import Profile

from web3mt.consts import env, DEV
from web3mt.onchain.solana.models.token import Token
from web3mt.utils.logger import my_logger

rpcs = [
    'https://api.mainnet-beta.solana.com',
    'https://grateful-jerrie-fast-mainnet.helius-rpc.com/'
]


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
            account: Keypair = None,
            rpc: str = rpcs[0],
            proxy: str = env.DEFAULT_PROXY
    ):
        self._rpc = rpc
        self.proxy = proxy
        self.account: Keypair = account or Keypair()

    def __str__(self):
        return self.log_info

    async def __aenter__(self):
        my_logger.info(f'{self.log_info} | Started')
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            my_logger.error(f'{self.log_info} | {exc_val}')
        else:
            my_logger.success(f'{self.log_info} | Tasks done')

    @property
    def rpc(self) -> str:
        return self._rpc

    @rpc.setter
    def rpc(self, rpc):
        self._rpc = rpc
        self._update_client()

    @property
    def proxy(self) -> str:
        return self._proxy

    @proxy.setter
    def proxy(self, proxy):
        self._proxy = proxy
        self._update_client()

    @property
    def account(self) -> Keypair:
        return self._account

    @account.setter
    def account(self, account: Keypair):
        self._account: Keypair = account
        self._update_log_info()

    def _update_log_info(self):
        self.log_info = f'BaseClient | {self._account.pubkey()}'

    def _update_client(self):
        self.client = AsyncClient(self._rpc or rpcs[0], proxy=self.proxy)

    async def my_balance(self, address: Pubkey | str = None):
        balance = await self.client.get_balance(address or self.account.pubkey())
        my_logger.info(f'{self} | {balance.value / 10 ** 9} SOL')

    async def get_transactions(self) -> list[RpcConfirmedTransactionStatusWithSignature]:
        resp = await self.client.get_signatures_for_address(self.account.pubkey())
        return resp.value

    async def get_onchain_token_info(self, token: Token = None):
        response = await self.client.get_account_info(token.address)
        if "value" in response and response["value"] is not None:
            data = response["value"]["data"]
            Token.decimals = int.from_bytes(bytes.fromhex(data[0][:2]), "little")


class Client(BaseClient):
    def __init__(self, profile: Profile, *args, **kwargs):
        self.profile = profile
        super().__init__(
            Keypair.from_base58_string(profile.solana_private),
            proxy=self.profile.proxy.proxy_string,
            *args, **kwargs
        )

    def _update_log_info(self):
        self.log_info = f'{self._account.pubkey()}'
        if self.profile:
            self.log_info = f"{self.profile.id} | {self.log_info}"


async def get_balance_batch(profiles: list[Profile], rpc: str = None):
    provider = AsyncHTTPProvider(rpc or rpcs[0])
    step = 1
    for batch in range(0, len(profiles), step):
        profiles_ = profiles[batch:batch + step]
        reqs = tuple(GetBalance(Keypair.from_base58_string(profile.solana_private).pubkey()) for profile in profiles_)
        parsers = (GetBalanceResp,) * len(profiles_)
        resps = await provider.make_batch_request(reqs, parsers)  # type: ignore
        for resp, profile in zip(resps, profiles_):
            my_logger.info(
                f'{profile.id} | {Keypair.from_base58_string(profile.solana_private).pubkey()} | {resp.value / 10 ** 9} SOL'
            )


async def main():
    db = DBHelper(env.LOCAL_CONNECTION_STRING)
    profiles = await db.get_all_from_table(Profile)
    await get_balance_batch(profiles)
    # await asyncio.gather(*[get_balance(profile) for profile in profiles])


if __name__ == "__main__":
    asyncio.run(main())
