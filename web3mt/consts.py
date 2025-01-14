import os
from dotenv import load_dotenv

load_dotenv()


class Web3mtENV:
    PASSPHRASE = os.getenv("PASSPHRASE", "")
    DEFAULT_PROXY = os.getenv("DEFAULT_PROXY", "")
    SOME_PASSWORD = os.getenv("SOME_PASSWORD", "")
    DEFAULT_EVM_ADDRESS = os.getenv("DEFAULT_EVM_ADDRESS", "")

    WEBSHARE_API_KEY = os.getenv("WEBSHARE_API_KEY", "")
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    CAPMONSTER_API_KEY = os.getenv("CAPMONSTER_API_KEY", "")
    TWO_CAPTCHA_API_KEY = os.getenv("TWO_CAPTCHA_API_KEY", "")
    COINGECKO_API_KEY = os.getenv("COINGECKO_API_KEY", "")
    ALCHEMY_API_KEY = os.getenv("ALCHEMY_API_KEY", "")
    THIRDWEB_API_KEY = os.getenv("THIRDWEB_API_KEY", "")
    CAPSOLVER_API_KEY = os.getenv("CAPSOLVER_API_KEY", "")
    HELIUS_API_KEY = os.getenv("HELIUS_API_KEY", "")

    LOCAL_CONNECTION_STRING = os.getenv("LOCAL_CONNECTION_STRING", "")
    REMOTE_CONNECTION_STRING = os.getenv("REMOTE_CONNECTION_STRING", "")

    OKX_API_KEY = os.getenv("OKX_API_KEY", "")
    OKX_API_SECRET = os.getenv("OKX_API_SECRET", "")
    OKX_API_PASSPHRASE = os.getenv("OKX_API_PASSPHRASE", "")


DEV = False
