import asyncio
import random

from web3mt.utils import my_logger
from ..consts import DEV


async def sleep(a: float, b: float = None, log_info: str = 'Main', echo: bool = DEV) -> None:
    delay = random.uniform(a, b) if b else a
    if echo and delay:
        my_logger.info(f"{log_info} | 💤 Sleeping for {delay} s.")
    await asyncio.sleep(delay)
