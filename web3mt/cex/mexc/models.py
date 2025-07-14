from web3mt.cex.base import Account
from web3mt.onchain.monero.models import Monero


__all__ = ["Trading", "chains"]


class Trading(Account):
    NAME = "Spot"
    ACCOUNT_ID = "SPOT"


chains = {Monero: "XMR"}
