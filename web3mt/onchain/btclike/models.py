from web3mt.config import btc_env
from web3mt.models import Chain, Token

default_decimals = 8

Bitcoin = Chain(
    name="Bitcoin",
    rpc=btc_env.bitcoin_public_rpc,
    explorer="https://mempool.space/",
)
BTC = Token(
    symbol="BTC",
    decimals=default_decimals,
    chain=Bitcoin,
)
Bitcoin.native_token = Bitcoin

Litecoin = Chain(
    name="Litecoin",
    rpc=btc_env.litecoin_rpc,
    explorer="https://litecoinspace.org/",
)
LTC = Token(
    symbol="LTC",
    decimals=default_decimals,
    chain=Litecoin,
)
Litecoin.native_token = LTC
