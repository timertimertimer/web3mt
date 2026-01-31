import asyncio
from dataclasses import dataclass
from _decimal import Decimal, InvalidOperation
from eth_utils import to_checksum_address

from web3mt.models import Coin
from web3mt.utils import format_number, logger
from typing import Union, TYPE_CHECKING

if TYPE_CHECKING:
    from web3mt.onchain.aptos.models import Token as AptosToken

__all__ = [
    "DefaultABIs",
    "Token",
    "TokenAmount",
    "Chain",
    "Ethereum",
    "Arbitrum",
    "Optimism",
    "Polygon",
    "BSC",
    "Linea",
    "zkSync",
    "Scroll",
    "Zora",
    "Base",
    "Metis",
    "opBNB",
    "Avalanche",
    "ETHEREUM_TOKENS",
    "BASE_TOKENS",
    "SCROLL_TOKENS",
    "BSC_TOKENS",
    "ARBITRUM_TOKENS",
    "POLYGON_TOKENS",
    "OPTIMISM_TOKENS",
    "ZKSYNC_TOKENS",
    "LINEA_TOKENS",
    "ZORA_TOKENS",
    "TOKENS",
]


@dataclass
class DefaultABIs:
    token = [
        {
            "constant": True,
            "inputs": [],
            "name": "name",
            "outputs": [{"name": "", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "symbol",
            "outputs": [{"name": "", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "totalSupply",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [{"name": "who", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [
                {"name": "_owner", "type": "address"},
                {"name": "_spender", "type": "address"},
            ],
            "name": "allowance",
            "outputs": [{"name": "remaining", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "_spender", "type": "address"},
                {"name": "_value", "type": "uint256"},
            ],
            "name": "approve",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "_to", "type": "address"},
                {"name": "_value", "type": "uint256"},
            ],
            "name": "transfer",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
    ]
    WETH = [
        {
            "constant": True,
            "inputs": [],
            "name": "name",
            "outputs": [{"name": "", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "guy", "type": "address"},
                {"name": "wad", "type": "uint256"},
            ],
            "name": "approve",
            "outputs": [{"name": "", "type": "bool"}],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "totalSupply",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "src", "type": "address"},
                {"name": "dst", "type": "address"},
                {"name": "wad", "type": "uint256"},
            ],
            "name": "transferFrom",
            "outputs": [{"name": "", "type": "bool"}],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [{"name": "wad", "type": "uint256"}],
            "name": "withdraw",
            "outputs": [],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "decimals",
            "outputs": [{"name": "", "type": "uint8"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [{"name": "", "type": "address"}],
            "name": "balanceOf",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [],
            "name": "symbol",
            "outputs": [{"name": "", "type": "string"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [
                {"name": "dst", "type": "address"},
                {"name": "wad", "type": "uint256"},
            ],
            "name": "transfer",
            "outputs": [{"name": "", "type": "bool"}],
            "payable": False,
            "stateMutability": "nonpayable",
            "type": "function",
        },
        {
            "constant": False,
            "inputs": [],
            "name": "deposit",
            "outputs": [],
            "payable": True,
            "stateMutability": "payable",
            "type": "function",
        },
        {
            "constant": True,
            "inputs": [
                {"name": "", "type": "address"},
                {"name": "", "type": "address"},
            ],
            "name": "allowance",
            "outputs": [{"name": "", "type": "uint256"}],
            "payable": False,
            "stateMutability": "view",
            "type": "function",
        },
        {"payable": True, "stateMutability": "payable", "type": "fallback"},
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "src", "type": "address"},
                {"indexed": True, "name": "guy", "type": "address"},
                {"indexed": False, "name": "wad", "type": "uint256"},
            ],
            "name": "Approval",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "src", "type": "address"},
                {"indexed": True, "name": "dst", "type": "address"},
                {"indexed": False, "name": "wad", "type": "uint256"},
            ],
            "name": "Transfer",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "dst", "type": "address"},
                {"indexed": False, "name": "wad", "type": "uint256"},
            ],
            "name": "Deposit",
            "type": "event",
        },
        {
            "anonymous": False,
            "inputs": [
                {"indexed": True, "name": "src", "type": "address"},
                {"indexed": False, "name": "wad", "type": "uint256"},
            ],
            "name": "Withdrawal",
            "type": "event",
        },
    ]


