from web3mt.cex.base import Account
from web3mt.onchain.monero.models import Monero


__all__ = ["Spot", "chains"]


class Spot(Account):
    NAME = "Spot"
    ACCOUNT_ID = "spot"


chains = {Monero: "xmr2"}
