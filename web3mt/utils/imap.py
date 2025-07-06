import email
from collections import defaultdict
from email.message import Message
from typing import Iterable
from aioimaplib.aioimaplib import IMAP4_SSL, Abort, CommandTimeout

from web3mt.utils import curl_cffiAsyncSession, sleep, logger
from web3db import Email

IMAP_SERVERS = {
    'outlook.com': 'outlook.office365.com',
    'hotmail.com': 'outlook.office365.com',
    'rambler.ru': 'imap.rambler.ru',
    'mail.ru': 'imap.mail.ru',
    'icloud.com': 'imap.mail.me.com',
    'gmail.com': 'imap.gmail.com',
}


class IMAPClient(IMAP4_SSL):
    def __new__(
            cls, email: Email = None, login: str = None, password: str = None, host: str = None,
            proxy: str | None = None
    ):
        domain = email.login.split('@')[-1]
        if domain == 'gmail.com':
            return super(IMAPClient, GoogleIMAPClient).__new__(GoogleIMAPClient)
        elif domain in ['outlook.com', 'hotmail.com']:
            return super(IMAPClient, MicrosoftIMAPClient).__new__(MicrosoftIMAPClient)
        else:
            return super().__new__(cls)

    def __init__(
            self, email: Email = None, login: str = None, password: str = None, host: str = None,
            proxy: str | None = None
    ):
        self.email = email or Email(login=login, password=password)
        self.proxy = proxy
        self.host = host or IMAP_SERVERS[email.login.split('@')[-1]]
        super().__init__(self.host)

    def __repr__(self):
        return f'{self.email.id if self.email.id else "Main"} | {self.email.login}'

    def __str__(self):
        return repr(self)

    async def __aenter__(self):
        await self.wait_hello_from_server()
        if self.email.refresh_token:
            if not self.email.access_token:
                self.email.access_token = await self._update_access_token()
            while True:
                try:
                    res = await self.xoauth2(self.email.login, self.email.access_token)
                except TimeoutError as e:
                    logger.warning(f"{self} | Timeout when loggin. Sleeping and trying again")
                    await sleep(5, echo=True, log_info=f"{self}")
                    continue
                except Exception as e:
                    logger.error(f"{self} | Failed to login to {self.email.login}: {e}")
                    return
                if res.result == 'OK':
                    break
                elif res.result == 'NO':
                    if res[1][0] == b'AUTHENTICATE failed.':
                        new_access_token = await self._()
                        logger.info(f'{self} | Updated access token for {self.email.login}')
                        self.email.access_token = new_access_token
                    else:
                        logger.error(f"{self} | Failed to login to {self.email.login}")
                        return
                else:
                    logger.error(f"{self} | Failed to login to {self.email.login}")
                    return
        else:
            res = await self.login(self.email.login, self.email.password)
            if res.result == 'NO':
                logger.error(f"{self} | Failed to login to {self.email.login}")
                return
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.logout()

    async def _update_access_token(self):
        raise NotImplementedError

    async def _get_messages_from_folders(self, folders: Iterable[str], limit: int = 10) -> dict[str: list[Message]]:
        messages = defaultdict(list)
        for folder in folders:
            result = None
            try:
                result, data = await self.select(folder)
            except Abort as e:
                pass
            if result != 'OK':
                continue
            if self.host == IMAP_SERVERS['outlook.com']:
                charset = 'US-ASCII'
            elif self.host == IMAP_SERVERS['icloud.com']:
                charset = None
            else:
                charset = 'utf-8'
            result, data = await self.search("ALL", charset=charset)
            if result == 'OK':
                numbers = data[0].split()
                for number_bytes in numbers[-1:len(numbers) - limit - 1:-1]:
                    number = number_bytes.decode('utf-8')
                    while True:
                        try:
                            result, data = await self.fetch(
                                number, '(BODY.PEEK[])' if self.host == IMAP_SERVERS['icloud.com'] else '(RFC822)'
                            )
                            break
                        except (TimeoutError, CommandTimeout) as e:
                            logger.warning(f"{self} | Timeout when fetching message. Sleeping and trying again")
                            await sleep(5, echo=True, log_info=f"{self}")
                            continue
                    if result == 'OK':
                        message = email.message_from_bytes(data[1])
                        messages[folder].append(message)
            else:
                pass
        return messages

    async def get_inbox_messages(self, limit: int = 10) -> list[Message]:
        return (await self._get_messages_from_folders(['INBOX'], limit))['INBOX']


class MicrosoftIMAPClient(IMAPClient):
    async def _update_access_token(self) -> str:
        try:
            async with curl_cffiAsyncSession(
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}, proxy=self.proxy
            ) as session:
                _, data = await session.post(url="https://login.microsoftonline.com/common/oauth2/v2.0/token", data={
                    'client_id': self.email.client_id,
                    'refresh_token': self.email.refresh_token,
                    'grant_type': 'refresh_token',
                })
                return data['access_token']
        except Exception as error:
            logger.error(f"{self} | Failed to retrieve Microsoft access token for {self.email.login}: {error}")
            raise


class GoogleIMAPClient(IMAPClient):
    async def _update_access_token(self) -> str:
        try:
            async with curl_cffiAsyncSession(
                    headers={'Content-Type': 'application/x-www-form-urlencoded'}, proxy=self.proxy
            ) as session:
                _, data = await session.post(url="https://oauth2.googleapis.com/token", data={
                    'client_id': self.email.client_id,
                    'client_secret': self.email.client_secret,
                    'refresh_token': self.email.refresh_token,
                    'grant_type': 'refresh_token',
                })
                return data['access_token']
        except Exception as error:
            logger.error(f"{self} | Failed to retrieve Google access token for {self.email.login}: {error}")
            raise