class Token(Coin):
    _instances = {}

    ethereum_symbol = "ETH"
    native_token_address = "0xEeeeeEeeeEeEeeEeEeEeeEEEeeeeEeeeeeeeEEeE"
    burner_address = "0x0000000000000000000000000000000000000000"

    def __new__(
        cls,
        chain: "Chain" = None,
        symbol: str = ethereum_symbol,
        address: str = native_token_address,
        decimals: int = 18,
        **kwargs,
    ):
        key = (
            chain,
            symbol,
            address,
            decimals,
        )
        if key not in cls._instances:
            cls._instances[key] = object.__new__(cls)
        return cls._instances[key]

    def __init__(
        self,
        chain: Union["Chain", int],
        symbol: str = ethereum_symbol,
        address: str = native_token_address,  # TODO: calculate address dynamically
        decimals: int = 18,
        price: Decimal | float = None,
        **kwargs,
    ):
        if isinstance(chain, int):
            chain = Chain._instances[chain]
        self.chain = chain
        self.decimals = decimals
        self.address = to_checksum_address(address)
        super().__init__(symbol, price)

    def __eq__(self, other):
        if isinstance(other, Token):
            return (
                self.symbol == other.symbol
                and any(
                    (
                        self.address == other.address,
                        self.address in [self.native_token_address, self.burner_address]
                        and other.address
                        in [self.native_token_address, self.burner_address],
                    )
                )
                and self.decimals == other.decimals
            )
        elif isinstance(other, Coin):
            return other.symbol == self.symbol
        return False

    def __repr__(self):
        return (
            f"Token(chain={self.chain.name}, symbol={self.symbol}, address={self.address}, decimals={self.decimals}"
            + (f", price={self.price}" if self.price else "")
            + ")"
        )

    def __str__(self):
        return self.symbol

    def __getitem__(self, token):
        return self._instances[
            (token.chain, token.symbol, token.address, token.decimals)
        ]

    @property
    def price(self) -> Decimal | None:
        return self._prices.get(self.get_unwrapped_symbol())

    @price.setter
    def price(self, value: int | float | str | Decimal):
        self._prices[self.get_unwrapped_symbol()] = Decimal(str(value))

    def get_unwrapped_symbol(self) -> str:
        symbol = self.symbol
        if self.symbol == "W" + self.chain.native_token.symbol:
            symbol = self.chain.native_token.symbol
        return symbol

    async def get_token_info(self) -> "Token":
        from web3mt.onchain.evm.client import BaseClient

        return await BaseClient(chain=self.chain).get_onchain_token_info(token=self)


