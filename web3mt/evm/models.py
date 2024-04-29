import asyncio
from dataclasses import dataclass
from decimal import Decimal
from typing import Union
from web3db import Profile


@dataclass
class DefaultABIs:
    """
    The default ABIs.
    """
    Token = [
        {
            'constant': True,
            'inputs': [],
            'name': 'name',
            'outputs': [{'name': '', 'type': 'string'}],
            'payable': False,
            'stateMutability': 'view',
            'type': 'function'
        },
        {
            'constant': True,
            'inputs': [],
            'name': 'symbol',
            'outputs': [{'name': '', 'type': 'string'}],
            'payable': False,
            'stateMutability': 'view',
            'type': 'function'
        },
        {
            'constant': True,
            'inputs': [],
            'name': 'totalSupply',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'payable': False,
            'stateMutability': 'view',
            'type': 'function'
        },
        {
            'constant': True,
            'inputs': [],
            'name': 'decimals',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'payable': False,
            'stateMutability': 'view',
            'type': 'function'
        },
        {
            'constant': True,
            'inputs': [{'name': 'who', 'type': 'address'}],
            'name': 'balanceOf',
            'outputs': [{'name': '', 'type': 'uint256'}],
            'payable': False,
            'stateMutability': 'view',
            'type': 'function'
        },
        {
            'constant': True,
            'inputs': [{'name': '_owner', 'type': 'address'}, {'name': '_spender', 'type': 'address'}],
            'name': 'allowance',
            'outputs': [{'name': 'remaining', 'type': 'uint256'}],
            'payable': False,
            'stateMutability': 'view',
            'type': 'function'
        },
        {
            'constant': False,
            'inputs': [{'name': '_spender', 'type': 'address'}, {'name': '_value', 'type': 'uint256'}],
            'name': 'approve',
            'outputs': [],
            'payable': False,
            'stateMutability': 'nonpayable',
            'type': 'function'
        },
        {
            'constant': False,
            'inputs': [{'name': '_to', 'type': 'address'}, {'name': '_value', 'type': 'uint256'}],
            'name': 'transfer',
            'outputs': [], 'payable': False,
            'stateMutability': 'nonpayable',
            'type': 'function'
        }]


class TokenAmount:
    Wei: int
    Ether: Decimal
    decimals: int

    def __init__(self, amount: Union[int, float, str, Decimal], decimals: int = 18, wei: bool = False) -> None:
        if wei:
            self.Wei: int = amount
            self.Ether: Decimal = Decimal(str(amount)) / 10 ** decimals

        else:
            self.Wei: int = int(Decimal(str(amount)) * 10 ** decimals)
            self.Ether: Decimal = Decimal(str(amount))

        self.decimals = decimals

    def __str__(self) -> str:
        return str(self.Ether)

    def __eq__(self, other):
        return self.Wei == other.Wei

    def __bool__(self):
        return bool(self.Wei)


class Chain:
    def __init__(
            self,
            name: str,
            rpc: str,
            chain_id: int,
            eip1559_tx: bool,
            coin_symbol: str,
            explorer: str,
            decimals: int = 18,
            max_gwei: int = 15
    ):
        self._name = name
        self._rpc = rpc
        self._chain_id = chain_id
        self._eip1559_tx = eip1559_tx
        self._coin_symbol = coin_symbol
        self._explorer = explorer.rstrip('/')
        self._decimals = decimals
        self._max_gwei = max_gwei

    def __str__(self):
        return f'{self.name}'

    @property
    def name(self):
        return self._name

    @property
    def rpc(self):
        return self._rpc

    @property
    def chain_id(self):
        return self._chain_id

    @property
    def eip1559_tx(self):
        return self._eip1559_tx

    @property
    def coin_symbol(self):
        return self._coin_symbol

    @property
    def explorer(self):
        return self._explorer

    @property
    def decimals(self):
        return self._decimals

    @property
    def max_gwei(self):
        return self._max_gwei

    @name.setter
    def name(self, value):
        self._name = value

    @rpc.setter
    def rpc(self, value):
        self._rpc = value

    @chain_id.setter
    def chain_id(self, value):
        self._chain_id = value

    @eip1559_tx.setter
    def eip1559_tx(self, value):
        self._eip1559_tx = value

    @coin_symbol.setter
    def coin_symbol(self, value):
        self._coin_symbol = value

    @explorer.setter
    def explorer(self, value):
        self._explorer = value

    @decimals.setter
    def decimals(self, value):
        self._decimals = value

    @max_gwei.setter
    def max_gwei(self, value):
        self._max_gwei = value


Ethereum = Chain(
    name='Ethereum',
    rpc='https://ethereum.publicnode.com',
    chain_id=1,
    eip1559_tx=True,
    coin_symbol='ETH',
    explorer='https://etherscan.io/',
    max_gwei=15
)

Arbitrum = Chain(
    name='Arbitrum',
    rpc='https://rpc.ankr.com/arbitrum/',
    chain_id=42161,
    eip1559_tx=True,
    coin_symbol='ETH',
    explorer='https://arbiscan.io/',
)

