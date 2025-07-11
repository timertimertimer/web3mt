import asyncio
from decimal import Decimal
from json import JSONDecodeError
from typing import Optional

from httpx import AsyncClient, HTTPStatusError, LocalProtocolError
from monero.numbers import to_atomic

from web3mt.config import env
from web3mt.utils.logger import logger


class AsyncSession:
    def __init__(self, host: str, port: int):
        self.url = f"http://{host}:{port}/json_rpc"
        self.session = AsyncClient(
            headers={"Content-Type": "application/json"},
            timeout=30,
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
                logger.info(f"POST {self.session.base_url} {request_data=}")
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
    def __init__(self, host: str = env.monero_host, port: int = 18081):
        super().__init__(host, port)


class AsyncJSONRPCWallet(AsyncSession):
    default_priority: int = 2

    def __init__(self, host: str = "localhost", port: int = 18081):
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
        node_host: str = env.monero_host,
        node_port: int = 18081,
        wallet_host: str = "localhost",
        wallet_port: int = 18081,
    ):
        self.daemon = AsyncJSONRPCDaemon(node_host, node_port)
        self.wallet = AsyncJSONRPCWallet(wallet_host, wallet_port)

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.wallet.__aexit__(exc_type, exc_val, exc_tb)
        await self.daemon.__aexit__(exc_type, exc_val, exc_tb)


async def main():
    async with BaseClient() as client:
        node_version = await client.daemon.get_version()
        wallet_version = await client.wallet.get_version()
        logger.info(f"Node version: {node_version}")
        logger.info(f"Wallet version: {wallet_version}")
        accounts = await client.wallet.get_accounts()
        zero_address = await client.wallet.get_address()
        amount = to_atomic(Decimal(0.1))
        addresses = [
            "89eCJipw7t4HgeCBy9myphMJ48NXYLdCvRoTk72hrdfkFFUidbtYjtsKrhpmtPJ1xPf69iMoief6U9H3zLqbyrcND6x33c7",  # mexc
            "83GUuR77xrScJv1oHXJjTmcXBa15xeGkY5fb4nmBJ1hjj9NpBC4bFdWXhRqAAc4NUEgAsnwMu8bUd1ZAMymDNufjK9szVkk",  # kucoin
            "89WUjP2hfHzRaBArMMXgxQaYABfGexR5aQNaeouF8LJoGRoVuEi35dsZKNf9qEqkdB1DQj9nH68ufDUXYCAUqbJLLJgC1bN",  # htx
        ]
        tx = await client.wallet.transfer(
            [{"amount": amount, "address": address} for address in addresses],
            account_index=4,
        )
        return accounts

if __name__ == '__main__':
    asyncio.run(main())