class TokenAmount:
    def __init__(
        self,
        amount: int | float | str | Decimal,
        is_wei: bool = False,
        token: Union[Token, "AptosToken"] = None,
        **kwargs,
    ) -> None:
        self.token = token or Token(Ethereum)
        if is_wei:
            self._wei: int = int(amount)
            self._ether: Decimal = self._convert_wei_to_ether(amount)
        else:
            self._wei: int = self._convert_ether_to_wei(amount)
            self._ether: Decimal = Decimal(str(amount))

    def __str__(self) -> str:
        return f"{self.format_ether()} {self.token.symbol}" + (
            f" ({self.amount_in_usd:.2f}$)" if self.amount_in_usd else ""
        )

    def __repr__(self):
        return (
            f"TokenAmount(wei={self.wei}, ether={self.format_ether()}, symbol={self.token.symbol}, "
            f"chain={self.token.chain}"
            + (f", amount_in_usd={self.amount_in_usd}" if self.amount_in_usd else "")
            + ")"
        )

    def __eq__(self, other):
        if other == 0:
            return self.wei == 0
        from web3mt.cex.models import Asset

        if isinstance(other, Asset):
            return self.token == other.coin
        return self.token == other.token and self.wei == other.sats

    def __gt__(self, other):
        if not isinstance(other, TokenAmount):
            raise TypeError(f"Cannot compare {other} with {repr(self)}")
        return self.wei > other.wei

    def __bool__(self):
        return bool(self.wei)

    def __add__(self, other):
        if other == 0:
            return self
        if isinstance(other, TokenAmount) and self.token == other.token:
            return TokenAmount(self.wei + other.wei, True, self.token)
        raise TypeError(f"Cannot add {other} to {repr(self)}")

    def __radd__(self, other):
        if other == 0:
            return self
        if not isinstance(other, (TokenAmount, Decimal)):
            raise TypeError(f"Cannot add {other} to {repr(self)}")
        if other == 0:
            return self
        return self.__add__(other)

    def __sub__(self, other):
        if other == 0:
            return self
        if isinstance(other, TokenAmount) and self.token == other.token:
            return TokenAmount(self.wei - other.wei, True, self.token)
        raise TypeError(f"Cannot add {other} to {repr(self)}")

    def __mul__(self, other):
        if isinstance(other, (int, float)):
            return TokenAmount(int(self.wei * other), True, self.token)
        return NotImplemented

    def __rmul__(self, other):
        return self.__mul__(other)

    @property
    def wei(self):
        return self._wei

    @wei.setter
    def wei(self, value):
        self._wei = value
        self._ether = self._convert_wei_to_ether(value)

    @property
    def ether(self):
        return self._ether

    @ether.setter
    def ether(self, value):
        self._ether = value
        self._wei = self._convert_ether_to_wei(value)

    @property
    def amount_in_usd(self) -> Decimal | None:
        if self.token.price:
            return self.token.price * self.ether
        return None

    def format_ether(self) -> str:
        return format_number(self._ether)

    def _convert_wei_to_ether(self, amount: int | float | str | Decimal) -> Decimal:
        try:
            return Decimal(str(amount)) / 10**self.token.decimals
        except InvalidOperation as e:
            logger.error(f"Couldn't convert {amount} wei to ether: {e}")
            raise e

    def _convert_ether_to_wei(self, amount: int | float | str | Decimal) -> int:
        try:
            return int(Decimal(str(amount)) * 10**self.token.decimals)
        except InvalidOperation as e:
            logger.error(f"Couldn't convert {amount} ether to wei: {e}")
            raise e


class Chain:
    _instances = {}

    def __new__(
        cls,
        name: str,
        rpc: str,
        chain_id: int,
        explorer: str,
        max_gwei: int = None,
        eip1559_tx: bool = False,
        native_token: "Token" = None,
    ):
        if chain_id in cls._instances:
            raise ValueError(f"Instance with chain_id {chain_id} already exists.")
        instance = super().__new__(cls)
        cls._instances[chain_id] = instance
        return instance

    def __init__(
        self,
        name: str,
        rpc: str,
        chain_id: int,
        explorer: str,
        max_gwei: int = None,
        eip1559_tx: bool = False,
        native_token: "Token" = None,
    ):
        self.name = name
        self.rpc = rpc
        self.chain_id = chain_id
        self.eip1559_tx = eip1559_tx
        self.explorer = explorer.rstrip("/")
        self.max_gwei = max_gwei
        self.native_token = native_token or Token(self)

    def __str__(self):
        return self.name

    def __repr__(self):
        return (
            f"Chain(name={self.name}, rpc={self.rpc}, chain_id={self.chain_id}, explorer={self.explorer}, "
            f"max_gwei={self.max_gwei}, eip1559_tx={self.eip1559_tx}, native_token={self.native_token.symbol})"
        )

    @classmethod
    def get_by_name(cls, name: str) -> "Chain":
        if name.upper() in ["ERC-20", "ERC20"]:
            name = "Ethereum"
        for instance in cls._instances.values():
            if instance.name == name:
                return instance
        raise ValueError(f"No instance found with name {name}")


Ethereum = Chain(
    name="Ethereum",
    rpc="https://ethereum.publicnode.com",
    chain_id=1,
    explorer="https://etherscan.io/",
    max_gwei=5,
    eip1559_tx=True,
)
Sepolia = Chain(
    name="Sepolia",
    rpc="https://ethereum-sepolia-rpc.publicnode.com",
    chain_id=11155111,
    explorer="https://sepolia.etherscan.io/",
    eip1559_tx=True,
)

Arbitrum = Chain(
    name="Arbitrum One",
    rpc="https://arbitrum.gateway.tenderly.co/1RhHTwPZOQv3RtsoB0EJ51",
    chain_id=42161,
    explorer="https://arbiscan.io/",
    eip1559_tx=True,
)
ARB_Sepolia = Chain(
    name="Arbitrum Sepolia",
    rpc="https://endpoints.omniatech.io/v1/arbitrum/sepolia/public",
    chain_id=421614,
    explorer="https://sepolia.arbiscan.io/",
    eip1559_tx=True,
)

