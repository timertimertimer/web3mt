from aioimaplib.aioimaplib import IMAP4_SSL
from web3db import Profile, Email

IMAP_SERVERS = {
    'outlook.com': 'imap-mail.outlook.com',
    'hotmail.com': 'imap-mail.outlook.com',
    'rambler.ru': 'imap.rambler.ru',
    'mail.ru': 'imap.mail.ru',
}


class IMAPClient(IMAP4_SSL):
    def __init__(self, profile: Profile, email: Email):
        self.email = email
        super().__init__(IMAP_SERVERS[email.login.split('@')[-1]])

    async def __aenter__(self):
        await self.wait_hello_from_server()
        await self.login(self.email.login, self.email.password)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
