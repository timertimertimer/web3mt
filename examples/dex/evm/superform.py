import asyncio

from web3db import Profile, DBHelper

from web3mt.config import env
from web3mt.onchain.evm.client import ProfileClient
from web3mt.onchain.evm.models import Base, TokenAmount
from web3mt.utils import logger, Profilecurl_cffiAsyncSession


class Superform:
    API_URL = 'https://api.superform.xyz/'
    PIGGY_API_URL = 'https://www.superform.xyz/api/proxy/token-distribution'

    def __init__(self, profile: Profile):
        self.client = ProfileClient(chain=Base, profile=profile)
        self.session = Profilecurl_cffiAsyncSession(profile)

    async def __aenter__(self):
        if await self.session.check_proxy():
            return self

    async def __aexit__(self, exc_type, exc_val, exc_tb=None):
        if exc_type:
            logger.error(f'{self.client.log_info} | {exc_val or exc_type}')
        else:
            logger.success(f'{self.client.log_info} | Tasks done')

    async def mint_superfrens(self):
        self.session.headers.update({'Sf-Api-Key': 'a1c6494d30851c65cdb8cb047fdd'})
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

    async def _get_piggy(self) -> tuple[bool, int]:
        while True:
            _, data = await self.session.get(
                f'{self.PIGGY_API_URL}/{self.client.account.address}', follow_redirects=True
            )
            if data.get('error'):
                await asyncio.sleep(10)
                logger.warning(f'{self.client.log_info} | {data}')
                continue
            if data.get('status'):
                logger.info(f'{self.client.log_info} | {data}')
                return True, 0
            break
        claimed = data.get('rewards_claimed')
        total_tokens = data['superrewards_stats']['total_tokens']
        logger.success(f'{self.client.log_info} | {total_tokens} $PIGGY. Claimed: {claimed}')
        return claimed, total_tokens

    async def claim_piggy(self) -> int:
        claimed, total = await self._get_piggy()
        if not claimed:
            _, data = await self.session.get(
                f'{self.PIGGY_API_URL}/claim/{self.client.account.address}', follow_redirects=True
            )
            await self.client.tx(data['to'], 'Claim $PIGGY', data['transactionData'])
        return total


async def start(profile: Profile):
    async with Superform(profile) as sf:
        if not sf:
            return
        # await sf.mint_superfrens()
        return await sf.claim_piggy()


async def main():
    db = DBHelper(env.LOCAL_CONNECTION_STRING)
    profiles: list[Profile] = await db.get_all_from_table(Profile)
    total = await asyncio.gather(*[asyncio.create_task(start(profile)) for profile in profiles])
    logger.info(f'Total $PIGGY: {sum(total)}')


if __name__ == '__main__':
    asyncio.run(main())
