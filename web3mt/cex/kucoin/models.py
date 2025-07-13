from web3mt.cex.base import Account
from web3mt.onchain.monero.models import Monero


class Trading(Account):
    NAME = "Trading"
    ACCOUNT_ID = "trade"


class Funding(Account):
    NAME = "Funding"
    ACCOUNT_ID = "main"


chains = {Monero: "xmr"}
