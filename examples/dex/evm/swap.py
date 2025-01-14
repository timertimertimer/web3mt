import asyncio

from web3db import Profile, DBHelper

from web3mt.consts import Web3mtENV
from web3mt.dex.uniswap.uniswap import Uniswap
from web3mt.onchain.evm.models import Arbitrum, Token, TokenAmount, ARB_WETH


async def uniswap(profile: Profile):
    u = Uniswap(profile=profile)
    u.client.chain = Arbitrum
    TIAN = Token(u.client.chain, address='0xD56734d7f9979dD94FAE3d67C7e928234e71cD4C')
    await ARB_WETH.get_token_info()
    token_out = u.client.chain.native_token
    token_in = TIAN
    # token_amount_in = TokenAmount(0.001, token=token_in)
    token_amount_in = await u.client.balance_of(token=token_in)
    await u.swap(token_amount_in, token_out)


async def main():
    db = DBHelper(Web3mtENV.LOCAL_CONNECTION_STRING)
    profile = await db.get_row_by_id(1, Profile)
    await uniswap(profile)


if __name__ == '__main__':
    asyncio.run(main())
