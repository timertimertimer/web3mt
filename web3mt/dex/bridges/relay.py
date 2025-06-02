from curl_cffi.requests import RequestsError

from web3mt.dex.bridges.base import Bridge, BridgeInfo
from web3mt.onchain.evm.models import Token, TokenAmount
from web3mt.utils import my_logger


class Relay(Bridge):
    NAME = 'Relay'
    API_URL = 'https://api.relay.link/'

    async def bridge(self, bridge_info: BridgeInfo, use_full_balance: bool = False) -> BridgeInfo | None:
        origin_currency: str = (
            bridge_info.token_amount_in.token.burner_address
            if (
                    bridge_info.token_amount_in.token.address ==
                    bridge_info.token_amount_in.token.chain.native_token.address
            )
            else bridge_info.token_amount_in.token.address
        )
        destination_currency: str = (
            bridge_info.token_out.burner_address
            if bridge_info.token_out.address == bridge_info.token_out.chain.native_token.address
            else bridge_info.token_out.address
        )
        payload = dict(
            user=bridge_info.user, recipient=bridge_info.recipient,
            originCurrency=origin_currency, destinationCurrency=destination_currency,
            amount=bridge_info.token_amount_in.wei,
            originChainId=bridge_info.token_amount_in.token.chain.chain_id,
            destinationChainId=bridge_info.token_out.chain.chain_id,
            tradeType='EXACT_OUTPUT' if bridge_info.exact_output else 'EXACT_INPUT'
        )
        try:
            response, data = await self.session.post(self.API_URL + 'execute/swap', json=payload)
        except RequestsError:
            my_logger.warning(f'{self.client.log_info} | Skipping Relay bridge')
            return
        fees = data['fees']['relayer']
        bridge_info.bridge_fee = TokenAmount(
            amount=fees['amount'], is_wei=True, token=Token(chain=fees["currency"]["chainId"], **fees["currency"])
        )
        bridge_info.token_amount_out = TokenAmount(
            amount=data["details"]["currencyOut"]["amount"], is_wei=True,
            token=Token(
                chain=data["details"]["currencyOut"]["currency"]["chainId"],
                **data["details"]["currencyOut"]["currency"]
            )
        )
        tx_data = data['steps'][0]['items'][0]['data']
        bridge_info.tx_params = await self.client.create_tx_params(
            to=tx_data['to'], value=bridge_info.token_amount_in,
            data=tx_data['data'], use_full_balance=use_full_balance
        )
        return self.validate_bridge_info(bridge_info)
