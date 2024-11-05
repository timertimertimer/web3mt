import asyncio
import json
import random
import re
import uuid
from datetime import datetime
from random import choice
from bs4 import BeautifulSoup
from examples.offchain.ozon.data import proxies, parse_cookies
from web3mt.utils import CustomAsyncSession, my_logger
from web3mt.utils.custom_sessions import SessionConfig

products = [1623223886]


class Ozon(CustomAsyncSession):
    DEFAULT_HEADERS = {
        'Accept': 'application/json',
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
    DEVICE_DATA = {
        "biometryType": "touchId", "os": "iOS", "version": "16.7.10", "hasBiometrics": True,
        "model": "iPhone10,4", "vendor": "Android", "deviceId": 'AA5EC0A2-DC44-40FB-93A3-E5FFF763ED7A'
    }
    URL = 'https://api.ozon.ru'
    XAPI_HEADERS = {
        'Host': 'xapi.ozon.ru',
        'Content-Type': 'application/json; charset=utf-8',
        'Accept-Encoding': 'gzip, deflate, br',
        'Connection': 'keep-alive',
        'Accept': '*/*',
        'User-Agent': 'TrackerSDK_IOS v0',
        'x-o3-fp': 'GFvu2hwskv3s0T40AO5ck/P2j+1IWhbxwMQnGLM9',
        'Accept-Language': 'ru'
    }

    def __init__(self, account_data: tuple[str, str]):
        cookie_file, proxy = account_data
        proxy = choice(proxies)
        super().__init__(
            proxy=proxy,
            config=SessionConfig(sleep_after_request=True, sleep_range=(1, 3)),
            cookies=parse_cookies(cookie_file)
        )
        my_logger.info(proxy)
        self.count = 0

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

    async def start(self):
        await self.generate_cookies()
        await self.current_location()
        await self.get_user()

        await self.collect_pineapples()
        # while True:
        #     await self.buy(choice(products))

    async def authorize_token(self):

        _, data = await self.post(
            'https://xapi.ozon.ru/tracker.bx/v1/authorize', headers=self.XAPI_HEADERS,
            json={
                "build_number": 876,
                "platform_store": "AppStore",
                "namespace": "bx",
                "appsflyer_id": "1568554658520-1651879",
                "test_id": "",
                "google_id": "00000000-0000-0000-0000-000000000000",
                "platform": "ios",
                "token": "6.38531849.bsecfmmlc4nnlz23qyphk1oa.57.ATaBvFtL4ja0v7aZ2fQDIPVAibX7aPM5j3jGHDEmQWE1Z1slI1jxime94FqFXZG2j3IZlArmVQrUhlyFu9lX3oiILQcuD9g5xhFFHqf518lKHckyMYKCSxszsLeJQhGCvQ..20241104155259.vfNrKuZBf5GCf3BrhMKDGp0UVdV57CvwUc3IumeuAf4.17c7d317edde2bcf9",
                "install_id": "1FD27D1C-AA26-459D-8DDD-D8D158D096FA",
                "os_version": "16.7.10", "firebase_install_id": "A9EBD58BCF3F4A5184F22CFFB9631962",
                "device_model": "iPhone10,4"
            }
        )

    async def generate_cookies(self):
        # _, data = await self.post(f'{self.URL}/composer-api.bx/_action/get3rdPartyConfig', json={})

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
        my_logger.debug(data)
        return data

    async def get_user(self) -> dict:
        data = {"profile": True, "email": True, "phone": True}
        _, data = await self.post(f'{self.URL}/composer-api.bx/_action/getUserV2', json=data)
        my_logger.debug(data)
        self.config.log_info = data['profile']['firstName']
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
        count, total = [int(el) for el in soup.find('div', class_='zp8_29 z8p_29 qr0_29').get_text().split('/')]
        my_logger.info(f'{self.config.log_info} | Pineapples: {count}/{total}')
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
            my_logger.success(f'{self.config.log_info} | {_data["notificationBar"]["title"]}. Теперь их {self.count}')

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

    async def buy(self, product_id: int):
        await self.add_to_cart(product_id)
        await self.bank_list()
        await self.set_payment()
        await self.create_order()

    async def add_to_cart(self, product_id: int):
        _, data = await self.post(
            f'{self.URL}/composer-api.bx/_action/addToCart', json=[{"forStars": False, "id": product_id, "quantity": 1}]
        )
        my_logger.info(data)
        await asyncio.sleep(5)

    async def bank_list(self):
        _, data = await self.post(
            f'{self.URL}/composer-api.bx/page/json/v2', params={'url': '/gocheckout/popularBankList'},
            json=self.DEVICE_DATA
        )
        my_logger.info(data)

    async def set_payment(self):
        _, data = await self.post(
            f'{self.URL}/composer-api.bx/page/json/v2', params={'url': '/gocheckout?payment_type%3D3%26set_payment%3D0'}
        )
        my_logger.info(data)

    async def create_order(self):
        self.config.sleep_after_request = False
        proxy = self.proxies['all']
        for _ in range(20):
            bank = choice([
                'bank100000000004',
                'bank110000000005',
                'bank100000000008',
                'bank100000000273',
                'bank100000000111'
            ])
            my_logger.info(f'{bank} {proxy}')
            _, data = await self.post(
                f'{self.URL}/composer-api.bx/_action/v2/createOrder', json={'bankId': bank}
            )
            if data:
                if not data['data']['error']:
                    my_logger.success(f'{self.config.log_info} | {data}')
            my_logger.warning(data)
            proxy = choice(proxies)
            self.update_proxy(proxy)


async def check_proxy():
    session = CustomAsyncSession(choice(proxies))
    host = await session.check_proxy()
    await session.get_proxy_location(host)


async def main():
    random.shuffle(proxies)
    data = list(zip([
        'irek_cookies.json',
        'my_cookies.txt',
        'talgat_cookies.json'
    ], proxies))
    await asyncio.gather(*[Ozon(account_data).start() for account_data in data])


if __name__ == '__main__':
    asyncio.run(main())
