import asyncio
import asyncio.exceptions
import re
import json
import configparser
from logger import logger
from pathlib import Path

import web3.main
import web3.auto
from eth_account import Account
from web3 import Web3
from web3.eth import AsyncEth

PRICE_FACTOR = 1.1
INCREASE_GAS = 1.1
Z8 = 10 ** 8
Z18 = 10 ** 18
config = configparser.ConfigParser()
MWD = Path(__file__).parent


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


def get_accounts(file_path: str = None) -> list[str]:
    accounts = []
    accounts_path = MWD / 'evm' / 'accounts.txt'
    if not accounts_path.exists():
        accounts_path.touch()
        return accounts
    with open(file_path or accounts_path, 'r', encoding='utf-8') as file:
        for row in file:
            target_private_key = find_keys(input_data=row.strip())

            if target_private_key:
                accounts.append(target_private_key)
    return accounts


async def get_web3(node_url: str):
    w3: web3.main.Web3 = Web3(Web3.AsyncHTTPProvider(node_url), modules={'eth': (AsyncEth,)}, middlewares=[])
    if await w3.is_connected():
        logger.info(f'Successfully connected to {node_url}')
        return w3
    logger.error(f'Failed to connect to {node_url}')


async def get_chain_id(provider: web3.auto.Web3) -> int:
    try:
        return await provider.eth.chain_id

    except (asyncio.exceptions.TimeoutError, TimeoutError):
        return await get_chain_id(provider=provider)

    except Exception as error:
        if not str(error):
            return get_chain_id(provider=provider)


async def get_nonce(provider: web3.auto.Web3,
                    address: str) -> int:
    try:
        return await provider.eth.get_transaction_count(address)

    except (asyncio.exceptions.TimeoutError, TimeoutError):
        return await get_nonce(provider=provider,
                               address=address)

    except Exception as error:
        if not str(error):
            return get_nonce(provider=provider,
                             address=address)


async def get_gwei(provider: web3.auto.Web3) -> int:
    try:
        return await provider.eth.gas_price

    except (asyncio.exceptions.TimeoutError, TimeoutError):
        return await get_gwei(provider=provider)

    except Exception as error:
        if not str(error):
            return get_gwei(provider=provider)


def read_json(path: str, encoding: str = None) -> list | dict:
    with open(path, encoding=encoding) as file:
        return json.load(file)


def read_txt(path: str, encoding: str = None) -> str:
    with open(path, encoding=encoding) as file:
        return file.read()
