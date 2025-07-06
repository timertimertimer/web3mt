import asyncio
from abc import ABC
from json import JSONDecodeError
from typing import Callable, Any, TYPE_CHECKING, Optional
from urllib.parse import urlencode

from better_proxy import Proxy
from curl_cffi import CurlMime
from curl_cffi.requests import AsyncSession, RequestsError, Response, BrowserType
from httpx import AsyncClient

if TYPE_CHECKING:
    from web3db.models import Profile
from web3mt.config import DEV, env
from web3mt.utils import logger, sleep, set_windows_event_loop_policy

set_windows_event_loop_policy()


class SessionConfig:
    def __init__(
        self,
        log_info: str = "Main",
        sleep_after_request: bool = False,
        sleep_range: tuple = (5, 10),
        sleep_echo: bool = False,
        requests_echo: bool = DEV,
        retry_count: int = env.retry_count,
        try_with_default_proxy: bool = False,
    ):
        self.log_info = log_info
        self.sleep_after_request = sleep_after_request
        self.sleep_range = sleep_range
        self.sleep_echo = sleep_echo and sleep_after_request
        self.requests_echo = requests_echo
        self.retry_count = retry_count
        self.try_with_default_proxy = try_with_default_proxy

    def __repr__(self):
        return (
            f"SessionConfig("
            + ", ".join([f"{key}={value}" for key, value in vars(self).items()])
            + ")"
        )


class BaseAsyncSession(ABC):
    _google_chrome_stable_version = 131
    DEFAULT_HEADERS = {
        "Accept": "*/*",
        "Accept-Language": "en-US,en",
        "Connection": "keep-alive",
        "Sec-Ch-Ua": f'"Not_A Brand";v="8", "Chromium";v="{_google_chrome_stable_version}", '
        f'"Google Chrome";v="{_google_chrome_stable_version}"',
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Fetch-Dest": "empty",
        "Sec-Fetch-Mode": "cors",
        "Sec-Fetch-Site": "same-origin",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
        f"Chrome/{_google_chrome_stable_version}.0.0.0 Safari/537.36",
    }

    def __init__(
        self,
        proxy: str | None = env.default_proxy,
        config: SessionConfig | None = None,
        **kwargs,
    ) -> None:
        self.config = config or SessionConfig()
        self._headers = self.DEFAULT_HEADERS | kwargs.pop("headers", {})
        self._proxy: Optional[Proxy] = Proxy.from_str(proxy=proxy) if proxy else None

    def __str__(self):
        return self.config.log_info

    async def __aenter__(self):
        return self

    @property
    def proxy(self):
        return self._proxy.as_url if self._proxy else self._proxy

    @proxy.setter
    def proxy(self, value):
        if isinstance(value, Proxy):
            self._proxy = value
        else:
            self._proxy = Proxy.from_str(proxy=value)

    async def make_request(self, *a, **kw):
        raise NotImplementedError("Must be implemented by subclasses")

    async def head(self, *a, **kw):
        return await self.make_request("HEAD", *a, **kw)

    async def get(self, *a, **kw):
        return await self.make_request("GET", *a, **kw)

    async def post(self, *a, **kw):
        return await self.make_request("POST", *a, **kw)

    async def put(self, *a, **kw):
        return await self.make_request("PUT", *a, **kw)

    async def patch(self, *a, **kw):
        return await self.make_request("PATCH", *a, **kw)

    async def delete(self, *a, **kw):
        return await self.make_request("DELETE", *a, **kw)

    async def options(self, *a, **kw):
        return await self.make_request("OPTIONS", *a, **kw)

    async def parse_exception(
        self,
        i: int,
        request_info: str,
        response,
        response_data,
        exception: type[Exception],
        retry_delay: tuple[int, int],
    ):
        raise NotImplementedError("Must be implemented by subclasses")

    def retry_request(func: Callable) -> Callable:
        async def wrapper(self, *args, **kwargs) -> Any:
            method = kwargs.get("method") or args[0]
            url = kwargs.get("url") or args[1]
            params = kwargs.get("params", {})
            params_str = urlencode(params)
            body = kwargs.get("body") or kwargs.get("json")
            retry_delay = kwargs.pop("retry_delay", self.config.sleep_range)
            retry_count = kwargs.pop("retry_count", self.config.retry_count)
            request_info = f"{method} {url} params={params_str or None} {body=}"
            if self.config.requests_echo:
                logger.info(f"{self.config.log_info} | {request_info}")
            response_data = None
            for i in range(retry_count):
                try:
                    response = None
                    response, response_data = await func(self, *args, **kwargs)
                    if not kwargs.get("follow_redirects") or kwargs.get(
                        "allow_redirects"
                    ):
                        response.raise_for_status()
                    if self.config.sleep_after_request:
                        await sleep(
                            *self.config.sleep_range,
                            log_info=self.config.log_info,
                            echo=self.config.sleep_echo,
                        )
                    return response, response_data
                except Exception as exception:
                    await self.parse_exception(
                        i=i,
                        request_info=request_info,
                        response=response,
                        response_data=response_data,
                        exception=exception,
                        retry_delay=retry_delay,
                    )
                    continue
            else:
                error_message = f"Tried to retry {self.config.retry_count} times"
                if self.config.requests_echo:
                    logger.error(f"{self.config.log_info} | {error_message=}")
                raise RequestsError(error_message)

        return wrapper

    async def update_user_agent(self):
        response, data = await self.get(
            "https://versionhistory.googleapis.com/v1/chrome/platforms/android/channels/stable/versions/all/releases",
            params={"filter": "endtime=none"},
        )
        BaseAsyncSession._google_chrome_stable_version = data["releases"][0][
            "version"
        ].split(".")[0]
        new_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
            f"Chrome/{BaseAsyncSession._google_chrome_stable_version}.0.0.0 Safari/537.36",
            "Sec-Ch-Ua": f'"Not_A Brand";v="8", "Chromium";v="{BaseAsyncSession._google_chrome_stable_version}", '
            f'"Google Chrome";v="{BaseAsyncSession._google_chrome_stable_version}"',
        }
        BaseAsyncSession.DEFAULT_HEADERS.update(new_headers)
        self.headers.update(new_headers)

    async def check_proxy(self, echo: bool = True, **request_kwargs) -> str | None:
        try:
            _, ip = await self.get("https://icanhazip.com", **request_kwargs)
            ip = ip.strip()
            if echo:
                logger.debug(f"{self.config.log_info} | Proxy {ip} is valid")
            return ip
        except RequestsError:
            if echo:
                logger.warning(
                    f"{self.config.log_info} | Proxy {self.proxy} is not working"
                )
        return None

    async def get_proxy_location(
        self, host: str = None, proxy: str = env.default_proxy
    ) -> tuple[str, str]:
        host = host or Proxy.from_str(self.proxy or proxy).host
        _, data = await self.get("https://api.iplocation.net/", params=dict(ip=host))
        logger.debug(
            f"{self.config.log_info} | Proxy {host} in {data['country_code2']}/{data['country_name']}"
        )
        return data["country_name"], data["country_code2"]


