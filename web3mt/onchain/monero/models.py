from web3mt.config import env
from web3mt.models import Chain, Token

Monero = Chain(
    name="Monero",
    rpc=env.monero_node_rpc_host,
    explorer="https://xmrchain.net/",
)
XMR = Token(
    symbol="XMR",
    decimals=12,
    chain=Monero,
)
Monero.native_token = XMR
