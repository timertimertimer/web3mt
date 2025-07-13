from json import JSONDecodeError
from typing import Optional

from httpx import AsyncClient, HTTPStatusError, LocalProtocolError, BasicAuth

from web3mt.config import env
from web3mt.utils.logger import logger


class AsyncSession:
    def __init__(
        self,
        host: str,
        port: int,
        login: Optional[str] = None,
        password: Optional[str] = None,
    ):
        self.url = f"http://{host}:{port}/json_rpc"
        self.session = AsyncClient(
            headers={"Content-Type": "application/json"},
            timeout=30,
            auth=BasicAuth(login or "", password or ""),
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.session.aclose()

    async def make_request(
        self,
        rpc_method: str,
        params: dict = None,
    ):
        response = None
        data = None
        request_data = {
            "jsonrpc": "2.0",
            "id": 0,
            "method": rpc_method,
            "params": params or {},
        }
        for i in range(env.retry_count):
            try:
                response = await self.session.post(url=self.url, json=request_data)
                logger.info(f"POST {self.url} {request_data=}")
                response.raise_for_status()
            except (HTTPStatusError, LocalProtocolError) as e:
                if response:
                    try:
                        data = response.json()
                    except JSONDecodeError:
                        data = response.text
                    status_code = e.response.status_code
                    reason_phrase = e.response.reason_phrase
                    logger.warning(
                        f"status: {status_code}, reason: {reason_phrase}, data: {data}"
                    )
                    return data
            except Exception as e:
                logger.error(e)
                raise e
            return response.json()["result"]
        logger.warning(
            f'Tried to send {request_data=} to "{self.session.base_url}" {env.retry_count} times. Stopping'
        )
        return data["result"]

    async def get_version(self):
        return await self.make_request("get_version")


class AsyncJSONRPCDaemon(AsyncSession):
    def __init__(
        self,
        host: str = env.monero_node_rpc_host,
        port: int = 18081,
        login: str = None,
        password: str = None,
    ):
        super().__init__(host, port, login, password)


class AsyncJSONRPCWallet(AsyncSession):
    default_priority: int = 2

    def __init__(
        self,
        host: str = "localhost",
        port: int = 18081,
    ):
        super().__init__(host, port)

    async def get_accounts(self):
        return await self.make_request("get_accounts")

    async def get_address(
        self, account_index: int = 0, address_index: Optional[list[int]] = None
    ):
        return await self.make_request(
            "get_address",
            params={"account_index": account_index, "address_index": address_index},
        )

    async def sweep_all(
        self,
        address: str,
        account_index: int,
        subaddr_indices: Optional[list[int]] = None,
        subaddr_indices_all: bool = False,
        priority: int = default_priority,
    ):
        return await self.make_request(
            "sweep_all",
            params={
                "address": address,
                "account_index": account_index,
                "subaddr_indices": subaddr_indices,
                "subaddr_indices_all": subaddr_indices_all,
                "priority": priority,
            },
        )

    async def transfer(
        self,
        destinations: list[dict[int, str]],
        account_index: Optional[int] = None,
    ):
        return await self.make_request(
            "transfer",
            params={"destinations": destinations, "account_index": account_index},
        )


class BaseClient:
    def __init__(
        self,
        node_host: str = env.monero_node_rpc_host,
        node_port: int = 18081,
        wallet_host: str = "localhost",
        wallet_port: int = 18088,
        wallet_login: Optional[str] = env.monero_wallet_rpc_login,
        wallet_password: Optional[str] = env.monero_wallet_rpc_password,
    ):
        self.daemon = AsyncJSONRPCDaemon(node_host, node_port)
        self.wallet = AsyncJSONRPCWallet(
            wallet_host, wallet_port, wallet_login, wallet_password
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.wallet.__aexit__(exc_type, exc_val, exc_tb)
        await self.daemon.__aexit__(exc_type, exc_val, exc_tb)

    async def transfer(
        self,
        destinations: list[dict[int, str]],
        account_index: Optional[int] = None,
    ):
        data = await self.wallet.transfer(destinations, account_index)
        logger.debug(f"Transfered {data}")
        return data

    async def collect_on_primary_account(self):
        accounts = await self.wallet.get_accounts()
        subaddress_accounts = accounts["subaddress_accounts"]
        zero_address = subaddress_accounts[0]['base_address']
        for account in subaddress_accounts[1:]:
            if account["unlocked_balance"] > 0:
                tx = await self.wallet.sweep_all(
                    address=zero_address,
                    account_index=account['account_index'],
                )
