import os
import random
import asyncio
from datetime import datetime
from dotenv import load_dotenv
from web3db import Profile, DBHelper
from curl_cffi.requests import RequestsError
from eth_account.messages import encode_typed_data, encode_defunct

from web3mt.evm.client import Client
from web3mt.evm.models import ZetaChain, BNB, TokenAmount, DefaultABIs
from web3mt.utils import set_windows_event_loop_policy, logger, sleep, ProfileSession
from examples.evm.zetachain.config import *
from examples.evm.zetachain.db import update_stats, create_table

load_dotenv()
set_windows_event_loop_policy()


async def zeta_and_bnb_price() -> tuple[float, float]:
    client = Client(okx_api_key=okx_api_key, okx_api_secret=okx_api_secret, okx_passphrase=okx_passphrase)
    return await client.get_token_price('ZETA'), await client.get_token_price('BNB')


class ZetachainHub(Client):

    def __init__(self, profile: Profile):
        super().__init__(
            network=ZetaChain,
            profile=profile,
            encryption_password=passphrase,
            delay_between_requests=delay_between_rpc_requests
        )
        self.session = ProfileSession(
            profile, headers={
                'Origin': 'https://hub.zetachain.com',
                'Referer': 'https://hub.zetachain.com/'
            }, requests_echo=False, verify=False
        )
        self.tasks = {
            "SEND_ZETA": self.receive_and_transfer,
            "RECEIVE_ZETA": None,
            "POOL_DEPOSIT_ANY_POOL": self.lp_pool,
            "RECEIVE_BTC": self.receive_btc,
            "RECEIVE_ETH": self.receive_eth,
            "RECEIVE_BNB": self.receive_bnb,
            "EDDY_FINANCE_SWAP": self.swap_eddy,
            "RANGE_PROTOCOL_VAULT_TRANSACTION": self.range_vault,
            "ACCUMULATED_FINANCE_DEPOSIT": self.accumulated_finance,
            "ZETA_EARN_STAKE": self.stake_zeta,
            "ZETA_SWAP_SWAP": self.zetaswap,
            "ULTIVERSE_MINT_BADGE": self.ultiverse_badge,
            "NATIVEX_SWAP": self.nativex,
            "ONE_INVITE_ACCEPTED": None,
            "TEN_INVITES_ACCEPTED": None,
            "FIFTY_INVITES_ACCEPTED": None,
            "WALLET_VERIFY": None,
            "WALLET_VERIFY_BY_INVITE": None,
            "LEAGUE_OF_THRONES_STATE_CHANGED": None,
            "ZEBRA_PROTOCOL_TROVE_UPDATED": None,
            "SPACE_ID_GET_ZETA_DOMAIN": None,
            "WEAVE_6_BUY_OR_SELL_NFT": None,
            "ULTIVERSE_ULTIPILOT_EXPLORE": self.ultiverse_explore,
        }

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await super().__aexit__(exc_type, exc_val, exc_tb)
        await self.session.close()

    def generate_signature(self) -> hex:
        msg = {
            "types": {
                "Message": [{"name": "content", "type": "string"}],
                "EIP712Domain": [
                    {"name": "name", "type": "string"},
                    {"name": "version", "type": "string"},
                    {"name": "chainId", "type": "uint256"},
                ],
            },
            "domain": {"name": "Hub/XP", "version": "1", "chainId": self.network.chain_id},
            "primaryType": "Message",
            "message": {"content": "Claim XP"},
        }

        encoded_data = encode_typed_data(full_message=msg)
        result = self.w3.eth.account.sign_message(encoded_data, self.account.key.hex())
        claim_signature = result.signature.hex()

        return claim_signature

    async def enroll(self):
        contract_address = CONTRACTS['enroll']
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(contract_address),
            abi=invitation_manager_abi
        )
        if await contract.functions.hasBeenVerified(self.account.address).call():
            logger.info(f"{self.log_info} | Already enrolled...")
            return
        await sleep(delay_between_rpc_requests, echo=False)
        await self.tx(
            to=self.w3.to_checksum_address(contract_address),
            data=contract.encodeABI('markAsVerified'),
            name='Enroll'
        )

    async def enroll_verify(self):
        while True:
            try:
                response, data = await self.session.post(
                    url="https://xp.cl04.zetachain.com/v1/enroll-in-zeta-xp",
                    json={"address": self.account.address}
                )
                logger.info(f"{self.log_info} | Verify enroll status: {data['isUserVerified']}")
                return
            except RequestsError:
                await sleep(600, 800, profile_id=self.profile.id)

    async def ultiverse_explore(self):
        name = '"Explore" any ZetaChain network event on Ultiverse'
        session = ProfileSession(
            self.profile, headers={
                'Origin': 'https://pilot-zetachain.ultiverse.io',
                'Referer': 'https://pilot-zetachain.ultiverse.io/',
                'Ul-Auth-Api-Key': 'YWktYWdlbnRAZFd4MGFYWmxjbk5s'
            }, sleep_echo=False, requests_echo=False, verify=False
        )
        response, data = await session.post(
            url=f'https://account-api.ultiverse.io/api/user/signature',
            json={"address": self.account.address, 'chainId': self.network.chain_id, 'feature': "assets-wallet-login"}
        )
        message = data['data']['message']
        signature = self.w3.eth.account.sign_message(
            encode_defunct(text=message),
            private_key=self.account.key.hex()
        ).signature.hex()
        response, data = await session.post(
            url='https://account-api.ultiverse.io/api/wallets/signin',
            json={"address": self.account.address, 'chainId': self.network.chain_id, 'signature': signature}
        )
        auth_token = data['data']['access_token']
        session.headers.update({'Ul-Auth-Token': auth_token, 'Ul-Auth-Address': self.account.address})
        session.cookies.update({'Ultiverse_Authorization': auth_token})

        session.headers.pop('Ul-Auth-Api-Key')
        response, data = await session.post(
            url='https://pml.ultiverse.io/api/explore/sign',
            json={'worldIds': ["Terminus"], 'chainId': self.network.chain_id}
        )
        data = data['data']
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(data['contract']),
            abi=ultiverse_explore_abi
        )
        await self.tx(
            to=contract.address, name=name,
            data=contract.encodeABI('explore', args=[
                data['deadline'], data['voyageId'], data['destinations'], data['data'], data['signature']
            ])
        )

    async def ultiverse_badge(self):
        async def get_mint_data():
            session = ProfileSession(
                self.profile, headers={
                    'Origin': 'https://mission.ultiverse.io',
                    'Referer': 'https://mission.ultiverse.io/',
                    'Ul-Auth-Api-Key': 'bWlzc2lvbl9ydW5uZXJAZFd4MGFYWmxjbk5s'
                }, sleep_echo=False, requests_echo=False, verify=False
            )
            response, data = await session.post(
                url=f'https://toolkit.ultiverse.io/api/user/signature',
                json={
                    "address": self.account.address, 'chainId': self.network.chain_id, 'feature': "assets-wallet-login"
                }
            )
            message = data['data']['message']
            signature = self.w3.eth.account.sign_message(
                encode_defunct(text=message),
                private_key=self.account.key.hex()
            ).signature.hex()
            response, data = await session.post(
                url='https://toolkit.ultiverse.io/api/wallets/signin',
                json={"address": self.account.address, 'chainId': self.network.chain_id, 'signature': signature}
            )
            auth_token = data['data']['access_token']
            session.headers.update({'Ul-Auth-Token': auth_token})
            session.cookies.update({'Ultiverse_Authorization': auth_token})
            response, data = await session.get(url='https://mission.ultiverse.io/api/tickets/list')
            while True:
                for badge in data['data']:
                    if badge['endAt'] > int(datetime.now().timestamp()) > badge['startAt']:
                        event_id = badge['eventId']
                        response, data = await session.post(
                            url="https://mission.ultiverse.io/api/tickets/mint",
                            json={"address": self.account.address, 'eventId': event_id}
                        )
                        if data['success']:
                            return data['data']
                        logger.warning(f'{self.log_info} | {data["err"]} - {badge["name"]}')

        mint_data = await get_mint_data()
        if not mint_data:
            return
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(mint_data['contract']),
            abi=ultiverse_badge_abi,
        )
        await self.tx(
            to=contract.address,
            data=contract.encodeABI('buy', args=[
                mint_data['expireAt'], mint_data['tokenId'], mint_data['eventId'], mint_data['signature']
            ]),
            name='"Mint a badge on Ultiverse" task'
        )

    async def zetaswap(self):
        headers = {
            'Api_key': '7e5e5cc85bb10c1a7c5b2836b55e00acfe0a9509',
            'Apikey': '7e5e5cc85bb10c1a7c5b2836b55e00acfe0a9509',
            'Origin': 'https://app.zetaswap.com',
            'Referer': 'https://app.zetaswap.com/'
        }
        while True:
            amount = random.randrange(TokenAmount(0.000001).Wei, TokenAmount(0.001).Wei)
            params = {
                'src_chain': 'zetachain', 'dst_chain': 'zetachain',
                'token_in': TOKENS['ZETA'],
                'token_out': TOKENS['ETH.ETH'],
                'amount': TokenAmount(amount, wei=True).Ether,
                'address': self.account.address,
                'slippage': 2
            }
            try:
                response, data = await self.session.get(
                    url='https://newapi.native.org/v1/firm-quote',
                    params=params,
                    headers=headers
                )
                if 'error' in data:
                    continue
                tx_data = data['txRequest']
                await self.tx(
                    to=tx_data['target'],
                    data=tx_data['calldata'],
                    value=TokenAmount(int(tx_data['value']), wei=True),
                    name='"Swap ETH.ETH to WZETA or vice-versa on ZetaSwap" task'
                )
                return
            except (RequestsError, KeyError) as e:
                await sleep(30)

    async def nativex(self):
        headers = {
            'Apikey': 'JWL73SF2K899AMPFRHZV',
            'If-None-Match': 'W/"12bb-HV/fFStOEEJTzXLYMNmpdVK9MjQ"',
            'Origin': 'https://nativex.finance',
            'Referer': 'https://nativex.finance/'
        }
        while True:
            amount = random.randrange(TokenAmount(0.001).Wei, TokenAmount(0.01).Wei)
            params = {
                'src_chain': 'zetachain', 'dst_chain': 'zetachain',
                'token_in': TOKENS['ZETA'],
                'token_out': TOKENS['BTC.BTC'],
                'amount': TokenAmount(amount, wei=True).Ether,
                'address': self.account.address,
                'slippage': 0.5
            }
            try:
                response, data = await self.session.get(
                    url='https://newapi.native.org/swap-api/v1/firm-quote',
                    params=params,
                    headers=headers
                )
                if 'error' in data:
                    continue
                tx_data = data['txRequest']
                if await self.tx(
                        to=tx_data['target'],
                        data=tx_data['calldata'],
                        value=TokenAmount(int(tx_data['value']), wei=True),
                        name='"Swap on NativeX" task'
                ):
                    return
            except (RequestsError, KeyError):
                await sleep(30)

    async def receive_and_transfer(self):
        await self.tx(
            to=self.account.address,
            name='"Send ZETA in ZetaChain" and "Receive ZETA in ZetaChain" task',
            value=TokenAmount(0.01)
        )

    async def receive_bnb(self) -> None:
        bsc_client = Client(BNB, self.profile, passphrase)
        if (await bsc_client.get_native_balance()).Ether == 0:
            return
        await sleep(delay_between_rpc_requests, echo=False)
        await bsc_client.tx(
            to=bsc_client.w3.to_checksum_address('0x70e967acFcC17c3941E87562161406d41676FD83'),
            value=TokenAmount(random.randint(10 ** 9, 10 ** 10), wei=True),
            name='"Receive BNB in ZetaChain" task'
        )

    async def lp_pool(self):
        if not await self.approve(
                token_address=TOKENS['BNB.BSC'],
                spender=CONTRACTS['hub_pool'],
                abi=DefaultABIs.Token,
                amount=TokenAmount(0.0001).Wei  # bnb
        ):
            return
        await sleep(delay_between_rpc_requests, echo=False)
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(CONTRACTS['hub_pool']),
            abi=pool_abi,
        )
        while True:
            bnb_amount = random.randint(1, 1000)
            ts = (await self.w3.eth.get_block("latest"))['timestamp'] + 3600 + delay_between_rpc_requests
            await sleep(delay_between_rpc_requests, echo=False)
            if await self.tx(
                    to=contract.address,
                    data=contract.encodeABI('addLiquidityETH', args=[
                        self.w3.to_checksum_address(TOKENS['BNB.BSC']),
                        bnb_amount,
                        0,
                        0,
                        self.account.address,
                        ts
                    ]),
                    value=TokenAmount(bnb_price / zeta_price * float(TokenAmount(bnb_amount, wei=True).Ether)),
                    name='"LP any core pool" task'
            ):
                return

    async def receive_btc(self):
        contract_for_encoding = self.w3.eth.contract(
            address=self.w3.to_checksum_address(CONTRACTS['contract_for_encoding']),
            abi=encoding_contract_abi,
        )
        main_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(CONTRACTS['multicall']),
            abi=multicall_abi,
        )
        while True:
            zeta_amount = random.randint(10 ** 15, 10 ** 16)
            await sleep(delay_between_rpc_requests, echo=False)
            encoded_data = contract_for_encoding.encodeABI(
                fn_name="swapAmount",
                args=[
                    (
                        b"_\x0b\x1a\x82t\x9c\xb4\xe2'\x8e\xc8\x7f\x8b\xf6\xb6\x18\xdcq\xa8\xbf\x00'\x10|\x8d\xda\x80\xbb\xbe\x12T\xa7\xaa\xcf2\x19\xeb\xe1H\x1cn\x01\xd7\x00'\x10_\x0b\x1a\x82t\x9c\xb4\xe2'\x8e\xc8\x7f\x8b\xf6\xb6\x18\xdcq\xa8\xbf\x00'\x10\x13\xa0\xc5\x93\x0c\x02\x85\x11\xdc\x02f^r\x85\x13Km\x11\xa5\xf4",
                        self.account.address,
                        zeta_amount,
                        3,
                        (await self.w3.eth.get_block("latest"))['timestamp'] + 3600 + delay_between_rpc_requests,
                    )
                ],
            )
            await sleep(delay_between_rpc_requests, echo=False)
            if await self.tx(
                    to=main_contract.address,
                    value=TokenAmount(zeta_amount, wei=True),
                    data=main_contract.encodeABI(fn_name="multicall", args=[[encoded_data, "0x12210e8a"]]),
                    name='"Receive BTC in ZetaChain" task'
            ):
                return

    async def receive_eth(self):
        contract_for_encoding = self.w3.eth.contract(
            address=self.w3.to_checksum_address(CONTRACTS['contract_for_encoding']),
            abi=encoding_contract_abi,
        )
        main_contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(CONTRACTS['multicall']),
            abi=multicall_abi,
        )
        while True:
            zeta_amount = random.randint(10 ** 14, 10 ** 15)
            encoded_data = contract_for_encoding.encodeABI(
                fn_name="swapAmount",
                args=[
                    (
                        b"_\x0b\x1a\x82t\x9c\xb4\xe2'\x8e\xc8\x7f\x8b\xf6\xb6\x18\xdcq\xa8\xbf\x00\x0b\xb8\x91\xd4\xf0\xd5@\x90\xdf-\x81\xe84\xc3\xc8\xceq\xc6\xc8e\xe7\x9f\x00\x0b\xb8\xd9{\x1d\xe3a\x9e\xd2\xc6\xbe\xb3\x86\x01G\xe3\x0c\xa8\xa7\xdc\x98\x91",
                        self.account.address,
                        zeta_amount,
                        10,
                        (await self.w3.eth.get_block("latest"))['timestamp'] + 3600 + delay_between_rpc_requests,
                    )
                ],
            )
            await sleep(delay_between_rpc_requests, echo=False)
            if await self.tx(
                    to=self.w3.to_checksum_address(CONTRACTS['multicall']),
                    value=TokenAmount(zeta_amount, wei=True),
                    data=main_contract.encodeABI(fn_name="multicall", args=[[encoded_data, "0x12210e8a"]]),
                    name='"Receive ETH in ZetaChain" task'
            ):
                return

    async def stake_zeta(self, amount: int = None):
        stZETA_balance = await self.balance_of(token_address=TOKENS['stZETA'])
        if amount:
            if stZETA_balance.Wei >= amount:
                logger.info(f'{self.log_info} | Already staking {stZETA_balance} stZETA')
                return
        await sleep(delay_between_rpc_requests, echo=False)
        await self.tx(
            to=TOKENS['stZETA'],
            value=TokenAmount(random.randint(10 ** 14, 10 ** 15), wei=True),
            data='0x5bcb2fc6',
            name='"Complete a stake on ZetaEarn" task'
        )

    async def range_vault(self):
        # wrap zeta, approve stzeta, approve wzeta, add liquidity

        async def wrap_zeta(amount: int):
            WZETA_balance = await self.balance_of(token_address=TOKENS['WZETA'])
            if WZETA_balance.Wei >= amount:
                logger.info(f'{self.log_info} | Already wrapped {WZETA_balance} WZETA')
                return
            await sleep(delay_between_rpc_requests, echo=False)
            await self.tx(
                to=TOKENS['WZETA'],
                value=TokenAmount(amount, wei=True),
                data='0xd0e30db0',
                name='Wrap ZETA'
            )

        izumi_wzeta_ztzeta_pool_contract = self.w3.eth.contract(
            address=CONTRACTS['izumi_wzeta_stzeta_pool'],
            abi=izumi_WZETA_stZETA_pool_abi
        )
        pool_balance = await izumi_wzeta_ztzeta_pool_contract.functions.getUnderlyingBalances().call()
        await sleep(delay_between_rpc_requests, echo=False)
        pool_ratio = pool_balance[0] / pool_balance[1]
        stZETA_amount = random.randint(10_000, 100_000)
        WZETA_amount = int(stZETA_amount / pool_ratio)
        stZETA_amount, WZETA_amount, RUNI_amount = await izumi_wzeta_ztzeta_pool_contract.functions.getMintAmounts(
            stZETA_amount, WZETA_amount
        ).call()
        await sleep(delay_between_rpc_requests, echo=False)

        await self.stake_zeta(stZETA_amount)
        await sleep(delay_between_rpc_requests, echo=False)
        await self.approve(
            token_address=TOKENS['stZETA'],
            spender=CONTRACTS['izumi_wzeta_stzeta_pool'],
            amount=TokenAmount(stZETA_amount, wei=True)
        )
        await sleep(delay_between_rpc_requests, echo=False)

        await wrap_zeta(WZETA_amount)
        await sleep(delay_between_rpc_requests, echo=False)
        await self.approve(
            token_address=TOKENS['WZETA'],
            spender=CONTRACTS['izumi_wzeta_stzeta_pool'],
            amount=TokenAmount(WZETA_amount, wei=True)
        )
        await sleep(delay_between_rpc_requests, echo=False)

        await self.tx(
            to=CONTRACTS['izumi_wzeta_stzeta_pool'],
            data=izumi_wzeta_ztzeta_pool_contract.encodeABI(
                fn_name='mint',
                args=[RUNI_amount, [stZETA_amount, WZETA_amount]]
            ),
            name='"Add liquidity to a ZetaChain Vault on Range" task'
        )

    async def accumulated_finance(self):
        stZETA_amount = random.randint(10_000, 100_000)

        async def deposit_stZETA():
            await self.tx(
                to=CONTRACTS['stzeta_minter'],
                value=TokenAmount(stZETA_amount, wei=True),
                data=self.w3.eth.contract(address=CONTRACTS['stzeta_minter'], abi=stZETA_minter_abi).encodeABI(
                    'deposit', args=[self.account.address]
                ),
                name='Mint stZETA'
            )

        async def deposit_wstZETA():
            await self.tx(
                to=TOKENS['wstZETA'],
                data=self.w3.eth.contract(
                    address=TOKENS['wstZETA'],
                    abi=wstZETA_abi
                ).encodeABI('deposit', args=[stZETA_amount, self.account.address]),
                name='"Mint and stake stZETA on Accumulated Finance" task'
            )

        await deposit_stZETA()
        await sleep(delay_between_rpc_requests, echo=False)
        await self.approve(
            spender=TOKENS['wstZETA'],
            token_address=TOKENS['stZETA'],
            amount=stZETA_amount
        )
        await sleep(delay_between_rpc_requests, echo=False)
        await deposit_wstZETA()

    async def swap_eddy(self):
        while True:
            if await self.tx(
                    to=CONTRACTS['eddy_swap'],
                    data=f'0x148e6bcc000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                         f'0000000000000000000000000000000000004000000000000000000000000000000000000000000000000000000000000000'
                         f'020000000000000000000000005f0b1a82749cb4e2278ec87f8bf6b618dc71a8bf000000000000000000000000'
                         f'{random.choice(list(ZRC20_TOKENS.values()) + [TOKENS["WZETA"], TOKENS["stZETA"]])[2:]}',
                    value=TokenAmount(random.randrange(TokenAmount(0.001).Wei), wei=True),
                    name='"Swap any tokens on Eddy Finance" task'
            ):
                return

    async def check_tasks(self) -> tuple[list[str], list[str]]:
        while True:
            try:
                response, data = await self.session.get(
                    url="https://xp.cl04.zetachain.com/v1/get-user-has-xp-to-refresh",
                    params={"address": self.account.address},
                    headers={
                        'Origin': 'https://hub.zetachain.com',
                        'Referer': 'https://hub.zetachain.com/'
                    },
                    retry_delay=random.uniform(200, 300)
                )
                break
            except RequestsError:
                await sleep(600, 800, profile_id=self.profile.id)

        tasks_to_refresh = []
        tasks_to_do = []
        for task, task_data in data["xpRefreshTrackingByTask"].items():
            if task_data["hasXpToRefresh"]:
                tasks_to_refresh.append(task)
            elif not task_data["hasAlreadyEarned"]:
                tasks_to_do.append(task)
        return tasks_to_refresh, tasks_to_do

    async def claim_tasks(self) -> list[str]:
        completed_tasks, available_tasks = await self.check_tasks()
        if not completed_tasks:
            logger.info(f"{self.log_info} | Nothing to claim")
        for task in completed_tasks:
            claim_data = {
                "address": self.account.address,
                "task": task,
                "signedMessage": self.generate_signature(),
            }
            while True:
                try:
                    await self.session.post(
                        url="https://xp.cl04.zetachain.com/v1/xp/claim-task",
                        json=claim_data,
                        headers={
                            'Origin': 'https://hub.zetachain.com',
                            'Referer': 'https://hub.zetachain.com/'
                        }
                    )
                    break
                except RequestsError:
                    await sleep(600, 800, profile_id=self.profile.id)

            logger.success(f"{self.log_info} | Claimed {task} task")
            await sleep(delay_between_http_requests, echo=False)
        return available_tasks

    async def get_stats(self) -> dict | None:
        while True:
            try:
                response, data = await self.session.get(
                    url=f'https://xp.cl04.zetachain.com/v1/get-points?address={self.account.address}',
                    headers={
                        'Origin': 'https://hub.zetachain.com',
                        'Referer': 'https://hub.zetachain.com/'
                    }
                )
                return {'level': data['level'], 'points': data['totalXp'], 'rank': data['rank']}
            except RequestsError:
                await sleep(600, 800, profile_id=self.profile.id)


