from bip_utils import (
    Bip39SeedGenerator,
    Bip44Coins,
    Bip44,
    Bip44Changes,
    Bip84,
    Bip84Coins,
)

def get_address_from_mnemonic(
    proposal_num_class: type[Bip44 | Bip84],
    chain: Bip44Coins | Bip84Coins,
    mnemonic: str,
    index: int = 0,
):
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
    bip_obj_mst = proposal_num_class.FromSeed(seed_bytes, chain)
    bip_obj_acc = bip_obj_mst.Purpose().Coin().Account(0)
    bip_obj_chain = bip_obj_acc.Change(Bip44Changes.CHAIN_EXT)
    bip_obj_addr = bip_obj_chain.AddressIndex(index)
    address = bip_obj_addr.PublicKey().ToAddress()
    return address


def get_private_key_from_mnemonic(
    proposal_num_class: type[Bip44 | Bip84],
    chain: Bip44Coins | Bip84Coins,
    mnemonic: str,
    index: int = 0,
):
    seed_bytes = Bip39SeedGenerator(mnemonic).Generate()
    bip_obj_mst = proposal_num_class.FromSeed(seed_bytes, chain)
    bip_obj_acc = bip_obj_mst.Purpose().Coin().Account(0)
    bip_obj_chain = bip_obj_acc.Change(Bip44Changes.CHAIN_EXT)
    bip_obj_addr = bip_obj_chain.AddressIndex(index)
    private_key = bip_obj_addr.PrivateKey().Raw().ToHex()
    return private_key


def get_address_from_mnemonic_bip44(mnemonic: str, chain: Bip44Coins):
    return get_address_from_mnemonic(Bip44, chain, mnemonic)


def get_address_from_mnemonic_bip84(mnemonic: str, chain: Bip44Coins):  # native segwit
    return get_address_from_mnemonic(Bip84, chain, mnemonic)