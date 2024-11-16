from abc import ABC
from decimal import Decimal
from pathlib import Path

from web3mt.dex.models import DEX
from web3mt.onchain.evm.client import TransactionParameters
from web3mt.onchain.evm.models import TokenAmount, Token
from web3mt.utils import my_logger, FileManager


class BridgeInfo:
    def __init__(
            self,
            name: str, user: str, recipient: str, log_info: str,
            token_amount_in: TokenAmount, token_out: Token,
            exact_output: bool = False
    ):
        self.name = name
        self.user = user
        self.recipient = recipient
        self.log_info = log_info
        self.token_amount_in = token_amount_in
        self.token_out = token_out
        self.exact_output = exact_output
        self.token_amount_out: TokenAmount | None = None
        self.bridge_fee: TokenAmount | None = None
        self._tx_params: TransactionParameters | None = None

    def __str__(self):
        return (
            f'{self.log_info} | Bridge {self.token_amount_in} from {self.token_amount_in.token.chain} to '
            f'{self.token_amount_out.token.chain} with {self.name}. -{self.token_amount_in}, '
            f'+{self.token_amount_out}. Bridge fee: {self.bridge_fee}. {self.tx_params}'
        )

    @property
    def tx_params(self):
        return self._tx_params

    @tx_params.setter
    def tx_params(self, value: TransactionParameters):
        self._tx_params = value
        self.bridge_fee += TokenAmount(
            self._tx_params.gas_price * self._tx_params.gas_limit, True, self.token_amount_in.token.chain.native_token
        )


class Bridge(DEX, ABC):
    NAME = 'Bridge'
    ABI = FileManager.read_json(Path(__file__).parent / 'abi.json')

    async def bridge(self, bridge_info: BridgeInfo, use_full_balance: bool = False) -> BridgeInfo | None:
        pass

    async def refuel(self, bridge_info: BridgeInfo, use_full_balance: bool = False) -> BridgeInfo | None:
        pass

    def validate_bridge_info(self, bridge_info: BridgeInfo) -> BridgeInfo | None:
        if bridge_info.bridge_fee.amount_in_usd > self.MAX_FEE_IN_USD:
            my_logger.warning(
                f'{self.client.log_info} | Can\'t bridge with {bridge_info.name}. '
                f'Bridge fee: {bridge_info.bridge_fee}'
            )
            return
        return bridge_info
