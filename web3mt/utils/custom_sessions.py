import asyncio
from functools import partialmethod
from json import JSONDecodeError
from typing import Callable, Any, Union, TYPE_CHECKING
from curl_cffi.requests import AsyncSession, RequestsError, Response, BrowserType
from better_proxy import Proxy

if TYPE_CHECKING:
    from web3db.models import Profile as RemoteProfile
    from web3mt.local_db import Profile as LocalProfile
from web3mt.consts import DEV, Web3mtENV
from web3mt.utils import my_logger, sleep, set_windows_event_loop_policy

set_windows_event_loop_policy()
RETRY_COUNT = 5


class SessionConfig:
    def __init__(
            self,
            log_info: str = 'Main',
            sleep_after_request: bool = DEV,
            sleep_range: tuple = (5, 10),
            sleep_echo: bool = DEV,
            requests_echo: bool = DEV,
            retry_count: int = RETRY_COUNT
    ):
        self.log_info = log_info
        self.sleep_after_request = sleep_after_request
        self.sleep_range = sleep_range
        self.sleep_echo = sleep_echo and sleep_after_request
        self.requests_echo = requests_echo
        self.retry_count = retry_count

    def __repr__(self):
        return f'SessionConfig(' + ", ".join([f'{key}={value}' for key, value in vars(self).items()]) + ')'


class CustomAsyncSession(AsyncSession):
    DEFAULT_HEADERS = {
        "accept": "*/*",
        "accept-language": "en-US,en",
        "user-agent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) '
                      'Chrome/126.0.0.0 Safari/537.36',
        "sec-ch-ua": '"Not_A Brand";v="8", "Chromium";v="126", "Google Chrome";v="126"',
        "sec-ch-ua-platform": '"Windows"',
        "sec-ch-ua-mobile": "?0",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "connection": "keep-alive",
    }

    def __init__(
            self,
            proxy: str = Web3mtENV.DEFAULT_PROXY,
            config: SessionConfig = None,
            **kwargs
    ) -> None:
        self.config = config or SessionConfig()
        headers = self.DEFAULT_HEADERS | kwargs.pop('headers', {})
        impersonate = kwargs.pop('impersonate', BrowserType.chrome120)
        super().__init__(
            proxy=Proxy.from_str(proxy=proxy).as_url,
            headers=headers,
            impersonate=impersonate,
            **kwargs
        )

    async def __aenter__(self):
        await self.check_proxy()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            my_logger.error(f'{self.config.log_info} | {exc_val}')
        else:
            my_logger.success(f'{self.config.log_info} | Tasks done')
        await self.close()

    def retry(func: Callable) -> Callable:
        async def wrapper(self, *args, **kwargs) -> Any:
            method = args[0]
            url = args[1]
            params = kwargs.get('params')
            params = '?' + '&'.join([f'{key}={value}' for key, value in params.items()]) if params else ''
            retry_delay = kwargs.pop('retry_delay', self.config.sleep_range)
            retry_count = kwargs.pop('retry_count', self.config.retry_count)
            if self.config.requests_echo:
                my_logger.info(f'{self.config.log_info} | {method} {url.rstrip("/") + params}')
            data = None
            for i in range(retry_count):
                try:
                    response = None
                    response, data = await func(self, *args, **kwargs)
                    if not kwargs.get('follow_redirects'):
                        response.raise_for_status()
                    if self.config.sleep_after_request:
                        await sleep(*self.config.sleep_range, log_info=self.config.log_info,
                                    echo=self.config.sleep_echo)
                    return response, data
                except RequestsError as e:
                    s = f'{url.rstrip("/") + params} {e} {data or ""}'
                    if e.code in (28, 55, 56):
                        pass
                    elif not response or 600 >= response.status_code >= 400:
                        raise RequestsError(s)
                    my_logger.warning(f'{self.config.log_info} | {s}. Retrying {i + 1} after {retry_delay} seconds')
                    await sleep(*retry_delay, log_info=self.config.log_info, echo=self.config.sleep_echo)
                    continue
            else:
                error_message = f'Tried to retry {self.config.retry_count} times'
                if self.config.requests_echo:
                    my_logger.info(f'{self.config.log_info} | {error_message}')
                raise RequestsError(error_message)

        return wrapper

    async def get_stable_chrome_user_agent(self):  # TODO
        response, data = await self.get(
            'https://versionhistory.googleapis.com/v1/chrome/platforms/android/channels/stable/versions/all/releases',
            params={'filter': 'endtime=none'}
        )
        self.headers
        ...

    async def check_proxy(self):
        try:
            _, ip = await self.get('https://icanhazip.com')
            if ip.strip() not in self.proxies['all']:
                raise RequestsError(f'Proxy {self.proxies["all"]} is not working')
            my_logger.info(f'{self.config.log_info} | Proxy {self.proxies["all"]} is valid')
            return True
        except RequestsError:
            my_logger.warning(f'{self.config.log_info} | Proxy {self.proxies["all"]} is not working')
            return False

    @retry
    async def request(
            self,
            method: str,
            url: str,
            params: dict = None,
            headers: dict = None,
            data: dict | str = None,
            json: dict = None,
            cookies: dict = None,
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
                data=data,
                json=json,
                cookies=cookies,
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
            self, profile: Union['RemoteProfile', 'LocalProfile'], config: SessionConfig = None, **kwargs
    ) -> None:
        config = config or SessionConfig()
        config.log_info = str(profile.id)
        proxy = profile.proxy.proxy_string
        super().__init__(Proxy.from_str(proxy=proxy).as_url, config, **kwargs)


async def check_proxies():
    from web3mt.local_db import DBHelper, Profile
    db = DBHelper(Web3mtENV.LOCAL_CONNECTION_STRING)
    profiles = await db.get_all_from_table(Profile)
    await asyncio.gather(*[ProfileSession(profile).check_proxy() for profile in profiles])


if __name__ == '__main__':
    asyncio.run(check_proxies())
