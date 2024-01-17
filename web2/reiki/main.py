import asyncio
import pytz
import datetime
import json
import random
from typing import Callable, Any
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

from aiohttp.client_exceptions import ClientResponseError, ServerDisconnectedError
from aiohttp import ClientSession
from aiohttp_proxy import ProxyConnector
from better_proxy import Proxy
from better_automation.discord import DiscordClient, DiscordAccount
from better_automation.twitter import TwitterClient, TwitterAccount

from eth_account.messages import encode_defunct
from eth_account.signers.local import LocalAccount
from web3.auto import w3

from evm.client import Client
from evm.config import REIKI_ABI
from evm.reiki import mint
from web2.reiki.db import *
from web2.reiki.config import *

from utils import logger, read_json
from models import Profile, BNB
from web2.reader import get_profiles

load_dotenv()


def retry(n: int):
    def wrapper(func: Callable) -> Callable:
        async def inner(*args, **kwargs) -> Any:
            for i in range(n):
                try:
                    return await func(*args, **kwargs)
                except ServerDisconnectedError:
                    logger.error(f'Retrying {i + 1}')
                    continue
            else:
                logger.info(f'Tried to retry {n} times. Nothing can do anymore :(')
                return None

        return inner

    return wrapper


@retry(5)
async def request(
        session: ClientSession,
        method: str,
        url: str,
        params: dict = None,
        json: dict = None,
        follow_redirects: bool = False
):
    logger.info(f'{method} {url}')
    response = await session.request(
        method=method,
        url=url,
        params=params,
        json=json,
        allow_redirects=follow_redirects
    )
    if response.content_type in ['text/html', 'application/octet-stream']:
        data = await response.text()
    else:
        data = await response.json()
    delay = random.uniform(5, 15)
    logger.info(f'Sleeping for {delay} seconds...')
    await asyncio.sleep(delay)
    return response, data


async def me(session: ClientSession, account: LocalAccount):
    url = 'https://reiki.web3go.xyz/api/GoldLeaf/me'
    while True:
        response, data = await request(session, 'GET', url)
        try:
            response.raise_for_status()
            logger.success(
                f'{account.address[:6]} | Points: today - {data["today"] if "today" in data else 0}, total - {data["total"] if "total" in data else 0}')
            return
        except ClientResponseError as e:
            logger.error(f'{account.address[:6]} | {e.message}')
            await create_bearer_token(session, account)


async def create_bearer_token(session: ClientSession, account: LocalAccount):
    nonce = await web3_nonce(session, account.address)
    token = await web3_challenge(session, account, nonce)
    await insert_record(account.address, token)
    session.headers['Authorization'] = f'Bearer {token}'


async def web3_nonce(session: ClientSession, address: str) -> str:
    url = REIKI_API + "account/web3/web3_nonce"
    payload = {
        "address": address
    }
    response, data = await request(session, 'POST', url, json=payload)
    nonce = data['nonce']
    logger.success(f'{address[:6]} | Nonce: {nonce}')
    return nonce


def message_and_sign_message(account: LocalAccount, nonce: str) -> tuple[str, str]:
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
    message = f'reiki.web3go.xyz wants you to sign in with your Ethereum account:\n{account.address}\n\nWelcome to Web3Go! Click to sign in and accept the Web3Go Terms of Service. This request will not trigger any blockchain transaction or cost any gas fees. Your authentication status will reset after 7 days. Wallet address: {account.address} Nonce: {nonce}\n\nURI: https://reiki.web3go.xyz\nVersion: 1\nChain ID: 56\nNonce: {nonce}\nIssued At: {timestamp}'

    sign = w3.eth.account.sign_message(encode_defunct(text=message),
                                       private_key=account.key).signature.hex()
    return message, sign


async def web3_challenge(session: ClientSession, account: LocalAccount, nonce: str) -> str:
    url = REIKI_API + "account/web3/web3_challenge"
    message, signature = message_and_sign_message(account, nonce)
    payload = {
        "address": account.address,
        'challenge': json.dumps({'msg': message}),
        'nonce': nonce,
        'signature': signature
    }
    response, data = await request(session, 'POST', url, json=payload)
    token = data['extra']['token']
    logger.success(f'{account.address[:6]} | Bearer token: {token}')
    return token


async def claim_gifts(session: ClientSession, account: LocalAccount) -> None:
    url = REIKI_API + 'gift'
    response, data = await request(session, 'GET', url, params={'type': 'recent'})
    if response.status == 200:
        if data:
            logger.info(f'{account.address[:6]} | Got gifts')
        else:
            logger.success(f'{account.address[:6]} | All gifts are opened')
    else:
        logger.error(f'{account.address[:6]} | {data["message"]}')
    for gift in data:
        gift_id = gift['id']
        gift_name = gift['name']
        if not gift['openedAt']:
            url = REIKI_API + f'gift/open/{gift_id}'
            response, data = await request(session, 'POST', url)
            if data == 'true':
                logger.success(f'{account.address[:6]} | Opened gift - {gift_name}')
            else:
                logger.error(f"{account.address[:6]} | Couldn't open gift - {gift_name}")
        else:
            logger.success(f'{account.address[:6]} | Already opened gift - {gift_name}')


