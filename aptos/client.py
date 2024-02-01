from aiohttp import ClientSession
from aptos_sdk.account import Account
from aptos_sdk.async_client import RestClient, ResourceNotFound

from logger import logger
from utils import read_txt, Z8


class AptosClient(RestClient):
    NODE_URL = "https://fullnode.mainnet.aptoslabs.com/v1"
    GRAPHQL_URL = "https://indexer.mainnet.aptoslabs.com/v1/graphql"

    def __init__(self, private_key: str, node_url: str = None):
        super().__init__(node_url or self.NODE_URL)
        self.account_ = Account.load_key(private_key)

    async def send_transaction(self, payload: dict) -> int:
        sender = self.account_.address()
        sequence = await self.account_sequence_number(sender)
        while True:
            try:
                txn_hash = await self.submit_transaction(self.account_, payload)
                logger.success(f"{str(self.account_.address())[:6]} | Sent transaction {txn_hash}")
                return sequence
            except Exception as e:
                if "Transaction already in mempool with a different payload" in str(
                        e) or "SEQUENCE_NUMBER_TOO_OLD" in str(e):
                    sequence += 1
                    continue
                logger.error(f"{str(self.account_.address())[:6]} | {e}")
                return False

    async def balance(self, ledger_version: int = None) -> float:
        try:
            balance = await super().account_balance(self.account_.address()) / Z8
            logger.info(f'{str(self.account_.address())[:6]} | {balance} APT')
            return balance
        except ResourceNotFound:
            return 0

    async def get_storage_ids(self, collection_id: str) -> list:
        query = read_txt('query.txt')

        variables = {'owner_address': str(self.account_.address()), 'collection_id': collection_id}

        while True:
            async with ClientSession() as session:
                resp = await session.post(self.GRAPHQL_URL, json={'query': query, 'variables': variables})
                data = await resp.json()
                if 'errors' not in data:
                    break
                logger.info(data['errors'])

        return data['data']['current_token_ownerships_v2']