class curl_cffiAsyncSession(BaseAsyncSession, AsyncSession):
    def __init__(
        self,
        **kwargs,
    ) -> None:
        BaseAsyncSession.__init__(self, **kwargs)
        impersonate = kwargs.pop("impersonate", BrowserType.chrome120)
        kwargs.pop('config', None)
        kwargs.pop('proxy')
        AsyncSession.__init__(
            self,
            proxy=self.proxy,
            headers=self._headers,
            impersonate=impersonate,
            **kwargs,
        )

    async def __aenter__(self):
        # await self.update_user_agent()
        # await self.check_proxy()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(f"{self.config.log_info} | {exc_val}")
        await self.close()

    @BaseAsyncSession.proxy.setter
    def proxy(self, value: str):
        super(curl_cffiAsyncSession, curl_cffiAsyncSession).proxy.fset(self, value)
        self.proxies["all"] = self.proxy.as_url

    async def parse_exception(
        self, i, request_info, response, response_data, exception: RequestsError, retry_delay
    ):
        response = response or exception.response
        s = f"{request_info=} {exception=}" + (
            f"\n{response_data=}" if response_data else ""
        )
        if exception.code in (28, 55, 56):
            pass
        elif exception.code == 7 and self.config.try_with_default_proxy:
            self.proxy = env.default_proxy
            s += " Trying with default proxy"
        elif not response or 600 >= response.status_code >= 400:
            raise RequestsError(s)
        logger.warning(
            f"{self.config.log_info} | {s}. Retrying {i + 1} after {retry_delay} seconds"
        )
        await sleep(
            *retry_delay,
            log_info=self.config.log_info,
            echo=self.config.sleep_echo,
        )

    @BaseAsyncSession.retry_request
    async def make_request(
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
        retry_count: int = env.retry_count,
        timeout: int = 30,
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
                timeout=timeout,
            )
            data = response.json()
        except JSONDecodeError:
            data = response.text
        return response, data


class httpxAsyncClient(BaseAsyncSession, AsyncClient):
    def __init__(
        self,
        **kwargs,
    ) -> None:
        BaseAsyncSession.__init__(self, **kwargs)
        kwargs.pop('config')
        kwargs.pop('proxy')
        AsyncClient.__init__(
            self,
            proxy=self.proxy,
            headers=self._headers,
            **kwargs,
        )

    async def parse_exception(
        self, i, request_info, response, response_data, exception, retry_delay
    ):
        raise NotImplementedError

    @BaseAsyncSession.retry_request
    async def make_request(
        self,
        method: str,
        url: str,
        params: dict = None,
        headers: dict = None,
        cookies: dict = None,
        data: dict | str = None,
        json: dict = None,
        follow_redirects: bool = False,
        retry_count: int = env.retry_count,
        timeout: int = 30,
        # `verify` argument in httpx lib works only on client, will not work each request, so to use `verify` you need to create a new client
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
                follow_redirects=follow_redirects,
                timeout=timeout,
            )
            data = response.json()
        except JSONDecodeError:
            data = response.text
        return response, data


class Profilecurl_cffiAsyncSession(curl_cffiAsyncSession):
    def __init__(
        self, profile: "Profile", config: SessionConfig = None, **kwargs
    ) -> None:
        config = config or SessionConfig()
        config.log_info = str(profile.id)
        super().__init__(
            proxy=profile.proxy.proxy_string,
            config=config,
            **kwargs,
        )


class ProfilehttpxAsyncClient(httpxAsyncClient):
    def __init__(
        self, profile: "Profile", config: SessionConfig = None, **kwargs
    ) -> None:
        self.profile = profile
        config = config or SessionConfig()
        config.log_info = str(profile.id)
        super().__init__(
            proxy=profile.proxy.proxy_string,
            config=config,
            **kwargs,
        )


async def check_proxies():
    from web3db.core import create_db_instance

    db = create_db_instance()
    profiles = await db.get_all_from_table(Profile)
    await asyncio.gather(
        *[Profilecurl_cffiAsyncSession(profile).check_proxy() for profile in profiles]
    )


async def get_location(ip: str = env.default_proxy):
    client = curl_cffiAsyncSession()
    await client.get_proxy_location(ip)


async def test_ua_update():
    async with curl_cffiAsyncSession() as session:
        print(session.headers)


if __name__ == '__main__':
    asyncio.run(test_ua_update())
