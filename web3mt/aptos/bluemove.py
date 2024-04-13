from web3db import Profile

from client import Client
from web3mt.utils import ProfileSession


class BlueMove(Client):
    BLUEMOVE_API_URL = 'https://aptos-mainnet-api.bluemove.net/api/'

    def __init__(self, profile: Profile, node_url: str = None):
        super().__init__(profile, node_url)
        self.session = ProfileSession(
            profile,
            headers={'Origin': 'https://bluemove.net', 'Referer': 'https://bluemove.net/'}
        )

    async def __aenter__(self):
        await self.login()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.session.close()
        await self.close()

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