async def process_account(profile: Profile) -> dict | None:
    async with ZetachainHub(profile) as zh:
        logger.info(f'{zh.log_info} | Balance {await zh.get_native_balance()} ZETA')
        await zh.enroll()
        await sleep(delay_between_http_requests, echo=False)
        await zh.enroll_verify()
        await sleep(delay_between_http_requests, echo=False)
        available_quests = await zh.claim_tasks()
        logger.info(f'{zh.log_info} | Available tasks: {", ".join(available_quests)}')
        await sleep(delay_between_http_requests, echo=False)
        if choice == 1:
            for task in random.sample(available_quests, len(available_quests)):
                if zh.tasks[task]:
                    await zh.tasks[task]()
                    await sleep(random.uniform(30, 60))
        await zh.claim_tasks()
        logger.success(f'{zh.log_info} | All tasks claimed')
        stats = await zh.get_stats()
        return {'address': zh.account.address, **stats}


async def swap_btc_to_zeta(profile: Profile):
    client = Client(
        network=ZetaChain,
        profile=profile,
        delay_between_requests=delay_between_rpc_requests)
    balance = await client.get_native_balance()
    if balance.Ether < 0.1:
        await sleep(5)
        btc_balance = await client.balance_of(token_address=TOKENS['BTC.BTC'])
        headers = {
            'Apikey': 'JWL73SF2K899AMPFRHZV',
            'If-None-Match': 'W/"12bb-HV/fFStOEEJTzXLYMNmpdVK9MjQ"',
            'Origin': 'https://nativex.finance',
            'Referer': 'https://nativex.finance/'
        }
        async with ProfileSession(profile, headers=headers) as session:
            while True:
                params = {
                    'src_chain': 'zetachain', 'dst_chain': 'zetachain',
                    'token_in': TOKENS['BTC.BTC'],
                    'token_out': TOKENS['ZETA'],
                    'amount': btc_balance.Ether,
                    'address': client.account.address,
                    'slippage': 0.5
                }
                try:
                    response, data = await session.get(
                        url='https://newapi.native.org/swap-api/v1/firm-quote', params=params
                    )
                    if 'error' in data:
                        continue
                    await client.approve(
                        '0xc6f7a7ba5388bFB5774bFAa87D350b7793FD9ef1',
                        token_address=TOKENS['BTC.BTC'],
                        amount=btc_balance
                    )
                    await sleep(5)
                    tx_data = data['txRequest']
                    if await client.tx(
                            to=tx_data['target'],
                            data=tx_data['calldata'],
                            value=TokenAmount(int(tx_data['value']), wei=True),
                            name='Swap BTC.BTC to ZETA'
                    ):
                        return
                except (RequestsError, KeyError):
                    await sleep(30)


