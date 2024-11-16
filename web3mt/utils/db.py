from web3db import DBHelper

from web3mt.offchain.webshare import Webshare
from web3mt.utils import my_logger


async def update_shared_proxies(db_helper: DBHelper):
    ws_proxies = set(await Webshare().proxy_list())
    profiles = await db_helper.get_profiles_with_shared_proxies()
    used_proxies = {profile.proxy.proxy_string for profile in profiles}
    new_proxies = ws_proxies.difference(used_proxies)
    for profile in profiles:
        if profile.proxy.proxy_string not in ws_proxies:
            new_proxy = new_proxies.pop()
            my_logger.info(f'{profile.id} | Changing proxy {profile.proxy.proxy_string} to {new_proxy}')
            profile.proxy.proxy_string = new_proxy
    await db_helper.add_record(profiles)
