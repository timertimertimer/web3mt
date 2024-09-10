from eth_utils import to_checksum_address, to_bytes

from web3mt.dex.bridges.base import BridgeInfo, Bridge
from web3mt.onchain.evm.models import TokenAmount


class RouterNitro(Bridge):
    NAME = 'RouterNitro'
    API_URL = 'https://api-beta.pathfinder.routerprotocol.com/api/v2/'

    async def bridge(self, bridge_info: BridgeInfo, use_full_balance: bool = False) -> BridgeInfo | None:
        params = dict(
            fromTokenAddress=bridge_info.token_amount_in.token.address,
            toTokenAddress=bridge_info.token_out.address, amount=bridge_info.token_amount_in.wei,
            fromTokenChainId=bridge_info.token_amount_in.token.chain.chain_id,
            toTokenChainId=bridge_info.token_out.chain.chain_id,
            partnerId=1
        )
        response, data = await self.session.get(self.API_URL + 'quote', params=params)
        response, data = await self.session.post(
            self.API_URL + 'transaction',
            json={
                **data, 'senderAddress': bridge_info.user, 'receiverAddress': bridge_info.recipient,
                'refundAddress': bridge_info.user
            }
        )
        bridge_info.bridge_fee = TokenAmount(
            data['bridgeFee']['amount'], wei=True, token=bridge_info.token_amount_in.token
        )
        bridge_info.token_amount_out = TokenAmount(
            amount=int(data["destination"]["tokenAmount"]), wei=True, token=bridge_info.token_out
        )
        tx_data = data["txn"]
        bridge_info.tx_params = await self.client.create_tx_params(
            to=tx_data['to'], value=bridge_info.token_amount_in,
            data=self.get_data(
                to=tx_data['to'],
                source_value=bridge_info.token_amount_in.wei,
                source_token=bridge_info.token_amount_in.token.address,
                destination_value=bridge_info.token_amount_out.wei,
                destination_token=bridge_info.token_out.address,
                destination_chain_id_bytes=(
                    str(bridge_info.token_out.chain.chain_id)
                    .encode('ascii').ljust(32, b'\0').hex()
                )
            ), use_full_balance=use_full_balance
        )
        return self.validate_bridge_info(bridge_info)

    def get_data(
            self,
            to: str,
            source_value: int,
            source_token: str,
            destination_value: int,
            destination_token: str,
            destination_chain_id_bytes: str,
            partner_id: int = 1
    ):
        return self.client.w3.eth.contract(to_checksum_address(to), abi=self.ABI['router_asset_forwarder']).encodeABI(
            'iDeposit',
            args=[
                [
                    partner_id, source_value, destination_value, source_token, self.client.account.address,
                    to_bytes(hexstr=destination_chain_id_bytes)
                ],
                to_bytes(hexstr=destination_token), to_bytes(hexstr=self.client.account.address)
            ]
        )