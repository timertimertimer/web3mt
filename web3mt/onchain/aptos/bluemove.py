from web3db import Profile
from web3mt.utils import ProfileSession, my_logger
from web3mt.onchain.aptos.client import Client
from web3mt.onchain.aptos.models import TokenAmount
from web3mt.consts import Web3mtENV


class BlueMove(Client):
    BLUEMOVE_API_URL = 'https://aptos-mainnet-api.bluemove.net/api/'

    def __init__(
            self, profile: Profile, encryption_password: str = Web3mtENV.PASSPHRASE, node_url: str = Client.NODE_URL
    ):
        super().__init__(profile, encryption_password=encryption_password, node_url=node_url)
        self.session = ProfileSession(
            profile,
            headers={'Origin': 'https://bluemove.net', 'Referer': 'https://bluemove.net/'}
        )

    async def __aenter__(self):
        await self.login()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
        await super().__aexit__(exc_type, exc_val, exc_tb)

    async def get_message(self):
        response, data = await self.session.post(
            url=self.BLUEMOVE_API_URL + 'auth-signature/get-message',
            json={'publicKey': str(self.account_.public_key())}
        )
        return data['message']

    async def login(self):
        message = (
            f"APTOS\naddress: {str(self.account_.address())}\napplication: bluemove.net\nchainId: 1\n"
            f"message: Click to sign in and accept the BlueMove Terms of Service. "
            f"This request will not cost any gas fees.\nnonce: {await self.get_message()}"
        )
        response, data = await self.session.post(
            url=self.BLUEMOVE_API_URL + 'auth-signature/login',
            json={
                'signature': str(self.account_.sign(message.encode('utf-8'))),
                'publicKey': str(self.account_.public_key()),
                'message': message,
                'walletAddress': str(self.account_.address()),
                'deviceToken': None
            }
        )
        token = data['jwt']
        self.session.headers.update({'Authorization': f'Bearer {token}'})

    async def get_listed_nfts(self) -> list[dict]:
        response, data = await self.session.get(
            url=self.BLUEMOVE_API_URL + 'market-items',
            params={
                'filters[listed_address][$eq]': str(self.account_.address()),
                'filters[status][$eq]': 1,
                'populate[collection][fields][0]': 'name',
                'populate[collection][fields][1]': 'creator',
                'pagination[page]': 1,
                'pagination[pageSize]': 100
            }
        )
        return data['data']

    async def get_listing_info(self, item_id: int) -> dict:
        response, data = await self.client.get(
            url=self.BLUEMOVE_API_URL + f'market-items/{item_id}',
            params={'populate': '*'}
        )
        return data['attributes']

    async def batch_list_token_v2(self, storage_ids: list[str] | str, prices: list[float] | float) -> int | bool:
        if not storage_ids:
            my_logger.warning(f'{self.log_info} | Nothing to list. Storage ids list is empty')
            return False
        if isinstance(storage_ids, str):
            storage_ids = [storage_ids]
        if isinstance(prices, float):
            prices = [prices] * len(storage_ids)
        my_logger.info(f'{self.log_info} | Listing {storage_ids}')
        payload = self.PAYLOAD
        payload['function'] = (
            "0xd520d8669b0a3de23119898dcdff3e0a27910db247663646ad18cf16e44c6f5"
            "::coin_listing::batch_list_token_v2"
        )
        payload['type_arguments'] = ["0x1::object::ObjectCore", "0x1::aptos_coin::AptosCoin"]
        payload['arguments'] = [
            [{'inner': sid} for sid in storage_ids],
            '0xb3e77042cc302994d7ae913d04286f61ecd2dbc4a73f6c7dbcb4333f3524b9d7',
            [str(TokenAmount(price).wei) for price in prices]
        ]
        return await self.send_transaction(payload)

    async def edit_listing_price(self, token_name: str, listing_id: str, price: float) -> int | bool:
        my_logger.info(f'{self.log_info} | Editing listing price {token_name}')
        payload = self.PAYLOAD.copy()
        payload['function'] = (
            "0xd520d8669b0a3de23119898dcdff3e0a27910db247663646ad18cf16e44c6f5"
            "::coin_listing::edit_fixed_price"
        )
        payload['type_arguments'] = ["0x1::aptos_coin::AptosCoin"]
        payload['arguments'] = [
            '0xb3e77042cc302994d7ae913d04286f61ecd2dbc4a73f6c7dbcb4333f3524b9d7',
            listing_id, str(TokenAmount(price).wei)
        ]
        return await self.send_transaction(payload)
