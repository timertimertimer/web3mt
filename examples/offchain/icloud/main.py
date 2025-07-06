import asyncio
from datetime import timedelta

from sqlalchemy import select, desc

from examples.offchain.icloud.model import CONNECTION_STRING, IcloudEmail
from web3mt.utils import curl_cffiAsyncSession, sleep
from web3mt.utils.db import create_db_instance
from web3mt.utils.logger import logger

with open('cookies.txt', encoding='utf-8') as file:
    cookie_str = file.read().strip()
cookies = dict()
for cookie in cookie_str.split(';'):
    if cookie:
        name, value = cookie.split('=', maxsplit=1)
        cookies[name] = value
db = create_db_instance(CONNECTION_STRING)


class Icloud:
    base_url_v1 = "https://p68-maildomainws.icloud.com/v1/hme"
    base_url_v2 = "https://p68-maildomainws.icloud.com/v2/hme"
    params = {
        "clientBuildNumber": "2317Project38",
        "clientMasteringNumber": "2317B22",
        "clientId": "",
        "dsid": "",
    }

    def __init__(self):
        self.session = curl_cffiAsyncSession()
        self.session.cookies.update(cookies)
        self.session.headers.update({'Origin': 'https://www.icloud.com'})

    async def get_emails(self):
        _, data = await self.session.get(f'{self.base_url_v2}/list', params=self.params)
        if not (data := data.get('result')):
            return
        return [{email_data['label']: email_data['hme']} for email_data in data['hmeEmails']]

    async def reserve_email(self, label: int):
        new_email = await self.generate_email()
        _, data = await self.session.post(
            f'{self.base_url_v1}/reserve', params=self.params, json=dict(hme=new_email, label=str(label), note='')
        )
        if not (data.get('result')):
            logger.warning(f'Failed to reserve email {new_email}. {data.get("error", {}).get("errorMessage")}')
            return
        data = data['result']
        return IcloudEmail(label=int(label), login=data['hme']['hme'])

    async def generate_email(self):
        _, data = await self.session.post(
            f'{self.base_url_v1}/generate', params=self.params, json=dict(langCode="en-us")
        )
        if not (data := data.get('result')):
            return
        return data['hme']


async def start_generator():
    last_email = (await db.execute_query(select(IcloudEmail).order_by(desc(IcloudEmail.label)))).scalar()
    last_label = last_email.label + 1
    icloud = Icloud()
    while True:
        for _ in range(5):
            new_email = await icloud.reserve_email(last_label)
            if new_email:
                await db.add_record(new_email)
                last_label += 1
            await sleep(5, echo=True)
        await sleep(time_delta=timedelta(hours=1, minutes=1), echo=True)


async def save_emails(emails: list[dict]):
    records = []
    for email in emails:
        label, login = list(email.items())[0]
        if not await db.get_row_by_login(login=login, model=IcloudEmail):
            records.append(IcloudEmail(label=label, login=login))
    await db.add_record(records)


async def main():
    icloud = Icloud()
    emails = await icloud.get_emails()
    await save_emails(emails)


if __name__ == '__main__':
    asyncio.run(main())
