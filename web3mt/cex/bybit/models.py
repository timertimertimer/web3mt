from web3mt.cex.base import Account


__all__ = ["Spot", "Funding"]


class Spot(Account):
    NAME = "Trading"
    ACCOUNT_ID = "UNIFIED"


class Funding(Account):
    NAME = "Funding"
    ACCOUNT_ID = "FUND"
