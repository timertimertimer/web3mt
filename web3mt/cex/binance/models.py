from web3mt.cex.base import Account


__all__ = ["Spot", "Funding"]


class Spot(Account):
    NAME = "Spot"
    ACCOUNT_ID = "SPOT"


class Funding(Account):
    NAME = "Funding"
    ACCOUNT_ID = "FUNDING"