async def claim_daily(session: ClientSession, account: LocalAccount) -> None:
    url = REIKI_API + "checkin/points/his"
    current_date = datetime.now(pytz.utc)
    days_until_monday = current_date.weekday()
    start_of_week = current_date - timedelta(days=days_until_monday)
    end_of_week = start_of_week + timedelta(days=6)
    response, data = await request(session, 'GET', url, params={
        'start': start_of_week.strftime('%Y%m%d'), 'end': end_of_week.strftime('%Y%m%d')
    })
    for day in data:
        if day['date'] == current_date.replace(hour=0, minute=0, second=0, microsecond=0).strftime(
                '%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z':
            if day['status'] != 'checked':
                url = REIKI_API + 'checkin'
                await request(session, 'PUT', url, params={'day': datetime.now().strftime("%Y-%m-%d")})
                logger.success(f'{account.address[:6]} | Daily claimed')
            else:
                logger.success(f"{account.address[:6]} | Daily already claimed")
            break


async def quizes(session: ClientSession, account: LocalAccount) -> None:
    url = REIKI_API + 'quiz'
    response, data = await request(session, 'GET', url)
    qs = random.sample(data, len(data))
    for quiz in qs:
        if quiz['currentProgress'] == quiz['totalItemCount']:
            logger.success(f'{account.address[:6]} | Quiz {quiz["title"]} already completed')
            continue
        quiz_id = quiz['id']
        url = REIKI_API + 'quiz/' + quiz_id
        response, data = await request(session, 'GET', url)
        questions = data['items']
        logger.info(
            f'{account.address[:6]} | Quiz {quiz["title"]}. {quiz["totalItemCount"] - quiz["currentProgress"]} questions left')
        for i, question in enumerate(questions[quiz['currentProgress']:], start=quiz['currentProgress']):
            if quiz_id == '631bb81f-035a-4ad5-8824-e219a7ec5ccb' and i == 0:
                payload = {'answers': [account.address]}
            else:
                payload = {'answers': [QUIZES[quiz_id][i]]}
            question_id = question['id']
            url = REIKI_API + 'quiz/' + question_id + '/answer'
            response, data = await request(session, 'POST', url, json=payload)
            if response.status == 201 or data['message'] == 'Already answered':
                logger.success(f'{account.address[:6]} | {data["message"]}')
            else:
                logger.info(f'{account.address[:6]} | {data["message"]}')


async def connect_email(session: ClientSession, account: LocalAccount, email: str):
    url = REIKI_API + 'profile'
    response, data = await request(session, 'GET', url)
    if data['email']:
        logger.success(f'Email {data["email"]} is already connected')
        return
    response, data = await request(session, 'PATCH', url, json={'email': email, 'name': None})
    if data == 'true':
        logger.success(f'{account.address[:6]} | Email connected')
    else:
        logger.error(f"{account.address[:6]} | Couldn't connect email - {data}")


async def connect_twitter(session: ClientSession, account: LocalAccount, auth_token: str):
    twitter_client = TwitterClient(
        client=TwitterClient(
            account=TwitterAccount(auth_token),
            proxy=str(session.connector.proxy_url),
            verify=False,
        )
    )
    url = REIKI_API + 'oauth/twitter2'
    response, data = await request(session, 'GET', url, follow_redirects=True)
    code = await twitter_client.oauth_2(**response.url.query)


async def connect_discord(session: ClientSession, account: LocalAccount, auth_token: str):
    discord_client = DiscordClient(
        account=DiscordAccount(auth_token),
        proxy=str(session.connector.proxy_url),
        verify=False,
    )
    url = REIKI_API + 'oauth/discord'
    response, data = await request(session, 'GET', url, follow_redirects=True)

    code = await discord_client.bind_app(
        client_id=response.url.query['client_id'],
        scope=response.url.query['scope'],
        state=response.url.query['state'],
    )


async def start_tasks(session: ClientSession, profile: Profile, tasks: bool = False) -> None:
    if tasks:
        all_tasks = [
            claim_daily(session, profile.evm_account),
            claim_gifts(session, profile.evm_account),
            quizes(session, profile.evm_account),
            connect_email(session, profile.evm_account, profile.email),
            # await connect_twitter(session, profile.evm_account, profile.twitter.auth_token),
            # await connect_discord(session, profile.evm_account, profile.discord.auth_token)
        ]
        for task in random.sample(all_tasks, len(all_tasks)):
            await task
    else:
        await claim_daily(session, profile.evm_account)


async def start(profile, choice: int) -> None:
    match choice:
        case 1:
            evm_client = Client(profile.evm_account.key.hex(), BNB)
            evm_client.default_abi = read_json(REIKI_ABI)
            await mint(evm_client)
        case 2 | 3:
            headers['User-Agent'] = profile.user_agent
            connector: ProxyConnector = ProxyConnector.from_url(
                url=Proxy.from_str(proxy=profile.proxy).as_url, verify_ssl=False
            )
            async with ClientSession(connector=connector, headers=headers, trust_env=True) as session:
                token = await get_token_by_address(profile.evm_account.address)
                if token:
                    session.headers['Authorization'] = f'Bearer {token}'
                await me(session, profile.evm_account)
                await start_tasks(session, profile, choice == 2)


async def main():
    print('1. Mint nft')
    print('2. Do tasks')
    print('3. Claim daily')
    choice = int(input())
    await create_table()

    tasks = []
    for profile in get_profiles():
        tasks.append(asyncio.create_task(start(profile, choice)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    asyncio.run(main())
