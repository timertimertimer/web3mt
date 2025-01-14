import asyncio
import json
import random
from curl_cffi.requests import RequestsError
from eth_abi import encode
from eth_utils import to_checksum_address, to_wei, to_bytes, to_hex, keccak
from hexbytes import HexBytes
from string import whitespace, punctuation
from examples.dex.evm.basehunt.db import BasehuntState, DBHelper as StateDBHelper
from examples.dex.evm.evm_warmup import Warmup
from web3db import DBHelper, Profile
from web3mt.cex import OKX
from web3mt.consts import Web3mtENV
from web3mt.dex.models import DEX
from web3mt.onchain.evm.client import Client
from web3mt.onchain.evm.models import TokenAmount, Base, Arbitrum, Optimism, Token, Linea, Zora, zkSync
from web3mt.utils import FileManager, sleep, my_logger
from web3mt.utils.custom_sessions import SessionConfig, RETRY_COUNT, CustomAsyncSession
from web3mt.utils.db import update_shared_proxies

nfts = {
    '0x3b4B32a5c9A01763A0945A8a4a4269052DC3DE2F': '6UuHdstl9MRFd4cgFf15kk',
    '0x5307c5ee9aee0b944fa2e0dba5d35d1d454e4bce': '39XYCR1jsdPwnoFEpwCwhD',
    '0xd60f13cc3e4d5bc96e7bae8aab5f448f3eff3f0c': '1HMONONDaMukjieAOD3PHQ',
    '0x9FF8Fd82c0ce09caE76e777f47d536579AF2Fe7C': '5c3PqZ2EGVbzQ2CQXL1vWK',
    '0x7B791EdF061Df65bAC7a9d47668F61F1a9A998C0': '1BWyKWI2UZHnOEw8E4hpS5'
}
state_db = StateDBHelper()
main_referral_code = '8a989ab9-19ed-479d-b6fe-22bd682e67b1'
states = []
ABI = FileManager.read_json('./abi.json')


