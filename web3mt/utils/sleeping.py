import asyncio
import random

from .logger import logger


async def sleep(a: float, b: float = None, profile_id: int = None, echo: bool = True) -> None:
    delay = random.uniform(a, b) if b else a

    if echo:
        logger.info(f"{f'{profile_id} | ' if profile_id else ''}💤 Sleeping for {delay} s.")
    await asyncio.sleep(delay)
