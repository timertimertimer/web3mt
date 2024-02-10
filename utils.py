import os
import re
import json
import random
import asyncio
import configparser
from typing import Callable, Any
from pathlib import Path
from dotenv import load_dotenv

from aiohttp.client import ClientSession
from aiohttp import ServerDisconnectedError, ClientConnectionError, ClientResponseError
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy

from eth_account import Account

from web3db.models import Profile
from web3db.utils import DEFAULT_UA

from logger import logger

load_dotenv()

PRICE_FACTOR = 1.1
INCREASE_GAS = 1.1
Z8 = 10 ** 8
Z18 = 10 ** 18
config = configparser.ConfigParser()
MWD = Path(__file__).parent

RETRY_COUNT = int(os.getenv('RETRY_COUNT'))


def get_config_section(section: str) -> dict:
    path = Path(__file__).parent / 'config.ini'
    config.read(path)
    return dict(config[section])


def find_keys(input_data: str) -> str | None:
    if not input_data:
        return None

    for value in re.findall(r'\w+', input_data):
        try:
            return Account.from_key(private_key=value).key.hex()
        except ValueError:
            continue
    return None


def get_accounts(file_path: str = None) -> list[Account] | list:
    accounts = []
    accounts_path = MWD / 'evm' / 'accounts.txt'
    if not accounts_path.exists():
        accounts_path.touch()
        return accounts
    with open(file_path or accounts_path, 'r', encoding='utf-8') as file:
        for row in file:
            target_private_key = find_keys(input_data=row.strip())

            if target_private_key:
                accounts.append(Account.from_key(target_private_key))
    return accounts


def read_json(path: str, encoding: str = None) -> list | dict:
    with open(path, encoding=encoding) as file:
        return json.load(file)


def read_txt(path: str, encoding: str = None) -> str:
    with open(path, encoding=encoding) as file:
        return file.read()


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
                    await asyncio.sleep(delay)
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
                        logger.error(f'{url} {e.message}', id=self.profile.id)
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
            data: str = None,
            json: dict = None,
            follow_redirects: bool = False,
            delay: bool = True,
            echo: bool = True
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
