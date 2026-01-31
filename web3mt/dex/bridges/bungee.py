from eth_utils import to_checksum_address
from web3mt.dex.bridges.base import Bridge, BridgeInfo
from web3mt.onchain.evm.models import TokenAmount
from web3mt.utils import logger


class Bungee(Bridge):
    NAME = 'Bungee'
    REFUEL_API_URL = 'https://refuel.socket.tech'
    BRIDGE_API_URL = 'https://api.socket.tech/v2'

    async def refuel(self, bridge_info: BridgeInfo, use_full_balance: bool = False) -> BridgeInfo | None:
        _, data = await self.http_session.get(
            f'{self.REFUEL_API_URL}/quote', params=dict(
                fromChainId=bridge_info.token_amount_in.token.chain.chain_id,
                toChainId=bridge_info.token_out.chain.chain_id,
                fromTokenAddress=bridge_info.token_amount_in.token.address,
            )
        )
        if not data['success']:
            logger.warning(f'{self.evm_client.log_info} | Skipping Bungee refuel. {data["result"]}')
            return None
        data = data['result']
        bridge_info.bridge_fee = TokenAmount(data['destinationFee'], True, bridge_info.token_amount_in.token)
        bridge_info.token_amount_out = TokenAmount(
            data["estimatedOutput"], True, bridge_info.token_out
        )
        bridge_info.tx_params = await self.evm_client.create_tx_params(
            to=data['contractAddress'], value=bridge_info.token_amount_in,
            data=(
                self.evm_client.w3.eth.contract(
                    to_checksum_address(data['contractAddress']), abi=self.ABI['bungee_refuel']
                ).encodeABI(
                    'depositNativeToken',
                    args=[bridge_info.token_out.chain.chain_id, self.evm_client.account.address]
                )
            ),
            use_full_balance=use_full_balance
        )
        return self.validate_bridge_info(bridge_info)
