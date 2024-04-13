from dataclasses import dataclass
from decimal import Decimal
from typing import Union


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
        self.name = name
        self.rpc = rpc
        self.chain_id = chain_id
        self.eip1559_tx = eip1559_tx
        self.coin_symbol = coin_symbol
        self.decimals = decimals
        self.explorer = explorer
        self.max_gwei = max_gwei

    def __str__(self):
        return f'{self.name}'


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
    explorer='https://explorer.zetachain.com/'
)

Scroll = Chain(
    name='Scroll',
    rpc='https://scroll.drpc.org',
    chain_id=534352,
    eip1559_tx=True,
    coin_symbol='ETH',
    explorer='https://scrollscan.com/'
)

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
