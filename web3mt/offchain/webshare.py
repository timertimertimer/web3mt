import asyncio
from functools import partialmethod
from pprint import pprint
from web3mt.config import env
from web3mt.utils import curl_cffiAsyncSession


class Webshare:
    API_VERSION = 2
    URL = f'https://proxy.webshare.io/api/v{API_VERSION}'

    def __init__(self):
        self.session = curl_cffiAsyncSession()

    async def request(self, method: str, path: str, **kwargs):
        return await self.session.request(
            method, f'{self.URL}/{path}', headers={"Authorization": f"Token {env.webshare_api_key}"}, **kwargs
        )

    head = partialmethod(request, "HEAD")
    get = partialmethod(request, "GET")
    post = partialmethod(request, "POST")
    put = partialmethod(request, "PUT")
    patch = partialmethod(request, "PATCH")
    delete = partialmethod(request, "DELETE")
    options = partialmethod(request, "OPTIONS")

    async def proxy_list(self):
        _, data = await self.get('proxy/list/?mode=direct&page=1&page_size=100')
        return {f'http://{el["username"]}:{el["password"]}@{el["proxy_address"]}:{el["port"]}' for el in data['results']}

    async def replacement_list(self):
        _, data = await self.get('proxy/replace')
        return data

    async def replaced_proxies_list(self):
        _, data = await self.get('proxy/list/replaced', follow_redirects=True)
        return data


async def main():
    ws = Webshare()
    proxies = await ws.replaced_proxies_list()
    pprint(proxies)
    print(len(proxies))


if __name__ == '__main__':
    asyncio.run(main())
