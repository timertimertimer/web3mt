from web3mt.cex.base import Account


class Spot(Account):
    NAME = 'Trading'
    ACCOUNT_ID = 'SPOT'


class Funding(Account):
    NAME = 'Funding'
    ACCOUNT_ID = 'FUND'
