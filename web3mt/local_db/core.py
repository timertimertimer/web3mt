import asyncio
from typing import Union
from sqlalchemy import select
from sqlalchemy.orm import joinedload
from web3db import DBHelper as BaseDBHelper, Proxy, Profile
from web3mt.consts import Web3mtENV
from web3mt.utils import my_logger
from web3mt.utils.webshare import Webshare

ModelType = Union[type(Proxy), type(Profile)]


class DBHelper(BaseDBHelper):
    def __init__(self, url: str = Web3mtENV.LOCAL_CONNECTION_STRING, *args, **kwargs):
        super().__init__(url, *args, **kwargs)

    async def get_proxies_by_string(self, s: str):
        query = select(Proxy).where(Proxy.proxy_string.like(f"%{s}%")).options(joinedload('*'))
        result = await self.execute_query(query)
        return result.scalars().all()

    async def get_profiles_with_shared_proxies(self):
        query = select(Profile).join(Profile.proxy).where(Proxy.proxy_type == 'shared').options(joinedload('*'))
        result = await self.execute_query(query)
        return result.scalars().all()

    async def update_shared_proxies(self):
        ws_proxies = set(await Webshare().proxy_list())
        profiles = await self.get_profiles_with_shared_proxies()
        used_proxies = {profile.proxy.proxy_string for profile in profiles}
        new_proxies = ws_proxies.difference(used_proxies)
        for profile in profiles:
            if profile.proxy.proxy_string not in ws_proxies:
                new_proxy = new_proxies.pop()
                my_logger.info(f'{profile.id} | Changing proxy {profile.proxy.proxy_string} to {new_proxy}')
                profile.proxy.proxy_string = new_proxy
        await self.add_record(profiles)


async def main():
    db = DBHelper(Web3mtENV.LOCAL_CONNECTION_STRING)
    await db.update_shared_proxies()


if __name__ == '__main__':
    asyncio.run(main())