Optimism = Chain(
    name='Optimism',
    rpc='https://rpc.ankr.com/optimism/',
    chain_id=10,
    eip1559_tx=True,
    coin_symbol='ETH',
    explorer='https://optimistic.etherscan.io/',
)
OP_Sepolia = Chain(
    name='Optimism Sepolia',
    rpc='https://sepolia.optimism.io',
    chain_id=11155420,
    eip1559_tx=True,
    coin_symbol='ETH',
    explorer='https://optimism-sepolia.blockscout.com/',
)

Polygon = Chain(
    name='Polygon',
    rpc='https://polygon-rpc.com/',
    chain_id=137,
    eip1559_tx=True,
    coin_symbol='MATIC',
    explorer='https://polygonscan.com/',
)
Mumbai = Chain(
    name='Mumbai',
    rpc='https://polygon-mumbai-bor-rpc.publicnode.com',
    chain_id=80001,
    eip1559_tx=True,
    coin_symbol='MATIC',
    explorer='https://mumbai.polygonscan.com/'
)

Avalanche = Chain(
    name='Avalanche',
    rpc='https://rpc.ankr.com/avalanche/',
    chain_id=43114,
    eip1559_tx=True,
    coin_symbol='AVAX',
    explorer='https://snowtrace.io/',
)

Fantom = Chain(
    name='Fantom',
    rpc='https://rpc.ankr.com/fantom/',
    chain_id=250,
    eip1559_tx=True,
    coin_symbol='FTM',
    explorer='https://ftmscan.com/',
)

opBNB = Chain(
    name='opBNB',
    rpc='https://opbnb.publicnode.com',
    chain_id=204,
    eip1559_tx=True,
    coin_symbol='BNB',
    explorer='https://bscscan.com/'
)

BNB = Chain(
    name='BNB',
    rpc='https://bsc.meowrpc.com',
    chain_id=56,
    eip1559_tx=True,
    coin_symbol='BNB',
    explorer='https://bscscan.com/'
)

Linea = Chain(
    name='Linea',
    rpc='https://rpc.linea.build',
    chain_id=59144,
    eip1559_tx=True,
    coin_symbol='ETH',
    explorer='https://lineascan.build/'
)

zkSync = Chain(
    name='zkSync',
    rpc='https://mainnet.era.zksync.io',
    chain_id=324,
    eip1559_tx=True,
    coin_symbol='ETH',
    explorer='https://explorer.zksync.io/'
)

ZetaChain = Chain(
    name='Zetachain',
    rpc='https://zetachain-evm.blockpi.network/v1/rpc/public',
    chain_id=7000,
    eip1559_tx=True,
    coin_symbol='ZETA',
    explorer='https://zetachain.blockscout.com/'
)
from web3mt.evm.client import Client


class Scroll(Chain, Client):
    def __init__(self, profile: Profile, encryption_password: str):
        Chain.__init__(
            self,
            name='Scroll',
            rpc='https://scroll.drpc.org',
            chain_id=534352,
            eip1559_tx=True,
            coin_symbol='ETH',
            explorer='https://scrollscan.com/'
        )
        Client.__init__(self, self, profile, encryption_password=encryption_password)

    async def withdraw(self, amount: TokenAmount = None) -> bool:
        contract = self.w3.eth.contract(
            self.w3.to_checksum_address('0x781e90f1c8fc4611c9b7497c3b47f99ef6969cbc'),
            abi=[
                {"inputs": [
                    {
                        "internalType": "address",
                        "name": "_to",
                        "type": "address"
                    },
                    {
                        "internalType": "uint256",
                        "name": "_value",
                        "type": "uint256"
                    },
                    {
                        "internalType": "bytes",
                        "name": "_message",
                        "type": "bytes"
                    },
                    {
                        "internalType": "uint256",
                        "name": "_gasLimit",
                        "type": "uint256"
                    }
                ],
                    "name": "sendMessage",
                    "outputs": [],
                    "stateMutability": "payable",
                    "type": "function"}
            ]
        )
        tx_params = {
            'from': self.account.address,
            'value': int((await self.get_native_balance()).Wei * 0.9),
            'nonce': await self.nonce(),
            'gasPrice': await self.w3.eth.gas_price,
        }
        tx_params['gas'] = await self.w3.eth.estimate_gas(
            {
                **tx_params,
                'to': contract.address,
                'data': contract.encodeABI('sendMessage', args=[
                    self.account.address,
                    int((await self.get_native_balance()).Wei * 0.9),
                    b'',
                    0
                ])
            }
        )
        tx = await contract.functions.sendMessage(
            self.account.address,
            int((await self.get_native_balance()).Wei * 0.9),
            b'',
            0
        ).build_transaction(tx_params)
        return tx
        # return await self.tx(
        #     '0x781e90f1c8fc4611c9b7497c3b47f99ef6969cbc', 'Bridge to Ethereum',
        #     contract.encodeABI('sendMessage', args=[self.account.address, (amount.Wei)]),
        #     full_balance=bool(amount)
        # )


Zora = Chain(
    name='Zora',
    rpc='https://rpc.zora.energy',
    chain_id=7777777,
    eip1559_tx=True,
    coin_symbol='ETH',
    explorer='https://zora.superscan.network/'
)

Base = Chain(
    name='Base',
    rpc='https://base.llamarpc.com',
    chain_id=8453,
    eip1559_tx=True,
    coin_symbol='ETH',
    explorer='https://basescan.com/'
)
