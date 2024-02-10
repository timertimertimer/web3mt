import asyncio
import os

import datetime
import json
import random

from datetime import datetime, timezone, timedelta

from dotenv import load_dotenv

from aiohttp.client_exceptions import ClientResponseError, ClientConnectionError
from better_automation.twitter import TwitterClient, TwitterAccount

from eth_account import Account
from eth_account.messages import encode_defunct
from web3.auto import w3
from web3db import DBHelper
from web3db.models import Profile
from web3db.utils import decrypt, DEFAULT_UA

from evm.client import Client
from evm.config import REIKI_ABI_PATH
from evm.reiki import mint
from web2.reiki.db import *
from web2.reiki.config import *
from web2.utils import *

from utils import logger, read_json, ProfileSession
from evm.models import BNB
from web2.models import DiscordAccountModified

load_dotenv()


class Reiki:
    def __init__(self, profile: Profile):
        headers['User-Agent'] = DEFAULT_UA
        self.session = ProfileSession(profile)
        self.evm_account = Account.from_key(decrypt(profile.evm_private, os.getenv('PASSPHRASE')))
        if not self.evm_account:
            logger.error("Couldn't decrypt private", id=profile.id)
        self.profile = profile

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        logger.success('Tasks completed', id=self.profile.id)
        await self.session.connector.close()
        await self.session.close()

    async def start_tasks(self, tasks: bool = False) -> None:
        if tasks:
            response, data = await self.profile_()
            if not data['referrerWalletAddress']:
                await self.refer()
            else:
                logger.success(f'Already referred by {data["referrerWalletAddress"]}', id=self.profile.id)
            await self.claim_gifts()
            all_tasks = [
                self.claim_daily(),
                self.quizes(),
                self.connect_socials()
            ]
            for task in random.sample(all_tasks, len(all_tasks)):
                await task
        else:
            await self.claim_daily()

    async def me(self):
        url = 'https://reiki.web3go.xyz/api/GoldLeaf/me'
        while True:
            try:
                response, data = await self.session.request(method='GET', url=url)
                response.raise_for_status()
                logger.success(
                    f'Points: today - {data["today"] if "today" in data else 0}, '
                    f'total - {data["total"] if "total" in data else 0}',
                    id=self.profile.id
                )
                return
            except ClientResponseError as e:
                await self.create_bearer_token()

    async def create_bearer_token(self):
        nonce = await self.web3_nonce()
        token = await self.web3_challenge(nonce)
        await insert_record(self.evm_account.address, token)
        self.session.headers['Authorization'] = f'Bearer {token}'

    async def web3_nonce(self) -> str:
        url = REIKI_API + "account/web3/web3_nonce"
        payload = {
            "address": self.evm_account.address
        }
        response, data = await self.session.request(method='POST', url=url, json=payload)
        nonce = data['nonce']
        logger.success(f'Nonce: {nonce}', id=self.profile.id)
        return nonce

    async def web3_challenge(self, nonce: str) -> str:
        url = REIKI_API + "account/web3/web3_challenge"
        message, signature = self.message_and_sign_message(nonce)
        payload = {
            "address": self.evm_account.address,
            'challenge': json.dumps({'msg': message}),
            'nonce': nonce,
            'signature': signature
        }
        response, data = await self.session.request(method='POST', url=url, json=payload)
        token = data['extra']['token']
        logger.success(f'Bearer token: {token}', id=self.profile.id)
        return token

    def message_and_sign_message(self, nonce: str) -> tuple[str, str]:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        message = f'reiki.web3go.xyz wants you to sign in with your Ethereum account:\n{self.evm_account.address}\n\nWelcome to Web3Go! Click to sign in and accept the Web3Go Terms of Service. This request will not trigger any blockchain transaction or cost any gas fees. Your authentication status will reset after 7 days. Wallet address: {self.evm_account.address} Nonce: {nonce}\n\nURI: https://reiki.web3go.xyz\nVersion: 1\nChain ID: 56\nNonce: {nonce}\nIssued At: {timestamp}'

        sign = w3.eth.account.sign_message(encode_defunct(text=message),
                                           private_key=self.evm_account.key).signature.hex()
        return message, sign

    async def refer(self):
        url = REIKI_API + 'nft/sync'
        referal_code = os.getenv('REIKI_REFERAL_CODE')
        self.session.headers['X-Referral-Code'] = referal_code
        response, data = await self.session.request(method='GET', url=url)
        if data['msg'] == 'success':
            logger.success("Refered by {referal_code}", id=self.profile.id)
        else:
            logger.error(data, id=self.profile.id)

    async def claim_gifts(self) -> None:
        url = REIKI_API + 'gift'
        response, data = await self.session.request(method='GET', url=url, params={'type': 'recent'})
        if response.status == 200:
            if data:
                logger.info(f'Got gifts', id=self.profile.id)
            else:
                logger.success(f'All gifts are opened', id=self.profile.id)
        else:
            logger.error(f'{data["message"]}', id=self.profile.id)
        for gift in data:
            gift_id = gift['id']
            gift_name = gift['name']
            if not gift['openedAt']:
                url = REIKI_API + f'gift/open/{gift_id}'
                response, data = await self.session.request(method='POST', url=url)
                if data == 'true':
                    logger.success(f'Opened gift - {gift_name}', id=self.profile.id)
                else:
                    logger.error("Couldn't open gift - {gift_name}", id=self.profile.id)
            else:
                logger.success(f'Already opened gift - {gift_name}', id=self.profile.id)

    async def claim_daily(self) -> None:
        url = REIKI_API + "checkin/points/his"
        current_date = datetime.now(timezone.utc)
        days_until_monday = current_date.weekday()
        start_of_week = current_date - timedelta(days=days_until_monday)
        end_of_week = start_of_week + timedelta(days=6)
        response, data = await self.session.request(
            method='GET',
            url=url,
            params={'start': start_of_week.strftime('%Y%m%d'), 'end': end_of_week.strftime('%Y%m%d')}
        )
        for day in data:
            if day['date'] == current_date.replace(hour=0, minute=0, second=0, microsecond=0).strftime(
                    '%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z':
                if day['status'] != 'checked':
                    url = REIKI_API + 'checkin'
                    await self.session.request(
                        method='PUT', url=url, params={'day': datetime.now().strftime("%Y-%m-%d")}
                    )
                    logger.success(f'Daily claimed', id=self.profile.id)
                else:
                    logger.success("Daily already claimed", id=self.profile.id)
                break

    async def quizes(self) -> None:
        url = REIKI_API + 'quiz'
        while True:
            try:
                response, data = await self.session.request(method='GET', url=url)
                break
            except ClientResponseError as e:
                logger.error(f'{url} {e.message}', id=self.profile.id)
                if e.status == 401:
                    await self.create_bearer_token()
                else:
                    return
        qs = random.sample(data, len(data))
        for quiz in qs:
            if quiz['currentProgress'] == quiz['totalItemCount']:
                logger.success(f'Quiz {quiz["title"]} already completed', id=self.profile.id)
                continue
            quiz_id = quiz['id']
            url = REIKI_API + 'quiz/' + quiz_id
            response, data = await self.session.request(method='GET', url=url)
            questions = data['items']
            logger.info(
                f'Quiz {quiz["title"]}. {quiz["totalItemCount"] - quiz["currentProgress"]} questions left',
                id=self.profile.id
            )
            for i, question in enumerate(questions[quiz['currentProgress']:], start=quiz['currentProgress']):
                if quiz_id == '631bb81f-035a-4ad5-8824-e219a7ec5ccb' and i == 0:
                    payload = {'answers': [self.evm_account.address]}
                else:
                    payload = {'answers': [QUIZES[quiz_id][i]]}
                question_id = question['id']
                url = REIKI_API + 'quiz/' + question_id + '/answer'
                response, data = await self.session.request(method='POST', url=url, json=payload)
                if response.status == 201 or data['message'] == 'Already answered':
                    logger.success(data["message"], id=self.profile.id)
                else:
                    logger.info(data["message"], id=self.profile.id)

    async def profile_(self):
        url = REIKI_API + 'profile'
        return await self.session.request(method='GET', url=url)

    async def connect_socials(self):
        response, data = await self.profile_()
        social_tasks = {
            'email': self.connect_email,
            'twitter': self.connect_twitter,
            'discord': self.connect_discord
        }
        if data['email'] == self.profile.email.login:
            logger.success(f'Email {data["email"]} already connected', id=self.profile.id)
            social_tasks.pop('email')
        for social in data['socials']:
            social_tasks.pop(social['type'])
            logger.success(f'{social["type"].capitalize()} already connected', id=self.profile.id)
        for task in social_tasks:
            await social_tasks[task]()

    async def connect_email(self):
        url = REIKI_API + 'profile'
        response, data = await self.session.request(
            method='PATCH', url=url, json={'email': self.profile.email.login, 'name': None}
        )
        if data == 'true':
            logger.success(f'Email connected', id=self.profile.id)
        else:
            logger.error("Couldn't connect email - {data}", id=self.profile.id)

    async def connect_twitter(self) -> bool:
        url = REIKI_API + 'oauth/twitter2/'
        try:
            response, data = await self.session.request(method='GET', url=url, follow_redirects=True)
        except ClientResponseError as e:
            logger.error(f'{url} {e.message}', id=self.profile.id)
            return False
        payload = {**response.url.query}
        payload.pop('nonce')
        code = await TwitterClient(
            account=TwitterAccount(self.profile.twitter.auth_token),
            proxy=str(self.session.connector.proxy_url),
            verify=False,
        ).oauth_2(**payload)
        await self.callback(url, code, response.url.query['state'])
        return True

    async def connect_discord(self):
        url = REIKI_API + 'oauth/discord/'
        try:
            response, data = await self.session.request(method='GET', url=url, follow_redirects=True)
        except ClientResponseError as e:
            logger.error(f'{url} {e.message}', id=self.profile.id)
            return False
        payload = {**response.url.query}
        payload.pop('nonce')
        code = await DiscordClientModified(
            account=DiscordAccountModified(self.profile.discord.auth_token),
            proxy=str(self.session.connector.proxy_url),
            verify=False
        ).oauth_2(**payload)
        await self.callback(url, code, response.url.query['state'])

    async def callback(self, url: str, code: str, state: str):
        url += 'callback'
        response, data = await self.session.request(
            method='GET',
            url=url,
            params={'code': code, 'state': state},
            follow_redirects=True
        )
        if response.url.query.get('success') == 'true':
            logger.success(f"{url} connected", id=self.profile.id)
        else:
            logger.error(response.url, id=self.profile.id)


async def start(profile, choice: int) -> None:
    async with Reiki(profile) as reiki:
        token = await get_token_by_address(reiki.evm_account.address)
        if token:
            reiki.session.headers['Authorization'] = f'Bearer {token}'
        client = Client(reiki.evm_account, BNB)
        client.default_abi = read_json(REIKI_ABI_PATH)
        if not await mint(client):
            return
        await reiki.me()
        await reiki.start_tasks(choice == 1)


async def main():
    print('1. Do tasks')
    print('2. Claim daily')
    choice = int(input())
    await create_table()

    tasks = []
    profiles = await get_profiles(random_proxy_distinct=True, limit=1)
    for profile in profiles:
        tasks.append(asyncio.create_task(start(profile, choice)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
