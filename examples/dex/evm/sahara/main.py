import asyncio
import random
from asyncio import Semaphore

from examples.dex.evm.sahara.client import SaharaClient, SaharaAchievementsClient
from examples.dex.evm.sahara.config import accounts_per_thread, start_delay_random_range
from examples.dex.evm.sahara.db import SaharaAccount
from examples.dex.evm.sahara.utils import data_path, db_helper
from web3mt.config import env
from web3mt.utils import logger, sleep


async def check_wl():
    def get_accounts_from_privates():
        with open(data_path / 'sahara/privates.txt', encoding='utf-8') as file:
            privates = [row.strip() for row in file.readlines()]
        return [SaharaAccount(private=private, proxy=env.rotating_proxy) for private in privates]

    MAX_PARALLEL_TASKS = 8
    semaphore = Semaphore(MAX_PARALLEL_TASKS)

    async def wait_flag(account: SaharaAccount, save_session=False):
        async with semaphore:
            async with SaharaClient(account, save_session=save_session) as client:
                if not client.user_info['waitFlag']:
                    logger.success(f'{client} | Found')

    accounts = get_accounts_from_privates()
    # accounts = await db_helper.get_all_from_table(SaharaAccount)
    await asyncio.gather(*[wait_flag(acc, save_session=False) for acc in accounts])


async def points(account: SaharaAccount):
    async with SaharaClient(account) as client:
        return client.sp


async def points_checker(ids: list[int] = None):
    if not ids:
        accounts = await db_helper.get_all_from_table(SaharaAccount)
    else:
        accounts = await db_helper.get_rows_by_filter(ids, SaharaAccount, SaharaAccount.account_id)
    total = await asyncio.gather(*[points(account) for account in accounts])
    logger.success(f'Total: {sum(total)} SP')


semaphore = Semaphore(accounts_per_thread)


async def do_tasks(account: SaharaAccount, more_than_one_accounts: bool):
    async with semaphore:
        if more_than_one_accounts or accounts_per_thread > 1:
            await sleep(*(start_delay_random_range), log_info=f'{account}', echo=True)
        async with SaharaClient(account, use_rotating_proxy_for_gpt=False) as client:
            if not client:
                return
            await client.do_tasks()
            return client.sp


async def claim_achievements_and_check_level(account: SaharaAccount, more_than_one_accounts: bool):
    async with semaphore:
        if more_than_one_accounts and accounts_per_thread > 1:
            await sleep(*start_delay_random_range, log_info=f'{account}', echo=True)
        async with SaharaAchievementsClient(account, use_rotating_proxy_for_gpt=False) as client:
            if not client:
                return
            await client.claim_and_mint_in_progress_achievements()
            await client.check_level()


async def main():
    accounts = await db_helper.get_rows_by_filter(
        # [115],
        a_1 + a_2 + a_3,
        SaharaAccount, SaharaAccount.account_id
    )
    # accounts: list[SaharaAccount] = await db_helper.get_all_from_table(SaharaAccount)
    random.shuffle(accounts)
    await asyncio.gather(*[claim_achievements_and_check_level(acc, len(accounts) > 1) for acc in accounts])


if __name__ == '__main__':
    a_1 = [226, 227, 229, 262, 263, 265, 266, 268, 269, 274, 277]
    a_2 = [1, 42, 43, 53, 54, 55, 56]
    a_3 = [1111, 111, 115, 142, 144, 192, 197, 201, 203, 221, 225]
    # asyncio.run(points_checker(a_1 + a_2 + a_3))
    asyncio.run(main())
