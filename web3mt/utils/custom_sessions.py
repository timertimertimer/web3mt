import asyncio
from functools import partialmethod
from json import JSONDecodeError
from typing import Callable, Any, TYPE_CHECKING, Optional

from curl_cffi import CurlMime
from curl_cffi.requests import AsyncSession, RequestsError, Response, BrowserType
from better_proxy import Proxy

if TYPE_CHECKING:
    from web3db.models import Profile
from web3mt.consts import DEV, env
from web3mt.utils import my_logger, sleep, set_windows_event_loop_policy

set_windows_event_loop_policy()
RETRY_COUNT = 5


class SessionConfig:
    def __init__(
            self,
            log_info: str = 'Main',
            sleep_after_request: bool = DEV,
            sleep_range: tuple = (5, 10),
            sleep_echo: bool = False,
            requests_echo: bool = DEV,
            retry_count: int = RETRY_COUNT,
            try_with_default_proxy: bool = False
    ):
        self.log_info = log_info
        self.sleep_after_request = sleep_after_request
        self.sleep_range = sleep_range
        self.sleep_echo = sleep_echo and sleep_after_request
        self.requests_echo = requests_echo
        self.retry_count = retry_count
        self.try_with_default_proxy = try_with_default_proxy

    def __repr__(self):
        return f'SessionConfig(' + ", ".join([f'{key}={value}' for key, value in vars(self).items()]) + ')'


class CustomAsyncSession(AsyncSession):
    DEFAULT_HEADERS = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en",
        "Connection": "keep-alive",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/131.0.0.0 Safari/537.36',
    }
    _stable_version: str | None = None

    def __init__(
            self,
            proxy: str | None = env.DEFAULT_PROXY,
            config: SessionConfig | None = None,
            **kwargs
    ) -> None:
        self.config = config or SessionConfig()
        headers = self.DEFAULT_HEADERS | kwargs.pop('headers', {})
        impersonate = kwargs.pop('impersonate', BrowserType.chrome120)
        super().__init__(
            proxy=Proxy.from_str(proxy=proxy).as_url if proxy else None,
            headers=headers,
            impersonate=impersonate,
            **kwargs
        )

    async def __aenter__(self):
        # await self.update_user_agent()
        # await self.check_proxy()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            my_logger.error(f'{self.config.log_info} | {exc_val}')
        await self.close()

    def __str__(self):
        return self.config.log_info

    def retry(func: Callable) -> Callable:
        async def wrapper(self, *args, **kwargs) -> Any:
            method = kwargs.get('method') or args[0]
            url = kwargs.get('url') or args[1]
            params = kwargs.get('params')
            params = '?' + '&'.join([f'{key}={value}' for key, value in params.items()]) if params else ''
            retry_delay = kwargs.pop('retry_delay', self.config.sleep_range)
            retry_count = kwargs.pop('retry_count', self.config.retry_count)
            if self.config.requests_echo:
                my_logger.debug(f'{self.config.log_info} | {method} {url.rstrip("/") + params}')
            data = None
            for i in range(retry_count):
                try:
                    response = None
                    response, data = await func(self, *args, **kwargs)
                    if not kwargs.get('follow_redirects'):
                        response.raise_for_status()
                    if self.config.sleep_after_request:
                        await sleep(
                            *self.config.sleep_range, log_info=self.config.log_info, echo=self.config.sleep_echo
                        )
                    return response, data
                except RequestsError as e:
                    response = response or e.response
                    s = f'{url.rstrip("/") + params} {e}' + (f' {data}' if data else '') + '.'
                    if e.code in (28, 55, 56):
                        pass
                    elif e.code == 7 and self.config.try_with_default_proxy:
                        self.proxies['all'] = env.DEFAULT_PROXY
                        s += ' Trying with default proxy'
                    elif not response or 600 >= response.status_code >= 400:
                        raise RequestsError(s)
                    my_logger.warning(f'{self.config.log_info} | {s}. Retrying {i + 1} after {retry_delay} seconds')
                    await sleep(*retry_delay, log_info=self.config.log_info, echo=self.config.sleep_echo)
                    continue
            else:
                error_message = f'Tried to retry {self.config.retry_count} times'
                if self.config.requests_echo:
                    my_logger.error(f'{self.config.log_info} | {error_message}')
                raise RequestsError(error_message)

        return wrapper

    async def update_user_agent(self):
        response, data = await self.get(
            'https://versionhistory.googleapis.com/v1/chrome/platforms/android/channels/stable/versions/all/releases',
            params={'filter': 'endtime=none'}
        )
        CustomAsyncSession._stable_version = data['releases'][0]['version'].split('.')[0]
        new_headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                          f'Chrome/{CustomAsyncSession._stable_version}.0.0.0 Safari/537.36',
            'Sec-Ch-Ua': f'"Not_A Brand";v="8", "Chromium";v="{CustomAsyncSession._stable_version}", '
                         f'"Google Chrome";v="{CustomAsyncSession._stable_version}"'
        }
        CustomAsyncSession.DEFAULT_HEADERS.update(new_headers)
        self.headers.update(new_headers)

    async def check_proxy(self, echo: bool = True, **request_kwargs) -> str | None:
        try:
            _, ip = await self.get('https://icanhazip.com', **request_kwargs)
            ip = ip.strip()
            if echo:
                my_logger.debug(f'{self.config.log_info} | Proxy {ip} is valid')
            return ip
        except RequestsError:
            if echo:
                my_logger.warning(f'{self.config.log_info} | Proxy {self.proxies["all"]} is not working')

    async def get_proxy_location(self, host: str = None, proxy: str = env.DEFAULT_PROXY) -> tuple[str, str]:
        host = host or Proxy.from_str(self.proxies['all'] or proxy).host
        _, data = await self.get('https://api.iplocation.net/', params=dict(ip=host))
        my_logger.debug(f'{self.config.log_info} | Proxy {host} in {data["country_code2"]}/{data["country_name"]}')
        return data['country_name'], data['country_code2']

    def update_proxy(self, proxy: str):
        self.proxies['all'] = proxy

    @retry
    async def request(
            self,
            method: str,
            url: str,
            params: dict = None,
            headers: dict = None,
            cookies: dict = None,
            data: dict | str = None,
            json: dict = None,
            multipart: Optional[CurlMime] = None,
            follow_redirects: bool = False,
            verify: bool = False,
            retry_count: int = RETRY_COUNT,
            timeout: int = 30
    ) -> tuple[Response, dict]:
        try:
            response = await super().request(
                method=method,
                url=url,
                params=params,
                headers=headers,
                cookies=cookies,
                data=data,
                json=json,
                multipart=multipart,
                allow_redirects=follow_redirects,
                verify=verify,
                timeout=timeout
            )
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


class ProfileSession(CustomAsyncSession):
    def __init__(
            self, profile: 'Profile', config: SessionConfig = None, **kwargs
    ) -> None:
        config = config or SessionConfig()
        config.log_info = str(profile.id)
        proxy = profile.proxy.proxy_string
        super().__init__(Proxy.from_str(proxy=proxy).as_url, config, **kwargs)


async def check_proxies():
    from web3db.core import create_db_instance
    db = create_db_instance()
    profiles = await db.get_all_from_table(Profile)
    await asyncio.gather(*[ProfileSession(profile).check_proxy() for profile in profiles])


async def get_location(ip: str = env.DEFAULT_PROXY):
    client = CustomAsyncSession()
    await client.get_proxy_location(ip)


async def test_ua_update():
    async with CustomAsyncSession() as session:
        print(session.headers)


if __name__ == '__main__':
    asyncio.run(test_ua_update())
