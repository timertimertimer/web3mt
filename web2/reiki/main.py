import asyncio
import os

import datetime
import json
import random

from datetime import datetime, timezone, timedelta

from curl_cffi.requests import RequestsError
from dotenv import load_dotenv

from twitter import Client as TwitterClient, Account as TwitterAccount
from twitter.errors import Forbidden, BadToken
from discord import Client as DiscordClient, HTTPException

from eth_account import Account
from eth_account.messages import encode_defunct
from web3.auto import w3
from web3db import DBHelper
from web3db.models import Profile
from web3db.utils import decrypt, DEFAULT_UA

from evm.reiki import mint
from web2.reiki.db import *
from web2.reiki.config import *
from web2.reiki.db import update_total_points

from utils import logger, ProfileSession

load_dotenv()


class Reiki:
    def __init__(self, profile: Profile):
        headers['User-Agent'] = DEFAULT_UA
        self.session = ProfileSession(profile)
        self.profile = profile

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if exc_type:
            logger.error(exc_val)
        else:
            logger.success(f'{self.profile.id} | Tasks completed')
        self.session.close()

    async def start_tasks(self, choice: int) -> None:
        if choice == 1:
            response, data = await self.profile_()
            if not data['referrerWalletAddress']:
                await self.refer()
            else:
                logger.success(f'{self.profile.id} | Already referred by {data["referrerWalletAddress"]}')
            await self.claim_gifts()
            all_tasks = [
                self.claim_daily(),
                self.quizzes(),
                self.connect_socials()
            ]
            for task in random.sample(all_tasks, len(all_tasks)):
                await task
        elif choice == 2:
            await self.claim_daily()
        else:
            await self.try_lottery()

    async def me(self) -> float:
        url = 'https://reiki.web3go.xyz/api/GoldLeaf/me'
        while True:
            try:
                response, data = await self.session.request(method='GET', url=url)
                response.raise_for_status()
                total = data["total"] if "total" in data else 0
                today = data["today"] if "today" in data else 0
                logger.success(f'{self.profile.id} | Points: today/total - {today}/{total}')
                await update_total_points(self.profile.id, total)
                return total
            except RequestsError:
                await self.create_bearer_token()

    async def create_bearer_token(self):
        nonce = await self.web3_nonce()
        token = await self.web3_challenge(nonce)
        await insert_record(self.profile.id, token)
        self.session.headers['Authorization'] = f'Bearer {token}'

    async def web3_nonce(self) -> str:
        url = REIKI_API + "account/web3/web3_nonce"
        payload = {
            "address": self.profile.evm_address
        }
        response, data = await self.session.request(method='POST', url=url, json=payload)
        nonce = data['nonce']
        logger.success(f'{self.profile.id} | Nonce: {nonce}')
        return nonce

    async def web3_challenge(self, nonce: str) -> str:
        url = REIKI_API + "account/web3/web3_challenge"
        message, signature = self.message_and_sign_message(nonce)
        payload = {
            "address": self.profile.evm_address,
            'challenge': json.dumps({'msg': message}),
            'nonce': nonce,
            'signature': signature
        }
        response, data = await self.session.request(method='POST', url=url, json=payload)
        token = data['extra']['token']
        logger.success(f'{self.profile.id} | Bearer token: {token}')
        return token

    def message_and_sign_message(self, nonce: str) -> tuple[str, str]:
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        message = (
            f'reiki.web3go.xyz wants you to sign in with your Ethereum account:\n{self.profile.evm_address}\n\n'
            f'Welcome to Web3Go! Click to sign in and accept the Web3Go Terms of Service. This request will not'
            f' trigger any blockchain transaction or cost any gas fees. Your authentication status will reset'
            f' after 7 days. Wallet address: {self.profile.evm_address} Nonce: {nonce}\n\n'
            f'URI: https://reiki.web3go.xyz\nVersion: 1\nChain ID: 56\nNonce: {nonce}\nIssued At: {timestamp}'
        )

        sign = w3.eth.account.sign_message(
            encode_defunct(text=message),
            private_key=Account.from_key(decrypt(self.profile.evm_private, os.getenv('PASSPHRASE'))).key.hex()
        ).signature.hex()
        return message, sign

    async def refer(self):
        url = REIKI_API + 'nft/sync'
        referral_code = os.getenv('REIKI_REFERAL_CODE')
        self.session.headers['X-Referral-Code'] = referral_code
        response, data = await self.session.request(method='GET', url=url)
        if data['msg'] == 'success':
            logger.success(f"{self.profile.id} | Referred by {referral_code}")
        else:
            logger.error(f'{self.profile.id} | {data}')

    async def claim_gifts(self) -> None:
        url = REIKI_API + 'gift'
        response, data = await self.session.request(method='GET', url=url, params={'type': 'recent'})
        if response.status_code == 200:
            if data:
                logger.info(f'{self.profile.id} | Got gifts')
            else:
                logger.success(f'{self.profile.id} | All gifts are opened')
        else:
            logger.error(f'{self.profile.id} | {data["message"]}')
        for gift in data:
            gift_id = gift['id']
            gift_name = gift['name']
            if not gift['openedAt']:
                url = REIKI_API + f'gift/open/{gift_id}'
                response, data = await self.session.request(method='POST', url=url)
                if data == 'true':
                    logger.success(f'{self.profile.id} | Opened gift - {gift_name}')
                else:
                    logger.error(f"{self.profile.id} | Couldn't open gift - {gift_name}")
            else:
                logger.success(f'{self.profile.id} | Already opened gift - {gift_name}')

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
                    logger.success(f'{self.profile.id} | Daily claimed')
                else:
                    logger.success(f"{self.profile.id} | Daily already claimed")
                break

    async def quizzes(self) -> None:
        url = REIKI_API + 'quiz'
        while True:
            try:
                response, data = await self.session.request(method='GET', url=url)
                break
            except RequestsError as e:
                logger.error(f'{self.profile.id} | {url} {e.message}')
                if e.status == 401:
                    await self.create_bearer_token()
                else:
                    return
        qs = random.sample(data, len(data))
        for quiz in qs:
            if quiz['currentProgress'] == quiz['totalItemCount']:
                logger.success(f'{self.profile.id} | Quiz {quiz["title"]} already completed')
                continue
            quiz_id = quiz['id']
            url = REIKI_API + 'quiz/' + quiz_id
            response, data = await self.session.request(method='GET', url=url)
            questions = data['items']
            logger.info(
                f'{self.profile.id} | Quiz {quiz["title"]}. {quiz["totalItemCount"] - quiz["currentProgress"]} '
                f'questions left'
            )
            for i, question in enumerate(questions[quiz['currentProgress']:], start=quiz['currentProgress']):
                if quiz_id == '631bb81f-035a-4ad5-8824-e219a7ec5ccb' and i == 0:
                    payload = {'answers': [self.profile.evm_address]}
                else:
                    payload = {'answers': [QUIZZES[quiz_id][i]]}
                question_id = question['id']
                url = REIKI_API + 'quiz/' + question_id + '/answer'
                response, data = await self.session.request(method='POST', url=url, json=payload)
                if response.status_code == 201 or data['message'] == 'Already answered':
                    logger.success(f'{self.profile.id} | {data["message"]}')
                else:
                    logger.info(f'{self.profile.id} | {data["message"]}')

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
            logger.success(f'{self.profile.id} | Email {data["email"]} already connected')
            social_tasks.pop('email')
        for social in data['socials']:
            social_tasks.pop(social['type'])
            logger.success(f'{self.profile.id} | {social["type"].capitalize()} already connected')
        for task in social_tasks:
            await social_tasks[task]()

    async def connect_email(self):
        url = REIKI_API + 'profile'
        response, data = await self.session.request(
            method='PATCH', url=url, json={'email': self.profile.email.login, 'name': None}
        )
        if data == 'true':
            logger.success(f'{self.profile.id} | Email connected')
        else:
            logger.warning(f"{self.profile.id} | Couldn't connect email - {data}")

    async def connect_twitter(self) -> bool:
        if not self.profile.twitter.ready:
            logger.warning(f'{self.profile.id} | Twitter is not ready, skipping')
            return False
        url = REIKI_API + 'oauth/twitter2/'
        try:
            response, data = await self.session.request(method='GET', url=url, follow_redirects=True)
        except RequestsError as e:
            logger.error(f'{self.profile.id} | {url} {e.message}')
            return False
        payload = {}
        for el in response.url.split('authorize?')[-1].split('&'):
            k, v = el.split('=')
            payload[k] = v
        payload.pop('nonce')
        client = TwitterClient(
            account=TwitterAccount(auth_token=self.profile.twitter.auth_token.strip()),
            proxy=str(self.session.proxies['all']),
            verify=False,
        )
        try:
            code = await client.oauth_2(**payload)
        except (Forbidden, BadToken) as e:
            logger.warning(
                f'{self.profile.id} | Couldn\'t connect twitter. Account status {client.account.status}'
            )
            return False
        await self.callback(url, code, payload['state'])
        return True

    async def connect_discord(self):
        url = REIKI_API + 'oauth/discord/'
        try:
            response, data = await self.session.request(method='GET', url=url, follow_redirects=True)
        except RequestsError as e:
            logger.error(f'{self.profile.id} | {url} {e.message}')
            return False
        payload = {
            'redirect_uri': 'https://reiki.web3go.xyz/api/oauth/discord/callback',
            'scopes': ['identify', 'connections', 'guilds']
        }
        application_id = None
        for el in response.url.split('authorize?')[-1].split('&'):
            k, v = el.split('=')
            if k == 'client_id':
                application_id = v
            elif k not in ['nonce', 'scope'] and k not in payload:
                payload[k] = v
        try:
            async with DiscordClient(proxy=self.profile.proxy.proxy_string) as client:
                code = await client.create_authorization(application_id, **payload)
        except HTTPException as e:
            logger.warning(f'{self.profile.id} | Discord token not valid, can\'t get oauth code')
            return
        await self.callback(url, code, payload['state'])

    async def callback(self, url: str, code: str, state: str):
        url += 'callback'
        response, data = await self.session.request(
            method='GET',
            url=url,
            params={'code': code, 'state': state},
            follow_redirects=True
        )
        if response.url.query.get('success') == 'true':
            logger.success(f"{self.profile.id} | {url} connected")
        else:
            logger.error(f"{self.profile.id} | {response.url}")

    async def try_lottery(self):
        url = REIKI_API + 'lottery/'
        while True:
            response, data = await self.session.request(method='GET', url=url + 'offchain')
            chip_num, piece_num, user_gold_leaf_count = data['chipNum'], data['pieceNum'], data['userGoldLeafCount']
            logger.info(
                f'{self.profile.id} | Lottery status: Chips/Pieces - {chip_num}/{piece_num}. '
                f'Gold leafs left - {user_gold_leaf_count}'
            )
            if user_gold_leaf_count < 2000:
                await update_total_points(self.profile.id, user_gold_leaf_count)
                await update_chips(self.profile.id, chip_num, piece_num)
                break
            response, data = await self.session.request(method='POST', url=url + 'try')
            logger.success(f"{self.profile.id} | Prize: {data['prize']}")


async def start(profile, choice: int) -> None:
    async with Reiki(profile) as reiki:
        if not await mint(profile):
            return
        token = await get_token(reiki.profile.id)
        if token:
            reiki.session.headers['Authorization'] = f'Bearer {token}'
        await reiki.me()
        await reiki.claim_daily()
        await reiki.try_lottery()
        if choice == 1:
            await reiki.start_tasks(choice)
        await reiki.me()


async def main():
    choice = int(input('1. Do tasks\n2. Claim daily'))
    await create_table()

    tasks = []
    db = DBHelper(os.getenv('CONNECTION_STRING'))
    profiles = await db.get_all_from_table(Profile)
    for profile in profiles:
        tasks.append(asyncio.create_task(start(profile, choice)))
    await asyncio.gather(*tasks)


if __name__ == '__main__':
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        pass
