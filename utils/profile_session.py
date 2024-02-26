import asyncio
import random
from typing import Callable, Any

from aiohttp import ClientResponseError, ClientConnectionError, ServerDisconnectedError, ClientSession
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from web3db.models import Profile
from web3db.utils import DEFAULT_UA

from .logger import logger
from .sleeping import sleep

RETRY_COUNT = 5


class ProfileSession(ClientSession):
    def __init__(self, profile: Profile, **kwargs) -> None:
        self.profile = profile
        verify_ssl = kwargs.get('verify_ssl', False)
        headers = kwargs.pop('headers', {'User-Agent': DEFAULT_UA})
        super().__init__(
            connector=ProxyConnector.from_url(
                url=Proxy.from_str(proxy=profile.proxy.proxy_string).as_url, verify_ssl=verify_ssl
            ),
            headers=headers,
            **kwargs
        )

    def retry(func: Callable) -> Callable:
        async def wrapper(self, *args, **kwargs) -> Any:
            method = kwargs.get('method')
            url = kwargs.get('url', 'unknown url')
            delay = kwargs.get('delay', random.uniform(5, 10))
            echo = kwargs.get('echo', True)
            if echo:
                logger.info(f'{method} {url}', id=self.profile.id)
            for i in range(RETRY_COUNT):
                try:
                    response, data = await func(self, *args, **kwargs)
                    if not kwargs.get('follow_redirects'):
                        response.raise_for_status()
                    if echo:
                        logger.info(f'Sleeping after request {delay} seconds...', id=self.profile.id)
                    await sleep(delay)
                    return response, data
                except ServerDisconnectedError as e:
                    if echo:
                        logger.error(e.message, id=self.profile.id)
                        logger.info(f'Retrying {i + 1}', id=self.profile.id)
                        logger.info(f'Sleeping after request {delay} seconds...', id=self.profile.id)
                    await asyncio.sleep(delay)
                    continue
                except (ClientResponseError, ClientConnectionError) as e:
                    if echo:
                        logger.error(f'{url} {e}', id=self.profile.id)
                    raise e
            else:
                if echo:
                    logger.info(f'Tried to retry {RETRY_COUNT} times. Nothing can do anymore :(', id=self.profile.id)
                return None

        return wrapper

    @retry
    async def request(
            self,
            method: str,
            url: str,
            params: dict = None,
            data: dict = None,
            json: dict = None,
            follow_redirects: bool = False
    ):
        response = await super().request(
            method=method,
            url=url,
            params=params,
            data=data,
            json=json,
            allow_redirects=follow_redirects
        )
        if response.content_type in ['text/html', 'application/octet-stream', 'text/plain']:
            data = await response.text()
        else:
            data = await response.json()
        return response, data
