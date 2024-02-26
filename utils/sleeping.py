import asyncio
import random

from .logger import logger


async def sleep(a: float, b: float = None):
    delay = random.uniform(a, b) if b else a

    logger.info(f"💤 Sleeping for {delay} s.")
    await asyncio.sleep(delay)
