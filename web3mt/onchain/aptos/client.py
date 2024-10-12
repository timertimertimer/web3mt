from web3db import LocalProfile
from web3db.utils import decrypt
from aptos_sdk.account import Account
from aptos_sdk.async_client import RestClient, ResourceNotFound
from pathlib import Path

from web3mt.onchain.aptos.models import Token, NFT, TokenAmount
from web3mt.consts import Web3mtENV
from web3mt.utils import ProfileSession, my_logger, FileManager
from web3mt.utils.custom_sessions import SessionConfig


class Client(RestClient):
    NODE_URL = "https://fullnode.mainnet.aptoslabs.com/v1"
    GRAPHQL_URL = "https://indexer.mainnet.aptoslabs.com/v1/graphql"
    PAYLOAD = {
        "function": "",
        "type_arguments": [],
        "arguments": [],
        "type": "entry_function_payload"

    }
    _queries_folder = Path(__file__).parent / 'queries'

    def __init__(
            self,
            profile: LocalProfile = None,
            encryption_password: str = Web3mtENV.PASSPHRASE,
            private: str = None,
            node_url: str = NODE_URL
    ):
        super().__init__(node_url)
        self.profile = profile
        if private:
            self.account_ = Account.load_key(private)
        elif self.profile:
            if self.profile.aptos_private.startswith('-----BEGIN PGP MESSAGE-----'):
                self.account_: Account = Account.load_key(decrypt(self.profile.aptos_private, encryption_password))
            elif self.profile.aptos_private.startswith('0x'):
                self.account_: Account = Account.load_key(self.profile.aptos_private)
        else:
            self.account_: Account = Account.generate()
        self.session = ProfileSession(self.profile, SessionConfig())
        self.log_info = f'{f"{self.profile.id} | " if self.profile else ""}{str(self.account_.address())}'

    async def __aenter__(self):
        my_logger.success(f'{self.log_info} | Started')
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        my_logger.error(f'{self.log_info} | {exc_val}') if exc_type else my_logger.success(f'{self.log_info} | Tasks done')
        await self.session.close()

    async def balance(self, echo: bool = False):
        try:
            balance = TokenAmount(await self.account_balance(self.account_.address()), wei=True)
            if echo:
                my_logger.info(f'{self.log_info} | Balance: {balance}')
            return balance
        except ResourceNotFound:
            return TokenAmount()

    async def send_transaction(self, payload: dict) -> int | bool:
        sender = self.account_.address()
        sequence = await self.account_sequence_number(sender)
        while True:
            try:
                txn_hash = await self.submit_transaction(self.account_, payload)
                my_logger.success(f'{self.log_info} | Sent transaction {txn_hash}')
                return sequence
            except Exception as e:
                if (
                        "Transaction already in mempool with a different payload" in str(e)
                        or "SEQUENCE_NUMBER_TOO_OLD" in str(e)
                ):
                    sequence += 1
                    continue
                my_logger.error(f'{self.log_info} | {e}')
                return False

    async def verify_transaction(self, tx_hash: str, tx_name: str) -> bool:
        while True:
            try:
                data = await self.wait_for_transaction(tx_hash)
                if 'status' in data and data['status'] == 1:
                    my_logger.info(f'{self.log_info} | Transaction {tx_name} ({tx_hash}) was successful')
                    return True
                else:
                    my_logger.error(
                        f'{self.log_info} | Transaction {tx_name} ({tx_hash}) failed: {data["transactionHash"].hex()}'
                    )
                    return False
            except Exception as err:
                my_logger.warning(f'{self.log_info} | Transaction {tx_name} ({tx_hash}) failed: {err}')
                return False

    async def nfts_data(self, limit: int = None, offset: int = None) -> list[NFT]:
        query = await FileManager.read_txt_async(self._queries_folder / 'nfts_data.graphql')
        variables = {'owner_address': str(self.account_.address()), 'limit': limit, 'offset': offset}
        response, data = await self.session.post(url=self.GRAPHQL_URL, json={'query': query, 'variables': variables})
        assets = data['data']['current_token_ownerships_v2']
        nfts = []
        for nft in assets:
            nfts.append(NFT(**nft['current_token_data'], amount=nft['amount'], storage_id=nft['storage_id']))
        return nfts

    async def tokens_data(self, limit: int = None, offset: int = None) -> list[TokenAmount]:
        query = await FileManager.read_txt_async(self._queries_folder / 'tokens_data.graphql')
        variables = {'owner_address': str(self.account_.address()), 'limit': limit, 'offset': offset}
        response, data = await self.session.post(url=self.GRAPHQL_URL, json={'query': query, 'variables': variables})
        assets = data['data']['current_fungible_asset_balances']
        return [
            TokenAmount(amount=token['amount'], wei=True, token=Token(**token['metadata']))
            for token in assets
        ]

