import asyncio
import csv
import sys
from datetime import datetime, UTC, timedelta

from eth_utils import to_checksum_address
from web3.contract import AsyncContract

from examples.dex.evm.config import abis
from examples.utils.other import data_path
from eth_account import Account

Account.enable_unaudited_hdwallet_features()
from web3mt.dex.models import DEX

import secrets
import string

from web3mt.onchain.evm.client import BaseClient
from web3mt.onchain.evm.models import TokenAmount, Token, BSC
from web3mt.utils import curl_cffiAsyncSession
from web3mt.utils.logger import logger


def generate_nonce(length=16):
    chars = string.ascii_letters + string.digits
    return "".join(secrets.choice(chars) for _ in range(length))


accounts = []
with open(data_path / "accounts.csv", encoding="utf-8", newline="") as f:
    reader = csv.reader(f, delimiter=";")
    for row in reader:
        accounts.append(row)


class SaharaClaimer(DEX):
    async def sign_in(self):
        domain = "knowledgedrop.saharaai.com"
        address = self.evm_client.account.address
        nonce = generate_nonce()
        statement = """Sign in with Ethereum to the app.

URI: https://knowledgedrop.saharaai.com"""
        version = 1
        chain_id = 56
        issued_at = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
        expiration_time = (datetime.now(UTC) + timedelta(days=7)).strftime(
            "%Y-%m-%dT%H:%M:%S.%f"
        )[:-3] + "Z"
        message = f"""{domain} wants you to sign in with your Ethereum account:
{address}

{statement}
Version: {version}
Chain ID: {chain_id}
Nonce: {nonce}
Issued At: {issued_at}
Expiration Time: {expiration_time}"""
        signature = self.evm_client.sign(message)
        resp, data = await self.http_session.post(
            f"https://earndrop.prd.galaxy.eco/sign_in",
            json={
                "address": address,
                "message": message,
                "signature": "0x" + signature,
                "public_key": "",
            },
        )
        token = data.get("token")
        self.http_session.headers.update({"Authorization": token})

    async def info(self):
        resp, data = await self.http_session.get(
            "https://earndrop.prd.galaxy.eco/sahara/info"
        )
        data = data.get("data")
        total_amount = int(data.get("total_amount", 0))
        eligible_amount = int(data.get("eligible_amount", 0))
        balance = await self.evm_client.balance_of()
        logger.info(
            f"{self.evm_client.account.address} | "
            f"Balance: {balance}, total: {TokenAmount(token=sahara_token, amount=total_amount, is_wei=True)}, "
            f"eligible: {TokenAmount(token=sahara_token, amount=eligible_amount, is_wei=True)}"
        )
        return total_amount, eligible_amount

    async def claim(self):
        total_amount, eligible_amount = await self.info()
        if not eligible_amount:
            return None
        resp, data = await self.http_session.post(
            "https://earndrop.prd.galaxy.eco/sahara/prepare_claim"
        )
        data = data.get("data")
        signature = data.get("signature")
        params = data.get("params")
        earndrop_id = data.get("earndrop_id")
        if len(params) > 1:
            raise ValueError("params len > 1")
        amount = params[0].get("amount")
        token_amount = TokenAmount(amount, is_wei=True, token=sahara_token)
        contract_address = data.get("contract_address")
        merkle_proof = params[0].get("merkle_proof")
        stage_index = params[0].get("stage_index")
        leaf_index = params[0].get("leaf_index")
        contract: AsyncContract = self.evm_client.w3.eth.contract(
            to_checksum_address(contract_address), abi=abis["sahara_claim"]
        )
        ok, tx_hash_or_err = await self.evm_client.tx(
            to=contract.address,
            name=f"Claim {token_amount}",
            data=contract.encode_abi(
                "claimEarndrop",
                args=[
                    earndrop_id,
                    [
                        stage_index,
                        leaf_index,
                        self.evm_client.account.address,
                        token_amount.wei,
                        merkle_proof,
                    ],
                    signature
                ],
            ),
            value=TokenAmount(data['claim_fee'], is_wei=True, token=self.evm_client.chain.native_token),
        )
        if ok:
            logger.success(f"Claimed {token_amount}")
        return None


def get_eth_account(seed: str):
    if " " in seed:
        account = Account.from_mnemonic(seed)
    else:
        account = Account.from_key(seed)
    return account


async def check(seed: str, proxy: str):
    account = get_eth_account(seed)
    sahara_claimer = SaharaClaimer(
        client=BaseClient(account=account, chain=BSC),
        session=curl_cffiAsyncSession(proxy=proxy if proxy else None),
    )
    await sahara_claimer.sign_in()
    info = await sahara_claimer.info()
    await sahara_claimer.close()
    return info


async def claim(seed: str, proxy: str):
    account = get_eth_account(seed)
    sahara_claimer = SaharaClaimer(
        client=BaseClient(account=account, chain=BSC),
        session=curl_cffiAsyncSession(proxy=proxy if proxy else None),
    )
    await sahara_claimer.sign_in()
    await sahara_claimer.claim()
    await sahara_claimer.close()


async def main(choice: int):
    await sahara_token.get_token_info()
    await sahara_token.update_price()
    logger.success(f"1 {sahara_token.symbol} = {sahara_token.price}$")
    if choice == 1:
        res = await asyncio.gather(*[check(seed, proxy) for seed, proxy in accounts])
        logger.info(
            f"Total: {TokenAmount(token=sahara_token, amount=sum([el[0] for el in res]), is_wei=True)}"
        )
        logger.info(
            f"Claimable: {TokenAmount(token=sahara_token, amount=sum([el[1] for el in res]), is_wei=True)}"
        )
    else:
        await asyncio.gather(*[claim(seed, proxy) for seed, proxy in accounts])


if __name__ == "__main__":
    choice = int(input(f'1. Checker\n2. Claimer\n3. Exit\n'))
    if choice == 3:
        sys.exit(0)
    sahara_token = Token(chain=BSC, address="0xFDFfB411C4A70AA7C95D5C981a6Fb4Da867e1111")
    asyncio.run(main(choice))