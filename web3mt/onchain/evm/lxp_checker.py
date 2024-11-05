import asyncio

from web3db import LocalProfile
from web3mt.local_db import DBHelper
from web3mt.onchain.evm.client import Client
from web3mt.onchain.evm.models import Linea, Token, TokenAmount
from web3mt.utils import my_logger, ProfileSession

db = DBHelper()


class Checker:
    lxp_contract_address = '0xd83af4fbD77f3AB65C3B1Dc4B38D7e67AEcf599A'
    lxpl_farmers = [1, 99, 100, 102, 105, 107]

    def __init__(self, profile: LocalProfile):
        self.session = ProfileSession(
            profile,
        )
        self.client = Client(profile, Linea)

    async def get_lxp(self, echo: bool = True) -> TokenAmount:
        return await self.client.balance_of(
            token=Token(Linea, address=self.lxp_contract_address), echo=echo, remove_zero_from_echo=True
        )

    async def get_lxpl(self) -> tuple[int, int, int]:
        _, data = await self.session.get(
            'https://kx58j6x5me.execute-api.us-east-1.amazonaws.com/linea/getUserPointsSearch',
            params={'user': self.client.account.address.lower()}
        )
        data = data[0]
        return data['rank_xp'], data['xp'], data['rp']


async def main():
    profiles = await db.get_all_from_table(LocalProfile)
    res = await asyncio.gather(*[Checker(profile).get_lxp() for profile in profiles])
    my_logger.info(f'Total LXP: {sum(res)}')
    profiles = await db.get_rows_by_id(Checker.lxpl_farmers, LocalProfile)
    res = await asyncio.gather(*[Checker(profile).get_lxpl() for profile in profiles])
    for profile, el in zip(profiles, res):
        my_logger.info(f'{profile.id} | {profile.evm_address} (Linea) | Rank: {el[0]}, Points: {el[1]} LXPL, Referal points: {el[2]} LXPL')
    my_logger.info(f'Total LXPL: {sum([el[1] for el in res])}')


if __name__ == '__main__':
    asyncio.run(main())
