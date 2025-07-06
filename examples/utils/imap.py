import asyncio
from asyncio import Semaphore
from email.header import decode_header
from email.utils import parsedate_to_datetime
from mailbox import Message

import chardet
from web3db import Email, Profile

from web3mt.utils import IMAPClient
from web3mt.config import env
from web3mt.utils.db import create_db_instance
from web3mt.utils.logger import logger


def parse_message(message: Message):
    subject, encoding = decode_header(message["Subject"])[0]
    if isinstance(subject, bytes):
        subject = subject.decode(encoding if encoding else "utf-8")
    from_ = message.get("From")
    to_ = message.get("To")
    date_ = message.get("Date")
    if date_:
        date_ = parsedate_to_datetime(date_)
    print("=" * 50)
    print(f"Subject: {subject}")
    print(f"From: {from_}")
    print(f"To: {to_}")
    print(f"Date: {date_}")
    print("=" * 50)
    if message.is_multipart():
        for part in message.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))
            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    body = part.get_payload(decode=True)
                    possible_encoding = chardet.detect(body)
                    detected_encoding = 'utf-8' if possible_encoding['confidence'] < 0.8 else possible_encoding["encoding"]
                    body = body.decode(detected_encoding)
                    if 'Congratulations' in body:
                        pass
                    print(f"Body:\n{body}")
                except Exception as e:
                    print(f"Ошибка при декодировании тела письма: {e}")
    else:
        try:
            body = message.get_payload(decode=True)
            possible_encoding = chardet.detect(body)
            detected_encoding = 'utf-8' if possible_encoding['confidence'] < 0.8 else possible_encoding["encoding"]
            body = body.decode(detected_encoding)
            print(f"Body:\n{body}")
        except Exception as e:
            print(f"Ошибка при декодировании тела письма: {e}")

    print("=" * 50)


MAX_PARALLEL_TASKS = 8
semaphore = Semaphore(MAX_PARALLEL_TASKS)
db = create_db_instance()


async def find_sahara(email: Email):
    async with semaphore:
        async with IMAPClient(email, env.rotating_proxy) as client:
            messages = await client.get_inbox_messages()
            await db.edit(email)
        for message in messages:
            if 'Sahara AI' in message['From'] and 'Whitelist' in message['Subject']:
                parse_message(message)
                break
            else:
                logger.info(f'{client} | Nothing. Message from {message["From"]}, {message["Subject"]}')


async def print_last_messages(profile: Profile):
    access_token = profile.email.access_token
    async with IMAPClient(profile.email, proxy=profile.proxy.proxy_string) as client:
        messages = await client.get_inbox_messages()
    for message in messages:
        parse_message(message)
    if access_token != profile.email.access_token:
        await db.edit(profile.email)


async def main():
    profiles: list[Profile] = await db.get_rows_by_id([1], Profile)
    await asyncio.gather(*[print_last_messages(profile) for profile in profiles])


if __name__ == '__main__':
    asyncio.run(main())