Optimism = Chain(
    name="Optimism",
    rpc="https://op-pokt.nodies.app",
    chain_id=10,
    explorer="https://optimistic.etherscan.io/",
    eip1559_tx=True,
)
OP_Sepolia = Chain(
    name="Optimism Sepolia",
    rpc="https://sepolia.optimism.io",
    chain_id=11155420,
    explorer="https://optimism-sepolia.blockscout.com/",
    eip1559_tx=True,
)

Polygon = Chain(
    name="Polygon",
    rpc="https://1rpc.io/matic",
    chain_id=137,
    explorer="https://polygonscan.com/",
    eip1559_tx=True,
)
Polygon.native_token.symbol = "POL"
Mumbai = Chain(
    name="Mumbai",
    rpc="https://polygon-testnet.public.blastapi.io",
    chain_id=80001,
    explorer="https://mumbai.polygonscan.com/",
    eip1559_tx=True,
)
Mumbai.native_token.symbol = "POL"

Avalanche = Chain(
    name="Avalanche C-Chain",
    rpc="https://rpc.ankr.com/avalanche/192d48a1a5b6c9408d2ef50d94e8fcc92902a511cf08e658473feca9f30650b9",
    chain_id=43114,
    explorer="https://snowtrace.io/",
    eip1559_tx=True,
)
Avalanche.native_token.symbol = "AVAX"

Fantom = Chain(
    name="Fantom",
    rpc="https://rpc.ankr.com/fantom/",
    chain_id=250,
    explorer="https://ftmscan.com/",
    eip1559_tx=True,
)
Fantom.native_token.symbol = "FTM"

opBNB = Chain(
    name="opBNB",
    rpc="https://opbnb.publicnode.com",
    chain_id=204,
    explorer="https://bscscan.com/",
    eip1559_tx=True,
)
opBNB.native_token.symbol = "BNB"

BSC = Chain(
    name="BSC",
    rpc="https://rpc.ankr.com/bsc/192d48a1a5b6c9408d2ef50d94e8fcc92902a511cf08e658473feca9f30650b9",
    chain_id=56,
    explorer="https://bscscan.com/",
    eip1559_tx=True,
)
BSC.native_token.symbol = "BNB"
Xterio = Chain(
    name="Xterio",
    rpc="https://xterio.alt.technology",
    chain_id=2702128,
    explorer="https://eth.xterscan.io",
    eip1559_tx=True,
)
Xterio.native_token.symbol = "BNB"

Linea = Chain(
    name="Linea",
    rpc="https://rpc.linea.build",
    chain_id=59144,
    explorer="https://lineascan.build/",
    eip1559_tx=True,
)

zkSync = Chain(
    name="zkSync",
    rpc="https://rpc.ankr.com/zksync_era",
    chain_id=324,
    explorer="https://explorer.zksync.io/",
    eip1559_tx=True,
)

ZetaChain = Chain(
    name="Zetachain",
    rpc="https://zetachain-evm.blockpi.network/v1/rpc/public",
    chain_id=7000,
    explorer="https://zetachain.blockscout.com/",
    eip1559_tx=True,
)
ZetaChain.native_token.symbol = "ZETA"

Scroll = Chain(
    name="Scroll",
    rpc="https://1rpc.io/scroll",
    chain_id=534352,
    explorer="https://scrollscan.com/",
    eip1559_tx=True,
)

Zora = Chain(
    name="Zora",
    rpc="https://rpc.zora.energy",
    chain_id=7777777,
    explorer="https://zora.superscan.network/",
    eip1559_tx=True,
)

Base = Chain(
    name="Base",
    rpc="https://base-rpc.publicnode.com",
    chain_id=8453,
    explorer="https://basescan.org/",
    eip1559_tx=True,
)

Metis = Chain(
    name="Metis",
    rpc="https://metis-pokt.nodies.app",
    chain_id=1088,
    explorer="https://explorer.metis.io/",
    eip1559_tx=False,
)
Metis.native_token.symbol = "METIS"