async def main():
    await create_table()
    db = DBHelper(os.getenv('CONNECTION_STRING'))
    profiles: list[Profile] = await db.get_rows_by_id([
        # 1,
        # 99, 100, 101, 102, 103, 104, 105, 106, 107, 108, 110, 111, 112, 113, 114, 115, 116, 118, 119, 120, 121, 122,
        # 123, 124, 125, 126, 127, 128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 141, 142, 143, 144, 145, 146,
        # 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159, 160, 161, 168, 268, 269, 274, 275, 280, 281,
        # 282, 284, 286, 287, 288, 289, 292, 295, 296, 297, 300, 301, 302, 303, 304, 306, 307, 309, 310, 312, 313, 314,
        # 315, 318, 319, 320, 322, 325, 326, 329, 330, 331, 337, 338, 340, 341, 345, 346, 347, 348, 350, 351, 352, 354,
        # 355, 356, 357, 358, 359, 360, 362, 363, 364
    ], Profile)
    stats = await asyncio.gather(*[asyncio.create_task(process_account(profile)) for profile in profiles])
    return stats or (await update_stats(**stat) for stat in stats)


if __name__ == "__main__":
    passphrase = os.getenv('PASSPHRASE')
    okx_api_key = os.getenv('OKX_API_KEY')
    okx_api_secret = os.getenv('OKX_API_SECRET')
    okx_passphrase = os.getenv('OKX_API_PASSPHRASE')
    zeta_price, bnb_price = asyncio.run(zeta_and_bnb_price())
    logger.info(f'ZETA: {zeta_price}, BNB: {bnb_price}')
    choice = int(
        input(
            "\n----------------------"
            "\n1: Do tasks"
            "\n2: Claim XP"
            "\n3: Get statistics"
            "\n----------------------"
            "\nChoice: "
        )
    )
    asyncio.run(main())
