import random
from functools import partialmethod
from json import JSONDecodeError
from typing import Callable, Any

import curl_cffi.requests
from curl_cffi.requests import AsyncSession, RequestsError
from better_proxy import Proxy
from web3db.models import Profile
from web3db.utils import DEFAULT_UA

from .logger import logger
from .sleeping import sleep
from .windows import set_windows_event_loop_policy

set_windows_event_loop_policy()

RETRY_COUNT = 5


class ProfileSession(AsyncSession):
    DEFAULT_HEADERS = {
        "accept": "*/*",
        "accept-language": "en-US,en",
        "user-agent": DEFAULT_UA,
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        "sec-ch-ua-platform": '"Windows"',
        "sec-ch-ua-mobile": "?0",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "connection": "keep-alive",
    }

    def __init__(self, profile: Profile, sleep_echo: bool = True, requests_echo: bool = True, **kwargs) -> None:
        self.profile = profile
        self.sleep_echo = sleep_echo
        self.request_echo = requests_echo
        headers = kwargs.pop('headers', self.DEFAULT_HEADERS)
        impersonate = kwargs.pop('impersonate', curl_cffi.requests.BrowserType.chrome120)
        super().__init__(
            proxy=Proxy.from_str(proxy=profile.proxy.proxy_string).as_url,
            headers=headers,
            impersonate=impersonate,
            **kwargs
        )

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    def retry(func: Callable) -> Callable:
        async def wrapper(self, *args, **kwargs) -> Any:
            method = kwargs.get('method', None) or args[0]
            url = kwargs.get('url', 'unknown url')
            delay = kwargs.pop('delay', random.uniform(5, 10))
            retry_count = kwargs.pop('retry_count', RETRY_COUNT)
            if self.request_echo:
                logger.info(f'{self.profile.id} | {method} {url}')
            data = None
            for i in range(retry_count):
                try:
                    response, data = await func(self, *args, **kwargs)
                    if not kwargs.get('follow_redirects'):
                        response.raise_for_status()
                    await sleep(delay, profile_id=self.profile.id, echo=self.sleep_echo)
                    return response, data
                except RequestsError as e:
                    s = f'{self.profile.id} | {url} {e} {data if data is not None else ""}'
                    if e.code in (28, 35, 52, 56):
                        logger.warning(f'{s} Retrying {i + 1} after {delay} seconds')
                        await sleep(delay, profile_id=self.profile.id, echo=self.sleep_echo)
                        continue
                    elif response.status_code in [400, 401, 403, 404, 500]:
                        logger.warning(s)
                        raise e
                    else:
                        logger.warning(f'{s} Retrying {i + 1} after {delay} seconds')
                        await sleep(delay, profile_id=self.profile.id, echo=self.sleep_echo)
                        continue
            else:
                if self.request_echo:
                    logger.info(f'{self.profile.id} | Tried to retry {RETRY_COUNT} times. Nothing can do anymore :(')
                return None

        return wrapper

    @retry
    async def request(
            self,
            method: str,
            url: str,
            params: dict = None,
            headers: dict = None,
            data: dict = None,
            json: dict = None,
            follow_redirects: bool = False,
            verify: bool = False,
            retry_count: int = RETRY_COUNT,
            timeout: int = 30
    ):
        response = await super().request(
            method=method,
            url=url,
            params=params,
            headers=headers,
            data=data,
            json=json,
            allow_redirects=follow_redirects,
            verify=verify,
            timeout=timeout
        )
        try:
            data = response.json()
        except JSONDecodeError:
            data = response.text
        return response, data

    head = partialmethod(request, "HEAD")
    get = partialmethod(request, "GET")
    post = partialmethod(request, "POST")
    put = partialmethod(request, "PUT")
    patch = partialmethod(request, "PATCH")
    delete = partialmethod(request, "DELETE")
    options = partialmethod(request, "OPTIONS")