Fuji = Chain(
    name="Avalanche Fuji C-Chain",
    rpc="https://api.avax-test.network/ext/bc/C/rpc",
    chain_id=43113,
    explorer="https://testnet.snowtrace.io/",
    eip1559_tx=True,
)
Fuji.native_token.symbol = "AVAX"

Ronin = Chain(
    name="Ronin Chain",
    rpc="https://ronin.drpc.org",
    chain_id=2020,
    explorer="https://app.roninchain.com/",
    eip1559_tx=False,
)
Ronin.native_token.symbol = "RON"

ETHEREUM_TOKENS = dict(
    WETH=Token(Ethereum, address="0xc02aaa39b223fe8d0a0e5c4f27ead9083c756cc2"),
    USDT=Token(Ethereum, address="0xdAC17F958D2ee523a2206206994597C13D831ec7"),
    USDC=Token(Ethereum, address="0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"),
)
BASE_TOKENS = dict(
    WETH=Token(Base, address="0x4200000000000000000000000000000000000006"),
    USDC=Token(Base, address="0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"),
    USDT=Token(Base, address="0xfde4C96c8593536E31F229EA8f37b2ADa2699bb2"),
)
SCROLL_TOKENS = dict(
    WETH=Token(Scroll, address="0x5300000000000000000000000000000000000004"),
    SCR=Token(Scroll, address="0xd29687c813d741e2f938f4ac377128810e217b1b"),
    USDT=Token(Scroll, address="0xf55BEC9cafDbE8730f096Aa55dad6D22d44099Df"),
    USDC=Token(Scroll, address="0x06eFdBFf2a14a7c8E15944D1F4A48F9F95F663A4"),
)
BSC_TOKENS = dict(
    USDC=Token(BSC, address="0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"),
    USDT=Token(BSC, address="0x55d398326f99059fF775485246999027B3197955"),
)
ARBITRUM_TOKENS = dict(
    WETH=Token(Arbitrum, address="0x82aF49447D8a07e3bd95BD0d56f35241523fBab1"),
    USDC=Token(Arbitrum, address="0xaf88d065e77c8cC2239327C5EDb3A432268e5831"),
    USDT=Token(Arbitrum, address="0xFd086bC7CD5C481DCC9C85ebE478A1C0b69FCbb9"),
)
POLYGON_TOKENS = dict(
    USDT=Token(Polygon, address="0xc2132D05D31c914a87C6611C10748AEb04B58e8F"),
    USDC=Token(Polygon, address="0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"),
)
OPTIMISM_TOKENS = dict(
    WETH=Token(Optimism, address="0x4200000000000000000000000000000000000006"),
    USDT=Token(Optimism, address="0x94b008aA00579c1307B0EF2c499aD98a8ce58e58"),
    USDC=Token(Optimism, address="0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85"),
)
ZKSYNC_TOKENS = dict(
    WETH=Token(zkSync, address="0xf00DAD97284D0c6F06dc4Db3c32454D4292c6813"),
    USDT=Token(zkSync, address="0x493257fD37EDB34451f62EDf8D2a0C418852bA4C"),
    USDC=Token(zkSync, address="0x1d17CBcF0D6D143135aE902365D2E5e2A16538D4"),
)
ZORA_TOKENS = dict(
    WETH=Token(Zora, address="0x4200000000000000000000000000000000000006")
)
LINEA_TOKENS = dict(
    LXP=Token(Linea, address="0xd83af4fbD77f3AB65C3B1Dc4B38D7e67AEcf599A"),
    USDC=Token(Linea, address="0x176211869ca2b568f2a7d4ee941e073a821ee1ff"),
    USDT=Token(Linea, address="0xa219439258ca9da29e9cc4ce5596924745e12b93")
)
TOKENS = {
    "ETHEREUM": ETHEREUM_TOKENS,
    "BASE": BASE_TOKENS,
    "SCROLL": SCROLL_TOKENS,
    "BSC": BSC_TOKENS,
    "ARBITRUM": ARBITRUM_TOKENS,
    "POLYGON": POLYGON_TOKENS,
    "OPTIMISM": OPTIMISM_TOKENS,
    "ZORA": ZORA_TOKENS,
    "LINEA": LINEA_TOKENS,
}

if __name__ == "__main__":
    a = Token(chain=Optimism, address="0x4200000000000000000000000000000000000006")
    asyncio.run(a.get_token_info())
    print(a)
