from web3mt.cex.base import Account


class Spot(Account):
    NAME = 'Trading'
    ACCOUNT_ID = 'UNIFIED'


class Funding(Account):
    NAME = 'Funding'
    ACCOUNT_ID = 'FUND'
