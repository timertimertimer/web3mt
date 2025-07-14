from web3mt.cex.base import Account

__all__ = ["Trading", "Funding"]


class Trading(Account):
    NAME = "Trading"
    ACCOUNT_ID = "18"


class Funding(Account):
    NAME = "Funding"
    ACCOUNT_ID = "6"
