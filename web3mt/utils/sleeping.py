import asyncio
import random
from datetime import timedelta

from web3mt.utils import my_logger
from web3mt.config import DEV


async def sleep(
        a: float = None, b: float = None, time_delta: timedelta = None, log_info: str = 'Main', echo: bool = DEV
) -> None:
    if a is not None:
        delay = random.uniform(a, b) if b else a
        time_delta = timedelta(seconds=delay)

    if echo and time_delta:
        days = time_delta.days
        hours, remainder = divmod(time_delta.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)
        days_str = f"{days} days" if days else ''
        hours_str = f"{hours} hours" if hours else ''
        minutes_str = f"{minutes} minutes" if minutes else ''
        seconds_str = f"{seconds} seconds" if seconds else ''
        my_logger.info(
            f"{log_info} | 💤 Sleeping for "
            f"{', '.join([el for el in [days_str, hours_str, minutes_str, seconds_str] if el])}"
        )
    await asyncio.sleep(time_delta.seconds)


if __name__ == '__main__':
    asyncio.run(sleep(24 * 60 * 60 + 5 * 60, echo=True))
