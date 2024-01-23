import os

from web3db.core import DBHelper
from dotenv import load_dotenv
from web3db.models import Profile

load_dotenv()


async def get_profiles(random_proxy_distinct: bool = False, limit: int = None):
    db = DBHelper(os.getenv('CONNECTION_STRING'))
    if random_proxy_distinct:
        return await db.get_random_profiles_by_proxy_distinct(limit)
    return await db.get_all_from_table(Profile, limit)
