import os

from aptos_sdk.account import Account
from aptos_sdk.async_client import RestClient, ResourceNotFound
from web3db.models import Profile
from web3db.utils import decrypt

from logger import logger
from utils import read_txt, Z8, ProfileSession


class AptosClient(RestClient):
    NODE_URL = "https://fullnode.mainnet.aptoslabs.com/v1"
    GRAPHQL_URL = "https://indexer.mainnet.aptoslabs.com/v1/graphql"

    def __init__(self, profile: Profile, node_url: str = None):
        super().__init__(node_url or self.NODE_URL)
        self.profile = profile
        self.account_ = Account.load_key(decrypt(profile.aptos_private, os.getenv('PASSPHRASE')))

    async def send_transaction(self, payload: dict) -> int:
        sender = self.account_.address()
        sequence = await self.account_sequence_number(sender)
        while True:
            try:
                txn_hash = await self.submit_transaction(self.account_, payload)
                logger.success(f"{str(self.account_.address())} | Sent transaction {txn_hash}", id=self.profile.id)
                return sequence
            except Exception as e:
                if "Transaction already in mempool with a different payload" in str(
                        e) or "SEQUENCE_NUMBER_TOO_OLD" in str(e):
                    sequence += 1
                    continue
                logger.error(f"{str(self.account_.address())[:6]} | {e}", id=self.profile.id)
                return False

    async def balance(self, ledger_version: int = None) -> float:
        try:
            balance = await super().account_balance(self.account_.address()) / Z8
            logger.info(f'{str(self.account_.address())} | {balance} APT', id=self.profile.id)
            return balance
        except ResourceNotFound:
            return 0

    async def v2_token_data(self, collection_id: str) -> list:
        query = read_txt('v2_token.graphql')
        variables = {'owner_address': str(self.account_.address()), 'collection_id': collection_id}
        async with ProfileSession(self.profile) as session:
            response, data = await session.request(
                method='POST',
                url=self.GRAPHQL_URL,
                json_={'query': query, 'variables': variables}
            )
            return data['data']['current_token_ownerships_v2']

    async def v1_token_data(self, token_data_id_hash: str, requests_echo: bool = True) -> list:
        query = read_txt('v1_token.graphql')
        variables = {'owner_address': str(self.account_.address()), 'token_data_id_hash': token_data_id_hash}
        async with ProfileSession(self.profile) as session:
            response, data = await session.request(
                method='POST',
                url=self.GRAPHQL_URL,
                json={'query': query, 'variables': variables},
                echo=requests_echo
            )
            return data
