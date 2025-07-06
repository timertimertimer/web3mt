import asyncio
import json
import pickle
import random
import re
import uuid
from datetime import datetime
from random import choice
from bs4 import BeautifulSoup
from pathlib import Path
from examples.offchain.ozon.data import proxies, parse_cookies
from web3mt.utils import curl_cffiAsyncSession, logger
from web3mt.utils.http_sessions import SessionConfig


def save_cookies(cookies, file_path: Path):
    file_path.write_bytes(pickle.dumps(cookies))


def load_cookies(file_path: Path):
    return pickle.loads(file_path.read_bytes()) if file_path.exists() else {}


some_products = {
    999665586,  # прокладки
    1625011281  # капибара
}
buy_products = {
    1720324111,  # часы
    1675710192  # вылесос
}
banks = [
    'bank100000000004',
    'bank110000000005',
    'bank100000000008',
    'bank100000000273',
    'bank100000000111'
]
ts = 1730908800 - 10


class Ozon(curl_cffiAsyncSession):
    DEFAULT_HEADERS = {
        'Accept': '*/*',
        'Accept-Language': 'ru',
        'Accept-Encoding': 'gzip, deflate, br',
        'Content-Type': 'application/json',
        'Connection': 'keep-alive',
        'Host': 'api.ozon.ru',
        'x-o3-fp': '0.624a0aa1dd53ae5f',
        'x-o3-app-name': 'ozonapp_ios',
        'x-o3-app-version': '17.40.1(876)',
        'x-o3-device-type': 'mobile',
        'x-o3-sample-trace': 'false',
        'User-Agent': 'OzonStore/876',
    }
    URL = 'https://api.ozon.ru'

    def __init__(self, account_data: tuple[Path, str]):
        self.file_path, proxy = account_data
        super().__init__(proxy=proxy,
                         config=SessionConfig(sleep_after_request=False, sleep_range=(1, 3), requests_echo=True))
        # self.cookies.jar._cookies.update(load_cookies(self.file_path.with_suffix('.pkl')))
        self.cookies.update(parse_cookies(self.file_path))
        self.count = 0
        self.device_id = str(uuid.uuid4()).upper()
        self.DEVICE_DATA = choice([
            {
                "biometryType": "touchId", "os": "iOS", "version": "16.7.10", "hasBiometrics": True,
                "model": "iPhone10,4", "vendor": "Apple"
            },
            {
                "biometryType": "faceId",
                "os": "iOS",
                "version": "15.6.2",
                "hasBiometrics": True,
                "model": "iPhone12,3",
                "vendor": "Apple",
            },
            {
                "biometryType": "none",
                "os": "Android",
                "version": "13.5.7",
                "hasBiometrics": False,
                "model": "Pixel6",
                "vendor": "Google",
            },
            {
                "biometryType": "irisScanner",
                "os": "HarmonyOS",
                "version": "17.0.3",
                "hasBiometrics": True,
                "model": "Huawei P50",
                "vendor": "Huawei"
            },
            {
                "biometryType": "touchId",
                "os": "iOS",
                "version": "16.7.10",
                "hasBiometrics": True,
                "model": "iPhone14,6",
                "vendor": "Apple",
            }
        ]) | {'deviceId': self.device_id}

    async def start(self):

        # update_local_data = False
        # while True:
        #     try:
        #         await self.current_location()
        #         await self.get_user()
        #         if update_local_data:
        #             save_cookies(self.cookies.jar._cookies, self.file_path.with_suffix('.pkl'))
        #         break
        #     except Exception as e:
        #         logger.warning(f'{self.config.log_info} | {e}')
        #         await self.generate_cookies()
        #         update_local_data = True

        await self.generate_cookies()
        while True:
            try:
                await self.current_location()
                await self.get_user()
                await self.try_buy()
            except Exception as e:
                logger.warning(f'{self.config.log_info} | {e}')

    async def generate_cookies(self):
        timestamp = datetime.utcnow().isoformat(timespec='milliseconds') + 'Z'
        data = [
            {"sdk": {
                "name": "sentry.cocoa", "version": "8.30.0",
                "packages": {"name": r"carthage:getsentry/sentry.cocoa", "version": "8.30.0"}
            },
                "sent_at": timestamp
            },
            {"type": "session", "length": 291},
            {
                "errors": 0, "status": "ok", "started": timestamp,
                "did": "919F0E0C-F736-496B-9470-CDA002594D3A", "sid": str(uuid.uuid4()).upper(),
                "init": True,
                "timestamp": timestamp,
                "attrs": {"release": "ru.ozon.OzonStore@17.40.1+876", "environment": "production"}, "seq": 1
            }
        ]
        _, data = await self.post(
            f'https://sentry.ozon.ru/api/442/envelope/',
            headers={
                'Host': 'sentry.ozon.ru', 'Content-Type': 'application/x-sentry-envelope',
                'Accept-Encoding': 'gzip, deflate, br', 'User-Agent': 'sentry.cocoa/8.30.0', 'Accept-Language': 'ru',
                'X-Sentry-Auth': 'Sentry sentry_version=7,sentry_client=sentry.cocoa/8.30.0,sentry_key=2336f050d6844d91a2d2fa6098263806',
                'Accept': '*/*', 'Connection': 'keep-alive'
            }, data='\n'.join(json.dumps(el).replace(' ', '') for el in data)
        )
        return data

    async def current_location(self):
        _, data = await self.get(
            f'{self.URL}/composer-api.bx/_action/currentLocation', params={'ignoreclient': True}
        )
        logger.debug(data)
        return data

    async def get_user(self) -> dict:
        data = {"profile": True, "email": True, "phone": True}
        _, data = await self.post(f'{self.URL}/composer-api.bx/_action/getUserV2', json=data)
        logger.debug(data)
        self.config.log_info = data['profile'].get('firstName', data['userId'])
        return data

    async def home(self) -> list[str]:
        _, data = await self.get(
            f'{self.URL}/composer-api.bx/page/json/v2', params={'url': '/home', 'from': 'from_app_icon'},
            headers={'firstLoad': 'true', 'MOBILE-LAT': '0', 'MOBILE-IDFA': ''}
        )
        top_vigoda = [item['action']['link'] for item in
                      json.loads(data['widgetStates']['hammers-3569565-default-1'])['products']]

        _, data = await self.post(
            f'{self.URL}/composer-api.bx/page/json/v2',
            params={
                'url': '/home', 'from': 'from_app_icon', 'layout_container': 'home_recommend_test3_v3',
                'layout_page_index': '2'
            }
        )
        vau_ceni_state_id = ''
        for item in data.get("layout", []):
            if item.get("component") == "uWidgetObject" and item.get("name") == "cms.uWidgetObject":
                vau_ceni_state_id = item.get("stateId")
                break
        vau_ceni = [
            v['link'] for k, v in (
                json.loads(data['widgetStates'][vau_ceni_state_id])['TrackingPayloads']['cell'].items()
            )
        ]

        tovari_narashvat_state_id = ''
        for item in data.get("layout", []):
            if item.get("component") == "skuGrid3" and item.get("name") == "tile.tileShelf":
                tovari_narashvat_state_id = item.get("stateId")
                break
        tovari_narashvat = [item['link'] for item in
                            json.loads(data['widgetStates'][tovari_narashvat_state_id])['productContainer']['products']]

        vam_ponravitsya_state_id = ''
        for item in data.get("layout", []):
            if item.get("component") == "tileGrid2" and item.get("name") == "shelf.infiniteScroll":
                vam_ponravitsya_state_id = item.get("stateId")
                break
        vam_ponravitsya = [item['action']['link'] for item in
                           json.loads(data['widgetStates'][vam_ponravitsya_state_id])['items']]

        return top_vigoda + vau_ceni + tovari_narashvat + vam_ponravitsya

    async def collect_pineapples(self):
        self.count, total = await self.count_pineapples()
        self.headers.update(
            {'MOBILE-IDFA': '00000000-0000-0000-0000-000000000000', 'MOBILE-LAT': '0', 'ob_theme': 'DARK'}
        )
        links = None
        link = None
        while self.count < total:
            if not links:
                links = set(await self.home())
            link = await self.move_to_product(link or links.pop())
        logger.success(f'{self.config.log_info} | Ананасы собраны')
        await self.count_pineapples()

    async def count_pineapples(self) -> tuple[int, int]:
        _, data = await self.get(
            'https://www.ozon.ru/landing/pineapple/',
            headers={
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept-Language': 'ru',
                'Connection': 'keep-alive',
                'Host': 'www.ozon.ru',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_7_10 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Mobile/15E148',
                'x-o3-app-name': 'ozonapp_ios',
                'x-o3-app-version': '17.40.1(876)',
                'x-o3-sample-trace': 'false'
            }, follow_redirects=True
        )
        soup = BeautifulSoup(data, 'lxml')
        if soup.find('div', class_='r0q_29'):
            return 0, 0
        count, total = [int(el) for el in soup.find('div', class_='zp8_29 z8p_29 qr0_29').get_text().split('/')]
        logger.info(f'{self.config.log_info} | Pineapples: {count}/{total}')
        return count, total

    async def move_to_product(self, link: str) -> list[str] | None:
        _, data = await self.post(
            f'{self.URL}/composer-api.bx/page/json/v2', params={'url': link.removeprefix('ozon:/')},
            json=self.DEVICE_DATA
        )
        _, data = await self.post(
            f'{self.URL}/composer-api.bx/page/json/v2', params={'url': data['nextPage']}, json=self.DEVICE_DATA
        )
        target_state_id = None
        for item in data.get("layout", []):
            if item.get("component") == "banner" and item.get("name") == "reachRewards.easterEgg":
                target_state_id = item.get("stateId")
                break
        if target_state_id:
            reward = json.loads(data['widgetStates'][target_state_id])['item']['action']['params']
            product_id = reward['product_id']
            hash_value = reward['hash_value']
            _, _data = await self.post(
                f'{self.URL}/composer-api.bx/_action/collapseWidget',
                json={'product_id': product_id, 'hash_value': hash_value}
            )
            match = re.search(r'\d+', _data['notificationBar']['title'])
            self.count += int(match.group()) if match else 1
            logger.success(f'{self.config.log_info} | {_data["notificationBar"]["title"]}. Теперь их {self.count}')

        for i in range(3):
            recommendations_state_id = ''
            for item in data.get("layout", []):
                if item.get("component") == "skuGrid3" and item.get("name") == "shelf.analogShelfPersonalPrimary":
                    recommendations_state_id = item.get("stateId")
                    break
            try:
                recommendations_products = (
                    json.loads(data['widgetStates'][recommendations_state_id])['productContainer']['products']
                )
                return choice([product['link'] for product in recommendations_products])
            except Exception as e:
                _, data = await self.post(
                    f'{self.URL}/composer-api.bx/page/json/v2', params={'url': data['nextPage']}, json=self.DEVICE_DATA
                )
        return

    async def test_try_buy(self):
        need_to_add = await self.check_cart(some_products)
        for product in need_to_add:
            await self.add_to_cart(product)

        some_product = choice(list(some_products))
        logger.info(f'{self} | Trying to buy {some_product}')
        await self.buy(some_product)

    async def try_buy(self):
        need_to_add = await self.check_cart(buy_products)
        for product in need_to_add:
            await self.add_to_cart(product)
        while True:
            now = int(datetime.now().timestamp())
            if now < ts:
                logger.info(f'Waiting for the right time. {str(now)}')
                await asyncio.sleep(1)
            else:
                break
        while True:
            for product in buy_products:
                logger.info(f'{self} | Trying to buy {product}')
                await self.buy(product)

    async def check_cart(self, need_to_buy: set) -> set:
        _, data = await self.get(f'{self.URL}/composer-api.bx/page/json/v2', params={'url': '/cart'})
        cart_split_state_id = None
        for item in data.get("layout", []):
            if item.get("component") == "cartSplit" and item.get("name") == "cart.cartSplit":
                cart_split_state_id = item.get("stateId")
                break
        products = {int(product['product']['id']) for product in
                    json.loads(data['widgetStates'][cart_split_state_id])['items']} if cart_split_state_id else set()
        return need_to_buy - products

    async def add_to_cart(self, product_id: int):
        _, data = await self.post(
            f'{self.URL}/composer-api.bx/_action/addToCart', json=[{"forStars": False, "id": product_id, "quantity": 1}]
        )
        logger.info(data)

    async def buy(self, product_id: int):
        await self.go_checkout(product_id)
        await self.bank_list()
        for bank in banks:
            await self.create_order(bank)

    async def go_checkout(self, product_id: int):
        _, data = await self.post(
            f'{self.URL}/composer-api.bx/page/json/v2', params={'url': '/gocheckout?start=0&activeTab=0'},
            json={
                "nativePaymentEnabled": True, "nativePaymentConfigured": False,
                "deviceId": self.device_id,
                "items": [{"id": str(product_id), "quantity": 1, "selected_delivery_schema": "retail"}]
            }
        )
        logger.info(data)

    async def bank_list(self):
        _, data = await self.post(
            f'{self.URL}/composer-api.bx/page/json/v2', params={'url': '/gocheckout/popularBankList'},
            json=self.DEVICE_DATA
        )
        logger.info(data)

    async def create_order(self, bank):
        # self.config.sleep_after_request = False
        logger.info(f'{bank} {self.proxies["all"]}')
        _, data = await self.post(
            f'{self.URL}/composer-api.bx/_action/v2/createOrder', json={'bankId': bank}
        )
        if data:
            if not data['error']:
                logger.success(f'{self.config.log_info} | {data}')
                return
        self.update_proxy(choice(proxies))


async def main():
    data = list(zip(list((Path.cwd() / 'data' / 'cookies').iterdir()), proxies))
    await asyncio.gather(*[Ozon(account_data).start() for account_data in data])


if __name__ == '__main__':
    random.shuffle(proxies)
    asyncio.run(main())
