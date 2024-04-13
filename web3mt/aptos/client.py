import os

from web3db.utils import decrypt
from web3db.models import Profile
from aptos_sdk.account import Account
from aptos_sdk.async_client import RestClient

from web3mt.utils import read_txt, ProfileSession, logger


class Client(RestClient):
    NODE_URL = "https://fullnode.mainnet.aptoslabs.com/v1"
    GRAPHQL_URL = "https://indexer.mainnet.aptoslabs.com/v1/graphql"
    PAYLOAD = {
        "function": "",
        "type_arguments": [],
        "arguments": [],
        "type": "entry_function_payload"
    }

    def __init__(self, profile: Profile = None, private: str = None, node_url: str = None):
        super().__init__(node_url or self.NODE_URL)
        self.profile = profile
        self.account_ = Account.load_key(
            decrypt(profile.aptos_private, os.getenv('PASSPHRASE')) if profile else private)

    async def send_transaction(self, payload: dict) -> int:
        sender = self.account_.address()
        sequence = await self.account_sequence_number(sender)
        while True:
            try:
                txn_hash = await self.submit_transaction(self.account_, payload)
                logger.success(
                    f'{f"{self.profile.id} | " if self.profile else ""}{str(self.account_.address())} | '
                    f'Sent transaction {txn_hash}'
                )
                return sequence
            except Exception as e:
                if "Transaction already in mempool with a different payload" in str(
                        e) or "SEQUENCE_NUMBER_TOO_OLD" in str(e):
                    sequence += 1
                    continue
                logger.error(
                    f'{f"{self.profile.id} | " if self.profile else ""}{str(self.account_.address())[:6]} | {e}'
                )
                return False

    async def v2_token_data(self, collection_id: str) -> list:
        query = read_txt('v2_token.graphql')
        variables = {'owner_address': str(self.account_.address()), 'collection_id': collection_id}
        async with ProfileSession(self.profile) as session:
            response, data = await session.request(
                method='POST',
                url=self.GRAPHQL_URL,
                json={'query': query, 'variables': variables}
            )
            return data['data']['current_token_ownerships_v2']

    async def v1_token_data(self, token_data_id_hash: str, requests_echo: bool = True) -> list:
        query = read_txt('v1_token.graphql')
        variables = {'owner_address': str(self.account_.address()), 'token_data_id_hash': token_data_id_hash}
        async with ProfileSession(self.profile) as session:
            response, data = await session.request(
                method='POST',
                url=self.GRAPHQL_URL,
                json={'query': query, 'variables': variables}
            )
            return data
