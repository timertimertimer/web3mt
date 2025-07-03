import asyncio

from web3mt.config import btc_env
from web3mt.onchain.btc.client import Client, LitecoinSpace

from bitcoinlib.wallets import Wallet, wallet_delete_if_exists
from bitcoinlib.keys import HDKey
from bitcoinlib.transactions import Transaction, Output

from web3mt.onchain.btc.models import BTCLikeAmount, Token

network = "litecoin"


async def sign_tx(to_address: str, amount: BTCLikeAmount):
    hk = HDKey.from_passphrase(btc_env.litecoin_mnemonic, network=network).subkey_for_path("m/84'/2'/0'/0/0")
    utxos = await LitecoinSpace().get_utxo(hk.address())
    amount = BTCLikeAmount(0.009, token=Token(chain=network))
    fee = BTCLikeAmount(0.001, token=Token(chain=network))
    total = 0
    selected = []
    for u in utxos:
        selected.append(u)
        total += u["value"]
        if total >= amount + fee.sat:
            break
    if total < amount.sat + fee.sat:
        raise Exception("Not enough balance")
    change = total - amount.sat - fee.sat
    tx = Transaction(network=network)
    for u in selected:
        tx.add_input(
            prev_txid=u["txid"],
            output_n=u["vout"],
            value=u["value"],
            keys=[hk],
            witness_type='segwit'
        )
    tx.outputs.append(Output(amount.sat, to_address, network=network))
    if change > 0:
        tx.outputs.append(Output(change, hk.address(), network=network))
    tx.sign()
    return tx.as_hex()


def some():
    wallet_delete_if_exists("temp_wallet", force=True)
    wallet = Wallet.create(
        "temp_wallet",
        keys=btc_env.litecoin_mnemonic,
        network=network,
        witness_type="segwit",
    )
    for i in range(5):
        key = wallet.get_key(change=1, account_id=i)
        print(f"Change address #{i}: {key.address}")


async def main():
    async with Client.from_config(url=btc_env.litecoin_rpc, auth=None) as client:
        data = await sign_tx('ltc1q7qelkfpcua7ppkj58tgdk2ptlsdnkaqwjeq6pn')
        data = await client.send_raw_transaction(data)
        return data


if __name__ == "__main__":
    # some()
    asyncio.run(main())