class Basehunt(DEX):
    NAME = 'Basehunt'
    API = 'https://basehunt.xyz/api'

    def __init__(self, session: CustomAsyncSession = None, client: Client = None, profile: Profile = None):
        super().__init__(session=session, client=client, profile=profile)
        self.session.config.sleep_after_request = True
        self.session.config.sleep_range = (5, 10)
        self.client.chain = Base

    async def start(self) -> tuple | None:
        try:
            data = await self.state()
        except RequestsError:
            data = {}
        if not data['isOptedIn']:
            await self.opt_in(random.choice(states))
        await self.free_mint()
        if not data['levelData']['currentLevel'] or int(data['levelData']['currentLevel']['level']) < 1:
            address, challenge_id = random.choice(list(nfts.items()))
            res, _ = await self.paid_mint(address)
            if not res:
                my_logger.error(f'{self.client.log_info} | Couldn\'t mint')
                return
            for _ in range(5):
                if await self.complete(challenge_id):
                    break
        spin_data = await self.spin_data()
        if not spin_data['spinData']['hasAvailableSpin']:
            my_logger.info(f'{self.client.log_info} | No spin available')
        else:
            await self.spin()
        await self.claim_ens()
        points_data = await self.state()
        state = [state for state in states if state.id == self.client.profile.id]
        if state:
            state[0].points = points_data['scoreData']['currentScore']
        await state_db.add_record(
            state[0] if state else BasehuntState(
                id=self.client.profile.id,
                address=self.client.account.address,
                points=points_data['scoreData']['currentScore'],
                referral_code=points_data['referralData']['referralCode']
            )
        )

    async def spin(self):
        try:
            _, data = await self.session.post(
                f'{self.API}/spin-the-wheel/execute',
                json={'gameId': 2, 'userAddress': str(self.client.account.address)}
            )
        except RequestsError as e:
            if e.args[0] == 'HTTP Error 500: ':
                my_logger.info(f'{self.client.log_info} | Already spun')
                return
        spin_result = data['spinData']['lastSpinResult']
        my_logger.debug(f'{self.client.log_info} | Got {spin_result["points"]} {spin_result["type"]}')

    async def spin_data(self):
        _, data = await self.session.get(
            f'{self.API}/spin-the-wheel',
            params={'gameId': 2, 'userAddress': str(self.client.account.address)}
        )
        return data

    async def paid_mint(self, address: str) -> tuple[bool, Exception | HexBytes | str]:
        contract = self.client.w3.eth.contract(to_checksum_address(address), abi=ABI['base_nft'])
        mints = await contract.functions.balanceOf(self.client.account.address).call()
        if mints > 0:
            return True, 'Already minted'
        data = await self.client.tx(
            contract.address, 'Mint NFT',
            contract.encode_abi('mintWithComment', args=[str(self.client.account.address), 1, '']),
            TokenAmount(0.0001, token=self.client.chain.native_token)
        )
        if isinstance(data[1], ValueError) and 'insufficient funds for gas' in data[1].args[0]['message']:
            await self.fund()
            return await self.paid_mint(address)
        await sleep(5, 10, log_info=str(self))
        return data

    async def free_mint(self):
        contract = self.client.w3.eth.contract(
            to_checksum_address('0x0821D16eCb68FA7C623f0cD7c83C8D5Bd80bd822'), abi=ABI['forbes']
        )
        mints = await contract.functions.balanceOf(self.client.account.address).call()
        if mints > 0:
            return True, 'Already minted'
        data = await self.client.tx(
            contract.address, 'Mint NFT',
            contract.encode_abi('claim', args=[
                str(self.client.account.address), 1, '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE', 0, (
                    ['0x0000000000000000000000000000000000000000000000000000000000000000'],
                    115792089237316195423570985008687907853269984665640564039457584007913129639935,
                    0, '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'
                ), b''
            ])
        )
        await sleep(5, 10, log_info=str(self))
        if data[0]:
            for _ in range(5):
                if await self.complete('ocsChallenge_b3f47fc6-3649-4bad-9e10-7244fbe1d484'):
                    break

    async def fund(self):
        routes = []
        for chain in [Arbitrum, Optimism, Zora, Linea, zkSync]:
            self.client.chain = chain
            balance = await self.client.balance_of()
            if balance > TokenAmount(0.00012, token=self.client.chain.native_token):
                routes.append(chain)
        self.client.chain = Base
        before_bridge = await self.client.balance_of()
        if routes:
            await Warmup(client=self.client).execute_bridge(
                TokenAmount(
                    random.randint(to_wei(0.00011, 'ether'), to_wei(0.00012, 'ether')),
                    wei=True, token=Token(random.choice(routes))
                ), self.client.chain.native_token
            )
        else:
            token_amount_out = TokenAmount(
                random.randint(to_wei(0.00015, 'ether'), to_wei(0.0002, 'ether')), wei=True,
                token=random.choice([Optimism, zkSync]).native_token
            )
            self.client.chain = token_amount_out.token.chain
            before_withdraw = await self.client.balance_of()
            while True:
                if await OKX(
                        profile=self.client.profile,
                        config=SessionConfig(sleep_after_request=True)
                ).withdraw(str(self.client.account.address), token_amount_out):
                    break
                await sleep(5, 10, log_info=str(self))
            while True:
                after_withdraw = await self.client.balance_of()
                if after_withdraw > before_withdraw:
                    break
                await sleep(5, 10, log_info=str(self))
            await Warmup(client=self.client).execute_bridge(
                TokenAmount(
                    random.randint(to_wei(0.00011, 'ether'), to_wei(0.00012, 'ether')),
                    wei=True, token=token_amount_out.token
                ), Base.native_token
            )
        self.client.chain = Base
        while True:
            after_bridge = await self.client.balance_of()
            if after_bridge > before_bridge:
                break
            await sleep(5, 10, log_info=str(self))

    async def complete(self, challenge_id: str) -> bool:
        _, data = await self.session.post(
            f'{self.API}/challenges/complete',
            json={'gameId': 2, 'userAddress': str(self.client.account.address), 'challengeId': challenge_id}
        )
        return data['success']

    async def state(self):
        for _ in range(RETRY_COUNT):
            try:
                _, data = await self.session.get(
                    f'{self.API}/profile/state',
                    params={'gameId': 2, 'userAddress': str(self.client.account.address)}
                )
                break
            except RequestsError as e:
                pass
        if not data:
            raise RequestsError('Failed to get state')
        return data

    async def opt_in(self, referer: BasehuntState) -> bool:
        referral_code = referer.referral_code
        _, data = await self.session.post(
            f'{self.API}/profile/opt-in',
            json={
                'gameId': 2, 'userAddress': str(self.client.account.address),
                'referralId': random.choice([referral_code] * 4 + [None] * 4 + [main_referral_code] * 2)
            }
        )
        if data['success']:
            my_logger.info(f'{self.client.log_info} | Opted in. Reffered by {referer.id} profile')
        return data['success']

    async def claim_badges(self):
        async def stand_with_crypto():
            _, data = await self.session.post(
                'https://www.standwithcrypto.org/action/sign-up',
                headers={
                    'Content-Type': 'application/json',
                    'Next-Action': 'd24546603da39fe456a13cb7ea842d234f2902e0'
                },
                data=json.dumps([self.client.account.address])
            )
            data = json.loads(data.removeprefix('0:["$@1",["--ksRhIIvFq6qzpETPlTx",null]]\n1:'))
            domain = data['domain']
            address = data['address']
            statement = data['statement']
            version = data['version']
            chain_id = data['chain_id']
            nonce = data['nonce']
            issued_at = data['issued_at']
            expiration_time = data['expiration_time']
            invalid_before = data['invalid_before']
            signature = self.client.sign(
                f'''{domain} wants you to sign in with your Ethereum account:
{address}

{statement}

Version: {version}
Chain ID: {chain_id}
Nonce: {nonce}
Issued At: {issued_at}
Expiration Time: {expiration_time}
Not Before: {invalid_before}'''
            )
            data.pop('resources')
            data.pop('uri')
            for i in range(RETRY_COUNT):
                try:
                    _, data = await self.session.post(
                        'https://www.standwithcrypto.org/action/sign-up',
                        headers={
                            'Content-Type': 'application/json',
                            'Next-Action': '310e1b4f7302cecee12c017d7fcedd973b919a79'
                        },
                        data=json.dumps([{'signature': '0x' + signature, 'payload': data}])
                    )
                except RequestsError as e:
                    my_logger.info(f'{self.client.log_info} | Failed to claim Stand With Crypto badge ({i}): {e}')

        badges = {
            'Stand With Crypto': (stand_with_crypto, 1),
            'Collector': 4,
            'Trader': 5,
            'Saver': 6,
            'Based: 10 transactions': 7,
            'Based: 50 transactions': 8,
            'Based: 100 transactions': 9,
            'Based: 1000 transactions': 10
        }
        for badge, func_and_id in badges.items():
            if isinstance(func_and_id, tuple):
                func, id_ = func_and_id
            else:
                func, id_ = None, func_and_id
            while True:
                try:
                    _, data = await self.session.post(
                        f'{self.API}/badges/claim',
                        json={'gameId': 2, 'userAddress': str(self.client.account.address), 'badgeId': str(id_)}
                    )
                    if data['success']:
                        my_logger.debug(f'{self.client.log_info} | Claimed {badge} badge')
                    break
                except RequestsError as e:
                    await sleep(5, 10, log_info=self.client.log_info)
                    if func:
                        await func()
                    else:
                        my_logger.info(f'{self.client.log_info} | Not eligible to claim "{badge}" badge. {e}')
                        break

    async def claim_ens(self):
        contract = self.client.w3.eth.contract(
            to_checksum_address('0x4cCb0BB02FCABA27e82a56646E81d8c5bC4119a5'), abi=ABI['ens']
        )
        registered = await contract.functions.discountedRegistrants(self.client.account.address).call()
        if registered:
            await self.complete('2XaiAPDQ8WwG5CUWfMMYaU')
            return
        points_data = await self.state()
        points = points_data['scoreData']['currentScore']
        if points < 5000:
            return
        name = self.client.profile.email.login.split('@')[0].translate(str.maketrans('', '', punctuation + whitespace))
        if not await contract.functions.available(name).call():
            name += str(random.randrange(10))
        name_with_domain = name + ".base.eth"
        name_hash = namehash(name_with_domain)
        await self.client.tx(
            contract.address,
            f'Mint ENS - {name}',
            contract.encode_abi('discountedRegister', args=[
                (
                    name, self.client.account.address, 315576000,
                    to_checksum_address('0xC6d566A56A1aFf6508b41f6c90ff131615583BCD'),
                    [
                        to_bytes(
                            hexstr=f'0xd5fa2b00{to_hex(name_hash)[2:]}000000000000000000000000{self.client.account.address[2:]}'),
                        to_bytes(
                            hexstr=f'0x77372213{to_hex(encode(["bytes32", "string"], [name_hash, name_with_domain]))[2:]}')
                    ],
                    True
                ),
                to_bytes(hexstr='0xc1af3c32616941d3f6d85f4f01aafb556b5620e8868acac1ed2a816fb9d0676d'),
                to_bytes(hexstr='0x00')
            ])
        )
        await sleep(5, 10, str(self.client))
        await self.complete('2XaiAPDQ8WwG5CUWfMMYaU')


def namehash(name):
    node = HexBytes('0x' + '00' * 32)
    if name:
        labels = name.split(".")
        for label in reversed(labels):
            label_hash = keccak(text=label)
            node = keccak(node + label_hash)
    return node


async def start(semaphore: asyncio.Semaphore, profile: Profile):
    async with semaphore:
        async with Basehunt(profile=profile) as bh:
            # await bh.claim_badges()
            await bh.start()


async def main():
    global states
    db = DBHelper(url=Web3mtENV.LOCAL_CONNECTION_STRING, query_echo=False)
    await update_shared_proxies(db)
    states = await state_db.get_all_from_table(BasehuntState)
    profiles = await db.get_all_from_table(Profile)
    # profiles = await db.get_rows_by_id([1], Profile)
    random.shuffle(profiles)
    semaphore = asyncio.Semaphore(20)
    await asyncio.gather(*[start(semaphore, profile) for profile in profiles])


if __name__ == '__main__':
    asyncio.run(main())
