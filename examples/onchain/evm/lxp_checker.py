import asyncio

from web3db import Profile, DBHelper

from web3mt.config import env
from web3mt.onchain.evm.client import ProfileClient
from web3mt.onchain.evm.models import Linea, Token, TokenAmount
from web3mt.utils import logger, Profilecurl_cffiAsyncSession

db = DBHelper(env.LOCAL_CONNECTION_STRING)


class Checker:
    lxp_contract_address = '0xd83af4fbD77f3AB65C3B1Dc4B38D7e67AEcf599A'
    lxpl_farmers = [1, 99, 100, 102, 105, 107]

    def __init__(self, profile: Profile):
        self.session = Profilecurl_cffiAsyncSession(profile)
        self.client = ProfileClient(profile, Linea)

    async def get_lxp(self, echo: bool = True) -> TokenAmount:
        return await self.client.balance_of(
            token=Token(Linea, address=self.lxp_contract_address), echo=echo, remove_zero_from_echo=True
        )

    async def get_lxpl(self) -> tuple[int, int, int] | None:
        _, data = await self.session.get(
            'https://kx58j6x5me.execute-api.us-east-1.amazonaws.com/linea/getUserPointsSearch',
            params={'user': self.client.account.address.lower()}
        )
        if not data:
            return
        data = data[0]
        return data['rank_xp'], data['xp'], data['rp']


async def change_proxy(profile: Profile):
    checker = Checker(profile)
    if not await checker.session.check_proxy(retry_count=0):
        checker.session.proxies['all'] = env.default_proxy
        checker.client.proxy = env.default_proxy
    return checker


async def main():
    profiles = await db.get_rows_by_id([1, 99, 100, 102, 105, 107, 108, 113], Profile)
    checkers = await asyncio.gather(*[change_proxy(profile) for profile in profiles])
    res = await asyncio.gather(*[checker.get_lxp() for checker in checkers])
    logger.info(f'Total LXP: {sum(res)}')
    profiles = await db.get_rows_by_id(Checker.lxpl_farmers, Profile)
    res = await asyncio.gather(*[checker.get_lxpl() for checker in checkers])
    ans = 0
    for profile, el in zip(profiles, res):
        if el:
            logger.info(
                f'{profile.id} | {profile.evm_address} (Linea) | '
                f'Rank: {el[0]}, Points: {el[1]} LXPL, Referal points: {el[2]} LXPL'
            )
            ans += el[1] or 0
    logger.info(f'Total LXPL: {ans}')


if __name__ == '__main__':
    asyncio.run(main())
