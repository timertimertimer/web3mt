import json
import os

import eth_abi
import jwt
import random
import secrets
import asyncio
from hashlib import sha256
from datetime import datetime, timezone
from time import time
from dotenv import load_dotenv
from curl_cffi.requests import RequestsError
from nltk.corpus import words

from evm.linea.db import task_done, get_task_status, select_profile, insert_record
from evm.models import Linea, TokenAmount
from evm.client import Client

from web3db import DBHelper, Profile

from utils import logger, ProfileSession, sleep

db = DBHelper(os.getenv('CONNECTION_STRING'))

load_dotenv()


class LineaPark(Client):
    def __init__(self, profile: Profile):
        super().__init__(Linea, profile, do_no_matter_what=True)
        self.tasks = [
            {
                'gamerboom': self.gamerboom,
                'nidium': self.nidium,
                'galactic_exploration': self.galactic_exploration
            },
            {
                'abyss_world': self.abyss_world,
                'pictographs': self.pictographs,
                'satoshi_universe': self.satoshi_universe,
                'yooldo': self.yooldo
            },
            {
                'dmail': self.dmail,
                'gamic': self.gamic,
                'asmatch': self.asmatch,
                'bitavatar': self.bitavatar,
                'readon': self.readon,
                'sendingme': self.sendingme
            },
            {
                'sarubol': self.sarubol,
                'z2048': self.z2048,
                'lucky_cat': self.lucky_cat,
                'ulti_pilot': self.ulti_pilot,
            },
            {
                'omnizone': self.omnizone,
                'battlemon': self.battlemon,
                'play_nouns': self.play_nouns,
                'unfettered_awakening': self.unfettered_awakening,
            },
            {
                'zace': self.zace,
                'micro3': self.micro3,
                'alienswap': self.alienswap,
                'frog_war': self.frog_war,
                'acg_worlds': self.acg_worlds,
                'bilinear': self.bilinear,
                'imaginairynfts': self.imaginairynfts,
                'arena_games': self.arena_games
            }
        ]
        self.INCREASE_GWEI = 1.1

    async def arena_games(self):
        headers = {'Origin': 'https://linea.arenavs.com', 'Referer': 'https://linea.arenavs.com/'}
        async with ProfileSession(self.profile, headers=headers) as session:
            password = self.profile.email.password
            try:
                response, data = await session.post(
                    url='https://arena-linea-api-p6z2e.ondigitalocean.app/auth/login',
                    json={'identifier': self.profile.email.login, 'password': password}
                )
                wallet_address = data['user']['walletAddress']
            except RequestsError:
                wallet_address = None
            if not wallet_address:
                while True:
                    username = random.choice(words.words())
                    try:
                        response, data = await session.post(
                            url='https://arena-linea-api-p6z2e.ondigitalocean.app/auth/register',
                            json={
                                'email': self.profile.email.login,
                                'password': self.profile.email.password,
                                'username': username,
                                'referralCode': ''
                            }
                        )
                        wallet_address = data['user']['walletAddress']
                        break
                    except RequestsError:
                        pass

        return await self.tx(
            '0xbd0ef89f141680b9b2417e4384fdf73cfc696f9f', 'Arena Games',
            f'0x40d097c3000000000000000000000000{wallet_address[2:]}'
        )

    async def imaginairynfts(self):
        return await self.tx(
            '0xb99e5534d42500eb1d5820fba3bb8416ccb76396', 'ImaginAIryNFTs',
            '0xd85d3d270000000000000000000000000000000000000000000000000000000000000020000000000000000000000000000'
            '000000000000000000000000000000000005e68747470733a2f2f697066732e696f2f697066732f626166797265696477783475617'
            '6357a6976766b376b746f327077737a786c6371617a71706278756232347a626b6b35787a6d65697567646170342f6d65746164617'
            '4612e6a736f6e0000', value=TokenAmount(0.0001)
        )

    async def bilinear(self):
        name = 'Bilinear'
        if not (await self.balance_of(token_address='0x1ED75cB175E667287451c78D8f85D48535749cB6')).Ether > 0:
            return await self.tx(
                '0xa091303966ef5f94cf68f85d892c729fd6c3f30b', name,
                '0x738a9fa100000000000000000000000000000000000000000000000000000000000000a0000000000000000000000000000'
                '00000000000000000000000000000000000c0000000000000000000000000000000000000000000000000000000000000016000000'
                '000000000000000000000000000000000000000000000000000000000009ce46a75af5117679e3393d8844ec85ed684cf325e48be9'
                '822469e12cfe5348200000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                '0000000000000000000000000000000000000400000000000000000000000000000000000000000000000000000000000000060000'
                '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                '0000000000000000001000000000000000000000000000000000000000000000000000000000000000100000000000000000000000'
                '0000000000000000000000000000000000000006000000000000000000000000000000000000000000000000000000000000000800'
                '0000000000000000000000000000000000000000000000000000000000000a00000000000000000000000000000000000000000000'
                '0000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000'
                '0000000000000000000000000000000000000000000', check_existing=False
            )
        logger.success(f'{self.profile.id} | {self.account.address} | {name} already minted')
        return True

    async def acg_worlds(self):
        return await self.tx(
            '0xcd1ea9e70d0260c0f47d217ed6d5be9cd4ed34fb', 'ACG WORLDS', value=TokenAmount(0.0001),
            check_existing=False
        )

    async def frog_war(self):
        name = 'Frog War'
        abi = [
            {
                "inputs": [
                    {
                        "internalType": "address",
                        "name": "account",
                        "type": "address"
                    },
                    {
                        "internalType": "uint256",
                        "name": "id",
                        "type": "uint256"
                    }
                ],
                "name": "balanceOf",
                "outputs": [
                    {
                        "internalType": "uint256",
                        "name": "",
                        "type": "uint256"
                    }
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {
                        "internalType": "address",
                        "name": "_receiver",
                        "type": "address"
                    },
                    {
                        "internalType": "uint256",
                        "name": "_tokenId",
                        "type": "uint256"
                    },
                    {
                        "internalType": "uint256",
                        "name": "_quantity",
                        "type": "uint256"
                    },
                    {
                        "internalType": "address",
                        "name": "_currency",
                        "type": "address"
                    },
                    {
                        "internalType": "uint256",
                        "name": "_pricePerToken",
                        "type": "uint256"
                    },
                    {
                        "components": [
                            {
                                "internalType": "bytes32[]",
                                "name": "proof",
                                "type": "bytes32[]"
                            },
                            {
                                "internalType": "uint256",
                                "name": "quantityLimitPerWallet",
                                "type": "uint256"
                            },
                            {
                                "internalType": "uint256",
                                "name": "pricePerToken",
                                "type": "uint256"
                            },
                            {
                                "internalType": "address",
                                "name": "currency",
                                "type": "address"
                            }
                        ],
                        "internalType": "struct IDrop1155.AllowlistProof",
                        "name": "_allowlistProof",
                        "type": "tuple"
                    },
                    {
                        "internalType": "bytes",
                        "name": "_data",
                        "type": "bytes"
                    }
                ],
                "name": "claim",
                "outputs": [],
                "stateMutability": "payable",
                "type": "function"
            }
        ]
        contract = self.w3.eth.contract(
            self.w3.to_checksum_address('0xea81a18fb97401a9f4b79963090c65a3a30ecdce'),
            abi=abi
        )
        if not await contract.functions.balanceOf(self.account.address, 1).call() > 0:
            value = TokenAmount(0.0001)
            await self.tx(
                contract.address, 'Frog War (Identity Pass)', contract.encodeABI('claim', args=[
                    self.account.address, 1, 1, '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE', value.Wei,
                    (['0x0000000000000000000000000000000000000000000000000000000000000000'], 3, value.Wei,
                     '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE'), b''
                ]), value=value, check_existing=False
            )
        else:
            logger.success(f'{self.profile.id} | {self.account.address} | {name} (Identity Pass) already minted')

        contract = self.w3.eth.contract(
            self.w3.to_checksum_address('0x184E5677890c5aDd563dE785fF371f6c188d3dB6'),
            abi=abi
        )
        if not await contract.functions.balanceOf(self.account.address, 6).call() > 0:
            return await self.tx(
                contract.address, 'Frog War (Warrior)', contract.encodeABI('claim', args=[
                    self.account.address, 6, 1, '0x21d624c846725ABe1e1e7d662E9fB274999009Aa', 0,
                    (['0x0000000000000000000000000000000000000000000000000000000000000000'], 1, 0,
                     '0x21d624c846725ABe1e1e7d662E9fB274999009Aa'), b''
                ]), check_existing=False
            )
        else:
            logger.success(f'{self.profile.id} | {self.account.address} | {name} (Warrior) already minted')
            return True

    async def alienswap(self):
        name = 'AlienSwap'
        abi = [
            {
                "inputs": [
                    {
                        "internalType": "uint256",
                        "name": "quantity",
                        "type": "uint256"
                    }
                ],
                "name": "purchase",
                "outputs": [],
                "stateMutability": "payable",
                "type": "function"
            },
            {
                "inputs": [
                    {
                        "internalType": "address",
                        "name": "operator",
                        "type": "address"
                    },
                    {
                        "internalType": "bool",
                        "name": "approved",
                        "type": "bool"
                    }
                ],
                "name": "setApprovalForAll",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        contract = self.w3.eth.contract(
            self.w3.to_checksum_address('0x5ecde77c11e52872adeb3ef3565ffa0b2bcc1c68'),
            abi=abi
        )
        return await self.tx(
            contract.address, name, contract.encodeABI('purchase', args=[1]), value=TokenAmount(0.0001)
        )

    async def zace(self):
        name = 'zAce'
        if (await self.balance_of(token_address='0x4446090D91CB7893E51C0B6d48829CdaBB84a980')).Ether > 0:
            logger.success(f'{self.profile.id} | {self.account.address} | {name} already minted')
            return True
        return await self.tx(
            '0x971a871fd8811abbb1f5e3fb1d84a873d381cee4', name, '0xbaeb0718', value=TokenAmount(0.0001),
            check_existing=False
        )

    async def micro3(self):
        return await self.tx(
            '0x915d2358192f5429fa6ee6a6e5d1b37026d580ba', 'Micro3',
            '0xefef39a10000000000000000000000000000000000000000000000000000000000000001', value=TokenAmount(0.0001)
        )

    async def omnizone(self):
        return await self.tx('0x7136abb0fa3d88e4b4d4ee58fc1dfb8506bb7de7', 'Omnizone')

    async def battlemon(self):
        return await self.tx('0x578705C60609C9f02d8B7c1d83825E2F031e35AA', 'Battlemon', '0x6871ee40')

    async def play_nouns(self):
        name = 'Play Nouns'
        abi = [
            {
                "inputs": [
                    {
                        "internalType": "address",
                        "name": "account",
                        "type": "address"
                    },
                    {
                        "internalType": "uint256",
                        "name": "id",
                        "type": "uint256"
                    }
                ],
                "name": "balanceOf",
                "outputs": [
                    {
                        "internalType": "uint256",
                        "name": "",
                        "type": "uint256"
                    }
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {
                        "internalType": "address",
                        "name": "_receiver",
                        "type": "address"
                    },
                    {
                        "internalType": "uint256",
                        "name": "_tokenId",
                        "type": "uint256"
                    },
                    {
                        "internalType": "uint256",
                        "name": "_quantity",
                        "type": "uint256"
                    },
                    {
                        "internalType": "address",
                        "name": "_currency",
                        "type": "address"
                    },
                    {
                        "internalType": "uint256",
                        "name": "_pricePerToken",
                        "type": "uint256"
                    },
                    {
                        "components": [
                            {
                                "internalType": "bytes32[]",
                                "name": "proof",
                                "type": "bytes32[]"
                            },
                            {
                                "internalType": "uint256",
                                "name": "quantityLimitPerWallet",
                                "type": "uint256"
                            },
                            {
                                "internalType": "uint256",
                                "name": "pricePerToken",
                                "type": "uint256"
                            },
                            {
                                "internalType": "address",
                                "name": "currency",
                                "type": "address"
                            }
                        ],
                        "internalType": "struct IDrop1155.AllowlistProof",
                        "name": "_allowlistProof",
                        "type": "tuple"
                    },
                    {
                        "internalType": "bytes",
                        "name": "_data",
                        "type": "bytes"
                    }
                ],
                "name": "claim",
                "outputs": [],
                "stateMutability": "payable",
                "type": "function"
            }
        ]
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address('0x9df3c2c75a92069b99c73bd386961631f143727c'),
            abi=abi
        )
        if await contract.functions.balanceOf(self.account.address, 0).call() > 0:
            logger.success(f'{self.profile.id} | {self.account.address} | {name} already minted')
            return True
        return await self.tx(
            to=contract.address,
            name=name,
            data=contract.encodeABI('claim', args=[
                self.account.address,
                0,
                1,
                "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE",
                0,
                (["0x0000000000000000000000000000000000000000000000000000000000000000"],
                 115792089237316195423570985008687907853269984665640564039457584007913129639935,
                 0,
                 "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"),
                "0x"
            ]),
            check_existing=False
        )

    async def unfettered_awakening(self) -> bool:
        async def web2_mint() -> bool:
            headers = {
                'Origin': 'https://park.theunfettered.io',
                'Referer': 'https://park.theunfettered.io/'
            }
            async with ProfileSession(self.profile, headers=headers) as session:
                response, data = await session.post(
                    url='https://park.theunfettered.io/api/login/metamask/temp-token',
                    json={'address': self.account.address.lower()}
                )
                temp_token = data['token']
                signature = self.sign(jwt.decode(temp_token, options={"verify_signature": False})['message'])
                response, data = await session.post(
                    url='https://park.theunfettered.io/api/login/metamask/access-token',
                    json={'tempToken': temp_token, 'signedMessage': signature}
                )
                token = data['token']
                session.cookies.update({'v1-token': token})
                response, data = await session.post(
                    url='https://park.theunfettered.io/api/playerServices/nftMint',
                    json={"AwakeningExpeditionPaid": True}
                )
                success1 = data['success']
                response, data = await session.post(
                    url='https://park.theunfettered.io/api/playerServices/nftMint',
                    json={"NewskinorBountyPaid": True}
                )
                success2 = data['success']
                return success1 and success2

        await self.tx(
            '0x2dc9d44ec35d5defd146e5fd718ee3277dfacf0a',
            'Expedition Legacy (Unfettered)',
            value=TokenAmount(0.0003)
        )
        await self.tx(
            '0x5ac7880e0607d0903a4c27d0a7c886f39d9b50dc',
            'Liane Legacy (Unfettered)',
            value=TokenAmount(0.00015)
        )
        return await web2_mint()

    async def sarubol(self):
        return await self.tx(
            '0x6cada4ccec51d7f40747be4a087520f02dde9f48', 'Tanuki (Sarubol)',
            '0xefef39a10000000000000000000000000000000000000000000000000000000000000001',
            value=TokenAmount(0.0001)
        )

    async def z2048(self):
        data = (
                '0x36ab86c4' + ''.join([random.choice('0123456789abcdef') for _ in range(64)]) +
                eth_abi.encode(['uint256'], [1]).hex()
        )
        return await self.tx('0x490d76b1e9418a78b5403740bd70dfd4f6007e0f', 'z2048', data, check_existing=False)

    async def lucky_cat(self):
        name = 'Lucky Cat'
        if (await self.balance_of(token_address='0x3BBee2922f47D276a70FBE2D38DcC2A920Ed1d05')).Ether > 0:
            logger.success(f'{self.profile.id} | {self.account.address} | {name} already minted')
            return True
        return await self.tx(
            to='0xc577018b3518cd7763d143d7699b280d6e50fdb6',
            name=name,
            data='0x70245bdc',
            check_existing=False
        )

    async def ulti_pilot(self):
        name = 'UltiPilot'
        if (await self.balance_of(token_address='0xE3b5500039F401e48627e8025b37d4871cF34f36')).Ether > 0:
            logger.success(f'{self.profile.id} | {self.account.address} | {name} already minted')
            return True
        abi = [
            {
                "inputs": [
                    {
                        "internalType": "uint256",
                        "name": "deadline",
                        "type": "uint256"
                    },
                    {
                        "internalType": "bytes32",
                        "name": "attributeHash",
                        "type": "bytes32"
                    },
                    {
                        "internalType": "bytes",
                        "name": "signature",
                        "type": "bytes"
                    }
                ],
                "name": "mintSBT",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        headers = {
            'Origin': 'https://pilot-linea.ultiverse.io',
            'Referer': 'https://pilot-linea.ultiverse.io/',
            'Ul-Auth-Api-Key': 'YWktYWdlbnRAZFd4MGFYWmxjbk5s'
        }
        async with ProfileSession(self.profile, headers=headers) as session:
            response, data = await session.post(
                url='https://account-api.ultiverse.io/api/user/signature',
                json={'address': self.account.address, 'chainId': 59144, 'feature': 'assets-wallet-login'}
            )
            signature = self.sign(data['data']['message'])
            response, data = await session.post(
                url='https://account-api.ultiverse.io/api/wallets/signin',
                json={'address': self.account.address, 'chainId': 59144, 'signature': signature}
            )
            token = data['data']['access_token']
            session.headers.update({'Ul-Auth-Address': self.account.address, 'Ul-Auth-Token': token})
            response, data = await session.post(
                url='https://pml.ultiverse.io/api/register/sign',
                json={"referralCode": "Linea", "chainId": 59144}
            )
            if not data['success']:
                logger.warning(
                    f'{self.profile.id} | {self.account.address} | '
                    f'{name} couldn\'t use ref code, maybe already reigestered'
                )
            response, data = await session.post(
                url='https://pml.ultiverse.io/api/register/mint',
                json={
                    'meta': [
                        random.choice(['Optimistic', 'Introverted', 'Adventurous']),
                        random.choice(['Sensitive', 'Confident', 'Curious']),
                        random.choice(['Practical', 'Social Butterfly', 'Independent']),
                        random.choice(['Responsible', 'Open-minded', 'Humorous']),
                        random.choice(['Grounded', 'Skeptical', 'Altruistic'])
                    ],
                    'chainId': 59144
                }
            )
            data = data['data']
            contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address('0x06f9914838903162515afa67d5b99ada0f9791cc'),
                abi=abi
            )
            return await self.tx(
                to=contract.address,
                name=name,
                data=contract.encodeABI('mintSBT', args=[data['deadline'], data['attributeHash'], data['signature']]),
                check_existing=False
            )

    async def dmail(self):
        name = 'Dmail'
        abi = [
            {
                "inputs": [
                    {
                        "internalType": "string",
                        "name": "to",
                        "type": "string"
                    },
                    {
                        "internalType": "string",
                        "name": "path",
                        "type": "string"
                    }
                ],
                "name": "send_mail",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        email = sha256(str(1e11 * random.random()).encode()).hexdigest()
        theme = sha256(str(1e11 * random.random()).encode()).hexdigest()
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address('0xd1a3abf42f9e66be86cfdea8c5c2c74f041c5e14'),
            abi=abi
        )
        return await self.tx(
            to=contract.address,
            name=name,
            data=contract.encodeABI('send_mail', args=[email, theme]),
            check_existing=False
        )

    async def gamic(self):
        abi = [
            {
                "inputs": [
                    {
                        "internalType": "address",
                        "name": "fromToken",
                        "type": "address"
                    },
                    {
                        "internalType": "address",
                        "name": "toToken",
                        "type": "address"
                    },
                    {
                        "internalType": "uint256",
                        "name": "fromTokenAmount",
                        "type": "uint256"
                    },
                    {
                        "internalType": "uint256",
                        "name": "minReturnAmount",
                        "type": "uint256"
                    },
                    {
                        "internalType": "address[]",
                        "name": "mixAdapters",
                        "type": "address[]"
                    },
                    {
                        "internalType": "address[]",
                        "name": "mixPairs",
                        "type": "address[]"
                    },
                    {
                        "internalType": "address[]",
                        "name": "assetTo",
                        "type": "address[]"
                    },
                    {
                        "internalType": "uint256",
                        "name": "directions",
                        "type": "uint256"
                    },
                    {
                        "internalType": "bytes[]",
                        "name": "moreInfos",
                        "type": "bytes[]"
                    },
                    {
                        "internalType": "bytes",
                        "name": "feeData",
                        "type": "bytes"
                    },
                    {
                        "internalType": "uint256",
                        "name": "deadLine",
                        "type": "uint256"
                    }
                ],
                "name": "mixSwap",
                "outputs": [
                    {
                        "internalType": "uint256",
                        "name": "receiveAmount",
                        "type": "uint256"
                    }
                ],
                "stateMutability": "payable",
                "type": "function"
            }
        ]
        slippage = 0.2
        async with ProfileSession(self.profile, headers={'Origin': 'https://swap.dodoex.io'}) as session:
            while True:
                response, data = await session.get(
                    url='https://api.dodoex.io/route-service/v2/widget/getdodoroute',
                    params={
                        'chainId': 59144,
                        'deadLine': ...,
                        'apikey': 'f78ebf46796fca2a5c',
                        'slippage': slippage,
                        'source': 'dodoV2AndMixWasm',
                        'toTokenAddress': '0xA219439258ca9da29E9Cc4cE5596924745e12B93',
                        'fromTokenAddress': '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE',
                        'userAddr': self.account.address,
                        'estimateGas': True,
                        'fromAmount': random.randint(100000000000000, 200000000000000)
                    }
                )
                data = data['data']
                contract = self.w3.eth.contract(data['to'], abi=abi)
                tx_data = contract.encodeABI('mixSwap', args=[
                    '0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE',
                    '0xA219439258ca9da29E9Cc4cE5596924745e12B93',
                    int(data['value']),
                    TokenAmount(data['resAmount'] * (100 - slippage) / 100, decimals=6).Wei,
                    ['0x2144BF2003bFd9Aa0950716333fBb5B7A1Caeda4', '0x1F076a800005c758a505E759720eb6737136e893'],
                    ['0x5615a7b1619980f7D6B5E7f69f3dc093DFe0C95C', '0x189de4b78e750E525025Cd069148D7ab4DCBc978'],
                    ["0x2144BF2003bFd9Aa0950716333fBb5B7A1Caeda4", "0x1F076a800005c758a505E759720eb6737136e893",
                     contract.address],
                    1,
                    [
                        "0x000000000000000000000000e5d7c2a44ffddf6b295a15c148167daaaf5cf34f000000000000000000000000176211869ca2b568f2a7d4ee941e073a821ee1ff00000000000000000000000000000000000000000000000000000000000c3500",
                        "0x000000000000000000000000176211869ca2b568f2a7d4ee941e073a821ee1ff000000000000000000000000a219439258ca9da29e9cc4ce5596924745e12b930000000000000000000000000000000000000000000000000000000000000008"
                    ],
                    '0x00000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000000',
                    int(datetime.now(timezone.utc).timestamp()) + 600
                ])
                if await self.tx(
                        contract.address, 'Gamic', tx_data,
                        value=TokenAmount(int(data['value']), wei=True), check_existing=False
                ):
                    return True

    async def asmatch(self):
        return await self.tx(
            '0xc043bce9af87004398181a8de46b26e63b29bf99', 'AsMatch',
            '0xefef39a10000000000000000000000000000000000000000000000000000000000000001', value=TokenAmount(0.0001)
        )

    async def bitavatar(self):
        abi = [
            {
                "inputs": [
                    {
                        "name": "tokenURI",
                        "type": "string"
                    }
                ],
                "name": "mint",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        name = 'BitAvatar'
        contract = self.w3.eth.contract(
            self.w3.to_checksum_address('0x37d4bfc8c583d297a0740d734b271eac9a88ade4'),
            abi=abi
        )
        await self.tx(
            contract.address, name + ' (mint)', contract.encodeABI('mint', args=[
                f'https://api.bitavatar.io/v1/avatar/'
                f'{"".join(secrets.choice("0123456789ABCDEFabcdef") for _ in range(24))}'
            ])
        )
        return await self.tx(contract.address, name + ' (checkin)', '0x183ff085', check_existing=False)

    async def readon(self):
        name = 'ReadOn'
        abi = [
            {
                "inputs": [
                    {
                        "internalType": "uint64",
                        "name": "contentUrl",
                        "type": "uint64"
                    }
                ],
                "name": "curate",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        async with ProfileSession(self.profile, headers={'Origin': 'https://content-hub.readon.me'}) as session:
            response, data = await session.post(
                url='https://readon-api.readon.me/web/wallet_login',
                json={
                    'from': 'web', 'login_type': 4, 'signature': self.sign('readon.me'),
                    'wallet_address': self.account.address, 'wallet_type': 5
                }
            )
            token = data['data']['token']
            session.headers.update({'Authorization': token})
            response, data = await session.post(
                url='https://readon-api.readon.me/v1/content_incubator/signature',
                json={
                    'url': random.choice([
                        "https://readonofficial.medium.com/readon-launches-content-hub-beta-join-to-discover-web3-contents-and-earn-read-testnet-tokens-da431af43e12",
                        "https://medium.com/@nodescience/run-63818b5be701",
                        "https://linea.mirror.xyz/wxR9tSVgraWqquTAhwAMARZPEWDMwmWxFSrtigJuzVw",
                        "https://mirror.xyz/wmp.eth/Ct08_eWfgzf1HjboKsDvoJz1UwPmG-Ste0zDPBYLBEM"
                    ]),
                    'wallet_address': self.account.address
                }
            )
            token_id = data['data']['token_id']
            contract = self.w3.eth.contract(
                address=self.w3.to_checksum_address('0x8286d601a0ed6cf75e067e0614f73a5b9f024151'),
                abi=abi
            )
            return await self.tx(
                to=contract.address,
                name=name,
                data=contract.encodeABI('curate', args=[int(token_id)]),
                check_existing=False
            )

    async def sendingme(self):
        await self.tx(
            '0x2933749E45796D50eBA9A352d29EeD6Fe58af8BB', 'SendingMe (Money Gun)',
            '0xf02bc6d500000000000000000000000000000000000000000000000000005af3107a4000000000000000000000000000eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee',
            value=TokenAmount(0.0001), check_existing=False
        )
        return await self.tx(self.account.address, 'SendingMe (Transfer)', data='', check_existing=False)

    async def social_scan(self):
        name = 'SocialScan'
        abi = [
            {
                "inputs": [
                    {
                        "internalType": "address",
                        "name": "signer",
                        "type": "address"
                    },
                    {
                        "internalType": "address",
                        "name": "to",
                        "type": "address"
                    },
                    {
                        "internalType": "uint256",
                        "name": "tokenID",
                        "type": "uint256"
                    },
                    {
                        "internalType": "string",
                        "name": "uri",
                        "type": "string"
                    },
                    {
                        "internalType": "bytes",
                        "name": "signature",
                        "type": "bytes"
                    }
                ],
                "name": "mintWithSignature",
                "outputs": [],
                "stateMutability": "payable",
                "type": "function"
            }
        ]
        random_bytes = secrets.token_bytes(32)
        hex_string = random_bytes.hex()
        current_time_utc = datetime.now(timezone.utc)
        message = (
            f"Login with this account\n\ntime: {current_time_utc.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'}\n"
            f"{hex_string}"
        )
        signature = self.sign(message)
        headers = {
            'Origin': 'https://socialscan.io',
            'Referer': 'https://socialscan.io/campaign/linea-park'
        }
        async with ProfileSession(self.profile, headers=headers) as session:
            response, data = await session.post(
                url='https://api.w3w.ai/v1/socialscan/user/login',
                json={'wallet_address': self.account.address.lower(), 'message': message, 'signature': signature}
            )
            auth = data['auth']
            session.headers.update({'Authorization': auth})

            response, data = await session.get(url='https://api.w3w.ai/v1/socialscan/user/badges')
            badges = [badge['id'] for badge in data['badges']]
            if 'linea_data_scanner' not in badges:
                response, data = await session.post(
                    url='https://api.w3w.ai/v1/socialscan/user/task/sign_mint_badge',
                    json={'badge_type': 'linea_data_scanner'}
                )
                contract = self.w3.eth.contract(self.w3.to_checksum_address(data['contract_address']), abi=abi)
                await self.tx(
                    contract.address, name + ' (Linea Data Scanner)',
                    contract.encodeABI('mintWithSignature', args=[
                        self.w3.to_checksum_address(data['signer_address']), self.account.address,
                        data['token_id'],
                        data['token_uri'], data['signed_message']
                    ])
                )
            else:
                logger.success(
                    f'{self.profile.id} | {self.account.address} | {name} (Linea Data Scanner) already minted'
                )
            if 'linea_gang' not in badges:
                response, data = await session.get(url='https://api.w3w.ai/v1/socialscan/user/profile')
                if data['followings_count'] < 5:
                    response, data = await session.get(
                        url='https://api.w3w.ai/v1/socialscan/wallet/recommendations',
                        params={'wallet': self.account.address.lower()}
                    )
                    for wallet in data:
                        await session.post(
                            url='https://api.w3w.ai/v1/socialscan/user/follow',
                            json={'followed_wallet_address': wallet['wallet_address']}
                        )

                response, data = await session.post(
                    url='https://api.w3w.ai/v1/socialscan/user/task/sign_mint_badge',
                    json={'badge_type': 'linea_gang'}
                )
                contract = self.w3.eth.contract(self.w3.to_checksum_address(data['contract_address']), abi=abi)
                return await self.tx(
                    contract.address, name + ' (Linea Gang)', contract.encodeABI('mintWithSignature', args=[
                        self.w3.to_checksum_address(data['signer_address']), self.account.address, data['token_id'],
                        data['token_uri'], data['signed_message']
                    ])
                )
            else:
                logger.success(
                    f'{self.profile.id} | {self.account.address} | {name} (Linea Gang) already minted'
                )
                return True

    async def abyss_world(self):
        return await self.tx(
            '0x0391c15886b5f74a776b404c82d30eef4be88335', 'Abyss World',
            '0xefef39a10000000000000000000000000000000000000000000000000000000000000001', value=TokenAmount(0.0001)
        )

    async def pictographs(self):
        abi = [
            {
                "inputs": [
                    {
                        "internalType": "address",
                        "name": "owner",
                        "type": "address"
                    }
                ],
                "name": "getOwnedTokens",
                "outputs": [
                    {
                        "internalType": "uint256[]",
                        "name": "",
                        "type": "uint256[]"
                    }
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {
                        "internalType": "uint256",
                        "name": "tokenId",
                        "type": "uint256"
                    }
                ],
                "name": "stake",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [],
                "name": "mintNFT",
                "outputs": [],
                "stateMutability": "payable",
                "type": "function"
            }
        ]
        contract = self.w3.eth.contract(
            self.w3.to_checksum_address('0xb18b7847072117ae863f71f9473d555d601eb537'),
            abi=abi
        )
        return await self.tx(contract.address, 'Pictographs (mint)', contract.encodeABI('mintNFT'))

    async def satoshi_universe(self):
        name = 'Satoshi Universe'
        abi = [
            {
                "inputs": [
                    {
                        "components": [
                            {
                                "internalType": "address",
                                "name": "to",
                                "type": "address"
                            },
                            {
                                "internalType": "address",
                                "name": "collection",
                                "type": "address"
                            },
                            {
                                "internalType": "uint24",
                                "name": "quantity",
                                "type": "uint24"
                            },
                            {
                                "internalType": "bytes32[]",
                                "name": "merkleProof",
                                "type": "bytes32[]"
                            },
                            {
                                "internalType": "uint8",
                                "name": "phaseId",
                                "type": "uint8"
                            },
                            {
                                "internalType": "bytes",
                                "name": "payloadForCall",
                                "type": "bytes"
                            }
                        ],
                        "internalType": "struct MintParams",
                        "name": "_params",
                        "type": "tuple"
                    }
                ],
                "name": "mint",
                "outputs": [],
                "stateMutability": "payable",
                "type": "function"
            }
        ]
        collection_address = '0x0dE240B2A3634fCD72919eB591A7207bDdef03cd'
        if (await self.balance_of(token_address=collection_address)).Ether > 0:
            logger.success(f'{self.profile.id} | {self.account.address} | {name} already minted')
            return True
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address('0xecbee1a087aa83db1fcc6c2c5effc30bcb191589'),
            abi=abi
        )
        return await self.tx(
            to=contract.address, name=name,
            data=contract.encodeABI('mint', args=[(
                str(self.account.address),
                collection_address,
                1,
                [],
                1,
                b""
            )]), value=TokenAmount(0.00015), check_existing=False
        )

    async def yooldo(self):
        return await self.tx(
            '0x63ce21bd9af8cc603322cb025f26db567de8102b', 'Yooldo', '0xfb89f3b1',
            value=TokenAmount(0.0001), check_existing=False
        )

    async def gamerboom(self):
        await self.tx(
            '0x6cd20be8914a9be48f2a35e56354490b80522856', 'GamerBoom (sign genesis proof)',
            '0xb9a2092d', check_existing=False
        )
        await sleep(10, 20)
        return await self.tx('0xc0b4ab5cb0fdd6f5dfddb2f7c10c4c6013f97bf2', 'GamerBoom (mint oat)')

    async def nidium(self):
        abi = [
            {
                "inputs": [
                    {
                        "internalType": "uint256[]",
                        "name": "_tokenID",
                        "type": "uint256[]"
                    },
                    {
                        "internalType": "uint256[]",
                        "name": "_nftAmountForMint",
                        "type": "uint256[]"
                    },
                    {
                        "internalType": "uint256",
                        "name": "_nonce",
                        "type": "uint256"
                    },
                    {
                        "internalType": "bytes32",
                        "name": "_msgForSign",
                        "type": "bytes32"
                    },
                    {
                        "internalType": "bytes",
                        "name": "_signature",
                        "type": "bytes"
                    }
                ],
                "name": "mintFromShadowBatch",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            },
            {
                "inputs": [
                    {
                        "internalType": "address",
                        "name": "account",
                        "type": "address"
                    },
                    {
                        "internalType": "uint256",
                        "name": "id",
                        "type": "uint256"
                    }
                ],
                "name": "balanceOf",
                "outputs": [
                    {
                        "internalType": "uint256",
                        "name": "",
                        "type": "uint256"
                    }
                ],
                "stateMutability": "view",
                "type": "function"
            },
            {
                "inputs": [
                    {
                        "internalType": "address",
                        "name": "account",
                        "type": "address"
                    },
                    {
                        "internalType": "uint256",
                        "name": "_tokenID",
                        "type": "uint256"
                    },
                    {
                        "internalType": "uint256",
                        "name": "amount",
                        "type": "uint256"
                    }
                ],
                "name": "burn",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        name = 'Nidium Mystery Box 2'
        contract_address = '0x34be5b8c30ee4fde069dc878989686abe9884470'
        contract = self.w3.eth.contract(
            address=self.w3.to_checksum_address(contract_address),
            abi=abi
        )
        if not await contract.functions.balanceOf(self.account.address, 9).call() > 0:
            headers = {
                'Origin': 'https://play.sidusheroes.com',
                'Referer': 'https://play.sidusheroes.com/'
            }
            async with ProfileSession(self.profile, headers=headers) as session:
                try:
                    response, data = await session.get(
                        url=f'https://auth.sidusheroes.com/api/v1/users/{self.account.address.lower()}'
                    )
                    nonce = data['data']['nonce']
                except RequestsError:
                    response, data = await session.post(
                        url='https://auth.sidusheroes.com/api/v1/users',
                        json={'address': self.account.address.lower()}
                    )
                    nonce = data['data']['nonce']
                message = f'Please sign this message to connect to sidusheroes.com: {nonce}'
                signature = self.sign(message)
                response, data = await session.post(
                    url='https://auth.sidusheroes.com/api/v1/auth',
                    json={'address': self.account.address.lower(), 'signature': signature}
                )
                token = data['data']['accessToken']
                session.headers.update({'Authorization': f'Bearer {token}'})
                try:
                    response, data = await session.post(
                        url=f'https://plsrv.sidusheroes.com/shadow-game-linea/api/v1/item',
                        json={'contract': contract.address, 'tokenId': 9, 'user': self.account.address.lower()}
                    )
                except RequestsError:
                    pass
                try:
                    response, data = await session.post(
                        url='https://plsrv.sidusheroes.com/shadow-game-linea/api/v1/claim',
                        json={
                            'contract': contract_address, 'user': self.account.address.lower(),
                            'tokensData': [{'tokenId': 9, 'amount': "1"}]
                        }
                    )
                except (TypeError, RequestsError):
                    logger.warning(f'{self.profile.id} | {self.account.address} | {name} couldn\'t mint')
                    return
                message = data['message']
                signature = data['signature']
                nonce = data['nonce']
                await self.tx(
                    contract_address, name, contract.encodeABI('mintFromShadowBatch', args=[
                        [9], [1], nonce, message, signature
                    ]), check_existing=False
                )
                await sleep(10, 20)
        else:
            logger.success(f'{self.profile.id} | {self.account.address} | {name} already minted')
        return await self.tx(contract.address, f'{name} (burn)', contract.encodeABI('burn', args=[
            self.account.address, 9, 1
        ]), check_existing=False)

    async def galactic_exploration(self):
        name = 'Galactic Exploration'
        if not (await self.balance_of(token_address='0xDA36dF0764d138993F9811353EcADD6B32CAAFb9')).Ether > 0:
            abi = [
                {
                    "inputs": [
                        {
                            "internalType": "bytes",
                            "name": "signature",
                            "type": "bytes"
                        },
                        {
                            "internalType": "uint256",
                            "name": "passId",
                            "type": "uint256"
                        },
                        {
                            "internalType": "uint256",
                            "name": "deadline",
                            "type": "uint256"
                        }
                    ],
                    "name": "createAccountSign",
                    "outputs": [],
                    "stateMutability": "payable",
                    "type": "function"
                }
            ]
            contract = self.w3.eth.contract(
                self.w3.to_checksum_address('0x281a95769916555d1c97036e0331b232b16edabc'),
                abi=abi
            )
            headers = {
                'Origin': 'https://game.townstory.io',
                'Referer': 'https://game.townstory.io/'
            }
            address = self.account.address.lower()[:19] + '...' + self.account.address.lower()[24:]
            message = (
                "Welcome to Town Story! \n\nClick to sign in and accept the Town Story\n"
                "Terms of Service:\nhttps://townstory.io/\n\nThis request will not trigger a blockchain\n"
                "transaction or cost any gas fees.\n\nYour authentication status will reset after\neach session.\n\n"
                f"Wallet address:\n{address}\n\nNonce: {int(time() / 86400)}"
            )
            signature = self.sign(message)
            async with ProfileSession(self.profile, headers=headers) as session:
                form_data = {
                    "header": {
                        "referer": "",
                        "baseVersion": "1.0.0",
                        "version": "1.0.1"
                    },
                    "transaction": {
                        "func": "register.loginByWallet",
                        "params": {
                            "address": self.account.address.lower(),
                            "signature": signature,
                            "platform": 301,
                            "chain": "linea",
                            "wallet": "metamask",
                            "hall": 0
                        }
                    }
                }
                response, data = await session.post(
                    url='https://aws-login.townstory.io/town-login/handler.php',
                    data=json.dumps(form_data)
                )
                deadline = data['response']['deadline']
                signature = data['response']['signature']
                pass_id = data['response']['passId']
                if not await self.tx(
                        contract.address, name,
                        contract.encodeABI('createAccountSign', args=[signature, pass_id, deadline]),
                        check_existing=False
                ):
                    return False
        else:
            logger.success(f'{self.profile.id} | {self.account.address} | {name} already created account')

        abi = [
            {
                "inputs": [
                    {
                        "internalType": "bytes",
                        "name": "signature",
                        "type": "bytes"
                    },
                    {
                        "internalType": "address",
                        "name": "_addr",
                        "type": "address"
                    },
                    {
                        "internalType": "uint256",
                        "name": "deadline",
                        "type": "uint256"
                    }
                ],
                "name": "claimLineaTravelbag",
                "outputs": [],
                "stateMutability": "nonpayable",
                "type": "function"
            }
        ]
        contract = self.w3.eth.contract(
            self.w3.to_checksum_address('0xd41ac492fedc671eb965707d1dedad4eb7b6efc5'),
            abi=abi
        )
        await sleep(10, 20)
        headers = {'Origin': 'https://townstory.io', 'Referer': 'https://townstory.io/linea'}
        async with ProfileSession(self.profile, headers=headers) as session:
            response, data = await session.post(
                url='https://townstory.io//api',
                data={'action': 'getLineaSign', 'address': self.account.address.lower()}
            )
            return await self.tx(
                contract.address, name + ' (Linea Travel Bag)', contract.encodeABI('claimLineaTravelbag', args=[
                    data['signature'], self.account.address, data['deadline']
                ]), check_existing=False
            )

    async def start(self):
        for week in random.sample(self.tasks, len(self.tasks)):
            for task_name, task in random.sample(sorted(week.items()), len(week)):
                if not await get_task_status(self.profile.evm_address, task_name):
                    if await task():
                        await task_done(self.profile.evm_address, task_name)
                        await sleep(30, 60)
                else:
                    logger.success(f'{self.profile.id} | {self.account.address} | {task_name} already done')
                    await task_done(self.profile.evm_address, task_name)
        logger.success(f'{self.profile.id} | {self.account.address} | All tasks done')


async def start(profile: Profile):
    if not await select_profile(profile.id):
        await insert_record(profile.evm_address, profile.id)
    park = LineaPark(profile)
    await park.start()


async def main():
    tasks = []
    profiles: list[Profile] = await db.get_all_from_table(Profile)
    for profile in profiles:
        tasks.append(asyncio.create_task(start(profile)))
    await asyncio.gather(*tasks)


if __name__ == "__main__":
    asyncio.run(main())
