from typing import TYPE_CHECKING

from aioimaplib.aioimaplib import IMAP4_SSL

if TYPE_CHECKING:
    from web3db import Email

IMAP_SERVERS = {
    'outlook.com': 'outlook.office365.com',
    'hotmail.com': 'outlook.office365.com',
    'rambler.ru': 'imap.rambler.ru',
    'mail.ru': 'imap.mail.ru',
}


class IMAPClient(IMAP4_SSL):
    def __init__(self, email: 'Email' = None, login: str = None, password: str = None):
        self.email = email or Email(0, login, password)
        super().__init__(IMAP_SERVERS[email.login.split('@')[-1]])

    async def __aenter__(self):
        await self.wait_hello_from_server()
        res = await self.login(self.email.login, self.email.password)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.logout()
        await self.close()
