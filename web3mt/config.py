from pathlib import Path
from typing import Optional

from pydantic_settings import SettingsConfigDict, BaseSettings

env_path = Path.cwd().parent.parent.parent / ".env"


class ENV(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=env_path, env_file_encoding="utf-8", extra="ignore"
    )

    passphrase: Optional[str] = None
    default_proxy: Optional[str] = None
    rotating_proxy: Optional[str] = None
    some_password: Optional[str] = None
    default_evm_address: Optional[str] = None

    webshare_api_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    capmonster_api_key: Optional[str] = None
    two_captcha_api_key: Optional[str] = None
    coingecko_api_key: Optional[str] = None
    alchemy_api_key: Optional[str] = None
    thirdweb_api_key: Optional[str] = None
    capsolver_api_key: Optional[str] = None
    helius_api_key: Optional[str] = None

    connection_string: Optional[str] = None

    okx_api_key: Optional[str] = None
    okx_api_secret: Optional[str] = None
    okx_api_passphrase: Optional[str] = None

    retry_count: int = 5

    monero_node_rpc_host: Optional[str] = None
    monero_wallet_rpc_login: Optional[str] = None
    monero_wallet_rpc_password: Optional[str] = None


class TronENV(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=env_path, env_file_encoding="utf-8", extra="ignore"
    )

    tron_ledger_private_key: Optional[str] = None
    tron_ledger_mnemonic: Optional[str] = None
    tron_private_key: Optional[str] = None
    tron_mnemonic: Optional[str] = None
    trongrid_api_key: Optional[str] = None
    tron_witness_private_key: Optional[str] = None
    nile_rpc: str = "https://nile.trongrid.io"
    tron_public_rpc: str = "https://tron-rpc.publicnode.com"
    symbol: str = "TRX"
    default_decimals: int = 6


class BTClikeENV(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=env_path, env_file_encoding="utf-8", extra="ignore"
    )

    bitcoin_public_rpc: str = "https://bitcoin-rpc.publicnode.com"
    litecoin_rpc: Optional[str] = None
    bitcoin_mnemonic: Optional[str] = None
    litecoin_mnemonic: Optional[str] = None


class CEXENV(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=env_path, env_file_encoding="utf-8", extra="ignore"
    )

    binance_api_key: Optional[str] = None
    binance_api_secret: Optional[str] = None

    htx_api_key: Optional[str] = None
    htx_api_secret: Optional[str] = None

    kucoin_api_passphrase: Optional[str] = None
    kucoin_api_key: Optional[str] = None
    kucoin_api_secret: Optional[str] = None

    mexc_api_key: Optional[str] = None
    mexc_api_secret: Optional[str] = None


env = ENV()
tron_env = TronENV()
btc_env = BTClikeENV()
cex_env = CEXENV()
DEV = True
