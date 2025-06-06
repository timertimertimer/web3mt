import asyncio
import base64
import hmac
import json
import websockets
from hashlib import sha256
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from datetime import datetime, timezone
from web3mt.cex.base import CEX, Asset
from web3mt.cex.models import WithdrawInfo, User
from web3mt.cex.okx.models import *
from web3mt.consts import DEV, env
from web3mt.models import Coin
from web3mt.onchain.aptos.models import TokenAmount
from web3mt.utils import my_logger

__all__ = [
    'OKX'
]


class OKX(CEX):
    API_VERSION = 5
    URL = f'https://www.okx.com/api/v{API_VERSION}'
    NAME = 'OKX'

    @staticmethod
    def _define_transfer_type(from_account: Account, to_account: Account) -> int:
        if not from_account.user.user_id:  # from master
            if not to_account.user.user_id:  # to master
                return 0
            else:  # to sub
                return 1
        else:  # from sub
            if not to_account.user.user_id:  # to master
                return 2
            else:  # to sub
                return 4

    @staticmethod
    def _define_path_for_log(
            from_account: Account,
            to_account: Account,
            type_: int
    ):
        match type_:
            case 0:
                return f'from {from_account.NAME} to {to_account.NAME}'
            case 1:
                return f'from master ({from_account.NAME}) to sub {to_account.user.user_id} ({to_account.NAME})'
            case 2:
                return f'from sub {from_account.user.user_id} ({from_account.NAME}) to master ({to_account.NAME})'
            case 4:
                return (
                    f'from sub {from_account.user.user_id} ({from_account.NAME}) '
                    f'to sub {to_account.user.user_id} ({to_account.NAME})'
                )
            case _:
                return ''

    def get_headers(self, path: str, method: str = 'GET', **kwargs):
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        params = kwargs.get('params')
        params = '?' + '&'.join([f'{key}={value}' for key, value in params.items()]) if params else ''
        prehash_string = (
                timestamp + method.upper() + f'/api/v{OKX.API_VERSION}/' + path + params + str(kwargs.get('data', ''))
        )
        secret_key_bytes = (
            self.profile.okx.api_secret if self.profile and self.profile.okx.api_secret
            else env.OKX_API_SECRET
        ).encode('utf-8')
        signature = hmac.new(secret_key_bytes, prehash_string.encode('utf-8'), sha256).digest()
        encoded_signature = base64.b64encode(signature).decode('utf-8')
        return {
            "Content-Type": "application/json",
            'OK-ACCESS-KEY': (
                self.profile.okx.api_key if self.profile and self.profile.okx.api_key else env.OKX_API_KEY
            ),
            'OK-ACCESS-SIGN': encoded_signature,
            'OK-ACCESS-TIMESTAMP': timestamp,
            'OK-ACCESS-PASSPHRASE': (
                self.profile.okx.api_passphrase if self.profile and self.profile.okx.api_passphrase
                else env.OKX_API_PASSPHRASE
            )
        }

    async def get_coin_price(self, coin: str | Coin = 'ETH') -> Decimal:
        if coin.price:
            return coin.price
        coin = Coin(coin) if isinstance(coin, str) else coin
        _, data = await self.get('market/ticker', params={'instId': f'{coin.symbol}-USDT'}, without_headers=True)
        if data['data']:
            coin.price = data['data'][0]['askPx']
            return coin.price
        else:
            my_logger.warning(f'{self.log_info} | {data["msg"]}. {coin.symbol}-USDT')
            return Decimal("0")

    async def get_funding_balance(self, user: User = None, coins: list[Asset | Coin | str] = None) -> list[Asset]:
        """
        Doesn't return current price for assets
        Args: currencies_with_comma example: 'BTC,ETH,TIA'. No more than 20
        """
        user = user or self.main_user
        _, data = await self.get(
            f'asset{"/subaccount" if user.user_id else ""}/balances',
            params={'ccy': ','.join([coin.symbol for coin in coins])}
            if coins else {'subAcct': user.user_id}
            if user.user_id else {}
        )
        user.funding_account.assets = [
            Asset(
                Coin(currency['ccy']), available_balance=currency['availBal'], total=currency['bal'],
                frozen_balance=currency['frozenBal']
            )
            for currency in data['data']
        ]
        if DEV:
            my_logger.info(user.funding_account)
        return user.funding_account.assets

    async def get_trading_balance(self, user: User = None, coins: list[Asset | Coin | str] = None) -> list[Asset]:
        user = user or self.main_user
        _, data = await self.get(
            f'account{"/subaccount" if user.user_id else ""}/balance' + ('s' if user.user_id else ""),
            params={'ccy': ','.join([coin.symbol for coin in coins])}
            if coins else {'subAcct': user.user_id}
            if user.user_id else {}
        )
        data = data['data'][0]
        user.trading_account.assets = [
            Asset(
                Coin(
                    currency['ccy'],
                    price=Decimal(currency['eqUsd']) / Decimal(max(currency['cashBal'], currency['eq']))
                ),
                available_balance=currency['availBal'], frozen_balance=currency['frozenBal'],
                total=max(currency['cashBal'], currency['eq'])
            )
            for currency in data['details']
        ]
        if DEV:
            my_logger.info(user.trading_account)
        return user.trading_account.assets

    async def get_earn_balance(self, coins: list[Asset | Coin | str] = None) -> list[Asset]:
        user = self.main_user
        _, data = await self.get(
            f'finance/savings/balance',
            params={'ccy': ','.join([coin.symbol for coin in coins])} if coins else {}
        )
        data = data['data']
        for currency in data:
            balance = Decimal(currency['loanAmt']) + Decimal(currency['earnings']) + Decimal(currency['pendingAmt'])
            user.funding_account.assets.append(Asset(
                Coin(currency['ccy']), available_balance=0, frozen_balance=balance, total=balance
            ))
        if DEV:
            my_logger.info(user.trading_account)
        return user.funding_account.assets

    async def get_sub_account_list(self) -> list[User]:
        _, data = await self.get('users/subaccount/list')
        return [User(self, sub_account['subAcct']) for sub_account in data['data']]

    async def transfer(
            self,
            from_account: Account,
            to_account: Account,
            asset: Asset
    ):
        """
        0: transfer within account
        1: master account to sub-account (Only applicable to API Key from master account)
        2: sub-account to master account (Only applicable to API Key from master account)
        3: sub-account to master account (Only applicable to APIKey from sub-account)
        4: USE `transfer_between_sub_accounts`
        """
        between_sub_accounts = "/subaccount" if from_account.user.user_id and to_account.user.user_id else ''
        sub_account_name = from_account.user.user_id or to_account.user.user_id
        type_ = self._define_transfer_type(from_account, to_account)
        data = dict(
            ccy=asset.coin.symbol,
            amt=asset.format_available_balance(),
            to=to_account.ACCOUNT_ID,
            type=str(type_)
        ) | {'from': from_account.ACCOUNT_ID} | (dict(
            fromSubAccount=from_account.user.user_id,
            toSubAccount=to_account.user.user_id
        ) if between_sub_accounts else dict(subAcct=sub_account_name) if sub_account_name else {})
        _, data = await self.post(f'asset{between_sub_accounts}/transfer', data=str(data))
        log = f'{asset} {self._define_path_for_log(from_account, to_account, type_)}'
        if not data['msg']:
            my_logger.debug(f'{self.log_info} | Transferred {log}')
        else:
            my_logger.warning(f'{self.log_info} | Couldn\'t transfer {log}. {data}')

    async def withdraw(
            self,
            address: str,
            token_amount: TokenAmount,
            max_fee_in_usd: int | float | str | Decimal = Decimal('1.5'),
            internal: bool = False
    ) -> Decimal | None:
        coin: Coin = token_amount.token
        chain: str = token_amount.token.chain.name
        amount: Decimal = token_amount.ether
        if not self.main_user.funding_account.assets:
            await self.collect_on_funding_master()
        if not self.main_user.funding_account.assets:
            await self.get_funding_balance()
        asset_to_withdraw: Asset = self.main_user.funding_account[coin] or Asset(coin, 0, 0, 0)
        if asset_to_withdraw < token_amount:
            my_logger.warning(f'{self.log_info} | Not enough balance on OKX. {token_amount} > {asset_to_withdraw}')
            return
        wis: list[WithdrawInfo] = await self.get_withdrawal_info(asset_to_withdraw.coin, internal)
        if chain == 'Ethereum':
            chain = 'ERC20'
        elif chain == 'zkSync':
            chain = 'zkSync Era'
        for wi in wis:
            if wi.internal == internal and wi.chain == chain:
                if not wi.minimum_withdrawal <= amount <= wi.maximum_withdrawal:
                    my_logger.warning(
                        f'{self.log_info} | {chain} | Withdraw of {token_amount} does not meet the range of minimum - '
                        f'{wi.minimum_withdrawal} and maximum - {wi.maximum_withdrawal} withdrawals'
                    )
                    return
                fee_in_usd = wi.fee * wi.coin.price
                if fee_in_usd > max_fee_in_usd:
                    my_logger.warning(
                        f'{self.log_info} | {chain} | Withdraw of {token_amount} takes too much fee - {fee_in_usd:.2f}$'
                    )
                    return
                my_logger.info(f'{self.log_info} | Trying to withdraw {token_amount} to {address}. {wi}')
                data = dict(
                    ccy=coin.symbol, amt=str(amount), dest=3 if internal else 4, toAddr=address, fee=str(wi.fee),
                    chain=f'{coin.symbol}-{chain}'
                )
                _, data = await self.post('asset/withdrawal', data=str(data))
                if not data['msg']:
                    my_logger.debug(f'{self.log_info} | Withdrawal ID - {data["data"][0]["wdId"]}')
                else:
                    my_logger.warning(f'{self.log_info} | {address} ({chain}) | {data}')
                    return
                return fee_in_usd
        my_logger.warning(
            f'{self.log_info} | Can\'t withdraw {token_amount}' +
            (f' to {token_amount.token.chain}' if not internal else '')
        )
        return

    async def get_withdrawal_info(self, coin: str | Coin = 'ETH', internal: bool = False):
        # Ask for chain selection
        # Choose random chain from `destination_chains` list
        # Selected chain should be withdrawable
        coin = Coin(coin) if isinstance(coin, str) else coin
        if not coin.price:
            await self.get_coin_price(coin)
        _, data = await self.get('asset/currencies', params={'ccy': coin.symbol})
        return [
            WithdrawInfo(
                coin=coin,
                chain=chain['chain'].removeprefix(f'{coin.symbol}-'),
                internal=internal,
                fee=chain['minFee'],
                minimum_withdrawal=chain['minWd'],
                maximum_withdrawal=chain['maxWd'],
                need_tag=chain['needTag']
            )
            for chain in data['data']
            if chain['canWd'] or (internal and chain['canInternal'])
        ]

    class Websocket:
        URL = 'wss://ws.okx.com:8443/ws/v5/business'

        def __init__(self):
            self.ws = None
            self.okx_api = OKX()

        async def __aenter__(self):
            self.ws = websockets.connect(self.URL)
            return self

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            if exc_type:
                if isinstance(exc_val, asyncio.CancelledError):
                    my_logger.debug(f'Connection was cancelled | {datetime.now().isoformat()}')
                else:
                    my_logger.error(f"Exception in context: {exc_type}, {exc_val}")
            if self.ws:
                await self.ws.__aexit__(exc_type, exc_val, exc_tb)

        @staticmethod
        def sign() -> dict:
            ts = str(int(datetime.now().timestamp()))
            args = dict(apiKey=OKXAPICreds.KEY, passphrase=OKXAPICreds.PASSPHRASE, timestamp=ts)
            sign = ts + 'GET' + '/users/self/verify'
            mac = hmac.new(
                bytes(OKXAPICreds.SECRET, encoding='utf8'),
                bytes(sign, encoding='utf-8'),
                digestmod='sha256'
            )
            args['sign'] = base64.b64encode(mac.digest()).decode(encoding='utf-8')
            return args

        @staticmethod
        async def send(ws, op: str, args: list):
            subs = dict(op=op, args=args)
            await ws.send(json.dumps(subs))

        async def start(self):
            async for ws in self.ws:
                try:
                    my_logger.debug(f'Connected to {self.URL} {datetime.now().isoformat()}')
                    await self.send(ws, 'login', [self.sign()])
                    async for msg_string in ws:
                        await self.handle_message(ws, msg_string)
                    my_logger.debug("Connection finished" + datetime.now().isoformat())
                except (websockets.ConnectionClosed, websockets.ConnectionClosedError):
                    await asyncio.sleep(5)
                    continue

        async def handle_message(self, ws, msg_string: str):
            try:
                m = json.loads(msg_string)
                event = m.get('event')
                data = m.get('data')
                if event == 'error':
                    my_logger.warning("Error ", msg_string)
                elif event in ['subscribe', 'unsubscribe']:
                    my_logger.debug("subscribe/unsubscribe ", msg_string)
                elif event == 'login':
                    my_logger.debug('Logged in')
                    await self.send(ws, 'subscribe', [dict(channel='deposit-info')])
                elif data:
                    data = data[0]
                    state = int(data.get('state'))
                    amount = data.get('amount')
                    asset = data.get('ccy')
                    sub_name = data.get('subAcct')
                    match state:
                        case 0 | 1:
                            my_logger.info(data)
                            if sub_name:
                                await self.transfer_from_sub(sub_name, asset, amount)
                        case 2:
                            my_logger.success(f'{amount} {asset} deposit to {f"{sub_name} sub" or "master"} completed')
                        case _:
                            my_logger.warning(data)
            except Exception as e:
                my_logger.warning(e)

        async def transfer_from_sub(self, sub_name: str, asset: str, amount: str) -> None:
            loop = asyncio.get_event_loop()
            with ThreadPoolExecutor() as pool:
                await loop.run_in_executor(
                    pool,
                    self.okx_api.transfer,
                    (
                        self.okx_api.Funding(SubAccountAPI(**OKX.KWARGS), sub_name),
                        self.okx_api.funding,
                        asset,
                        amount
                    )
                )


# Получение уведомления о поступлении
# Если средства поступили на субаккаунт, перевести на мейн funding
# Вывод с funding на кошелек
# FIXME
async def start_websocket():
    async with OKX.Websocket() as ws:
        await ws.start()


async def start():
    okx = OKX()
    print(await okx.get_earn_balance())


if __name__ == '__main__':
    asyncio.run(start())
