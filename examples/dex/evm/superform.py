import asyncio

from web3db import Profile

from web3mt.local_db import DBHelper
from web3mt.onchain.evm.client import Client
from web3mt.onchain.evm.models import Base, TokenAmount
from web3mt.utils import my_logger, ProfileSession


class Superform:
    API_URL = 'https://api.superform.xyz/'

    def __init__(self, profile: Profile):
        self.client = Client(chain=Base, profile=profile)
        self.session = ProfileSession(profile, headers={'Sf-Api-Key': 'a1c6494d30851c65cdb8cb047fdd'})

    async def __aenter__(self):
        if await self.session.check_proxy():
            return self

    async def __aexit__(self, exc_type, exc_val, exc_tb=None):
        if exc_type:
            my_logger.error(f'{self.client.log_info} | {exc_val or exc_type}')
        else:
            my_logger.success(f'{self.client.log_info} | Tasks done')

    async def mint_superfrens(self):
        tournaments_ids = [int(tournament['id']) for tournament in await self._get_tournaments()]
        tournaments_rewards = await asyncio.gather(*[
            self.session.get(self.API_URL + f'superrewards/rewards/{tournament_id}/{str(self.client.account.address)}')
            for tournament_id in tournaments_ids
        ])
        for tournament_id, tournament in zip(tournaments_ids, tournaments_rewards):
            _, data = tournament
            if any([tier['status'] == 'claimable' for tier in data]):
                await self.mint_all_rewards(tournament_id)

    async def _get_tournaments(self) -> list:
        return (await self.session.get(self.API_URL + 'superrewards/tournaments'))[1]

    async def mint_all_rewards(self, tournament_id: int):
        _, data = await self.session.post(
            'https://api.superform.xyz/superrewards/start/claim',
            json={'tournamentID': tournament_id, 'user': str(self.client.account.address)}
        )
        await self.client.tx(
            data['to'], f'Mint All Rewards of {tournament_id} tournament', data['transactionData'],
            value=TokenAmount(data['value'], True, self.client.chain.native_token)
        )


async def start(profile: Profile):
    async with Superform(profile) as sf:
        if not sf:
            return
        await sf.mint_superfrens()


async def main():
    db = DBHelper()
    profiles: list[Profile] = await db.get_all_from_table(Profile)
    await asyncio.gather(*[asyncio.create_task(start(profile)) for profile in profiles])


if __name__ == '__main__':
    asyncio.run(main())
