from pathlib import Path
from typing import Optional

from pydantic_settings import SettingsConfigDict, BaseSettings

env_path = Path.cwd().parent.parent.parent / ".env"


class ENV(BaseSettings):
    model_config = SettingsConfigDict(env_file=env_path, env_file_encoding='utf-8', extra='ignore')

    PASSPHRASE: Optional[str] = None
    DEFAULT_PROXY: Optional[str] = None
    ROTATING_PROXY: Optional[str] = None
    SOME_PASSWORD: Optional[str] = None
    DEFAULT_EVM_ADDRESS: Optional[str] = None

    WEBSHARE_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    CAPMONSTER_API_KEY: Optional[str] = None
    TWO_CAPTCHA_API_KEY: Optional[str] = None
    COINGECKO_API_KEY: Optional[str] = None
    ALCHEMY_API_KEY: Optional[str] = None
    THIRDWEB_API_KEY: Optional[str] = None
    CAPSOLVER_API_KEY: Optional[str] = None
    HELIUS_API_KEY: Optional[str] = None

    CONNECTION_STRING: Optional[str] = None

    OKX_API_KEY: Optional[str] = None
    OKX_API_SECRET: Optional[str] = None
    OKX_API_PASSPHRASE: Optional[str] = None


class TronENV(BaseSettings):
    model_config = SettingsConfigDict(env_file=env_path, env_file_encoding='utf-8', extra='ignore')

    TRON_LEDGER_PRIVATE_KEY: Optional[str] = None
    TRON_LEDGER_MNEMONIC: Optional[str] = None
    TRON_PRIVATE_KEY: Optional[str] = None
    TRON_MNEMONIC: Optional[str] = None
    TRONGRID_API_KEY: Optional[str] = None
    TRON_WITNESS_PRIVATE_KEY: Optional[str] = None
    nile_rpc: str = 'https://nile.trongrid.io'
    public_rpc: str = 'https://tron-rpc.publicnode.com'
    symbol: str = 'TRX'
    default_decimals: int = 6


env = ENV()
tron_env = TronENV()
DEV = False
