from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from web3mt.config import env
from web3mt.models import Coin
from web3mt.utils import curl_cffiAsyncSession
from web3mt.utils import FileManager
from web3mt.utils.http_sessions import SessionConfig


class CoinGecko(curl_cffiAsyncSession):
    URL = 'https://api.coingecko.com/api/v3/'
    LOCAL_STORAGE = Path(__file__).parent / 'coins.json'

    def __new__(cls):
        if not hasattr(cls, 'instance'):
            cls._instance = object.__new__(cls)
        return cls._instance

    def __init__(self):
        super().__init__(
            env.default_proxy, SessionConfig('CoinGecko'),
            headers={'x-cg-demo-api-key': env.coingecko_api_key}
        )

    async def _get_coins_list(self, include_contracts_in_response: bool = True) -> list:
        if (
                FileManager.file_last_modification_time(self.LOCAL_STORAGE) <
                (datetime.now() - timedelta(weeks=1)).timestamp()
                or FileManager.file_data(self.LOCAL_STORAGE).st_size == 0
        ):
            _, data = await self.get(
                self.URL + 'coins/list',
                params={'include_platform': include_contracts_in_response}
            )
            await FileManager.write_async(self.LOCAL_STORAGE, data)
        else:
            data = FileManager.read_json(self.LOCAL_STORAGE)
        return data

    async def get_brief_coin_data(
            self, coin: Coin = Coin('ETH'), include_contracts_in_response: bool = True
    ) -> dict:
        """Returns id, symbol, name + contract addresses, if include_contracts_in_response=True"""
        for _coin in await self._get_coins_list(include_contracts_in_response):
            if _coin.get('symbol') == coin.symbol.lower() and _coin.get('name') == coin.name:
                return _coin

    async def _get_coin_data_by_id(self, coin_id: str = 'ethereum'):
        return (await self.get(self.URL + f'coins/{coin_id.lower()}'))[1]

    async def get_full_coin_data(self, coin: Coin = Coin('ETH')) -> dict:
        coin_id = (await self.get_brief_coin_data(coin, include_contracts_in_response=False))['id']
        return await self._get_coin_data_by_id(coin_id)

    async def get_coin_price(self, coin: str | Coin = 'ETH') -> Decimal:
        coin = Coin(coin) if isinstance(coin, str) else coin
        if coin.price:
            return coin.price
        coins_list = await self._get_coins_list()
        for coin_data in coins_list:
            if coin_data.get('symbol') == coin.symbol.lower():
                data = await self._get_coin_data_by_id(coin_data.get("id"))
                if 'market_data' in data:
                    token_info = data['market_data']
                    if token_info['current_price']:
                        coin.price = token_info['current_price']['usd']
                        break
        return coin.price


if __name__ == '__main__':
    print(id(CoinGecko()))
    print(id(CoinGecko()))
