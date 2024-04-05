import asyncio

import aiosqlite


def execute(func):
    async def wrapper(*args, **kwargs):
        async with aiosqlite.connect("linea_park.db") as db:
            cursor = await db.cursor()
            await cursor.execute(await func(*args, **kwargs))
            await db.commit()
            record = await cursor.fetchone()
            return record[0] if record else record

    return wrapper


tasks_names = {
    'alienswap', 'micro3', 'omnizone', 'battlemon', 'play_nouns', 'unfettered_awakening', 'readon', 'nidium', 'z2048',
    'sarubol', 'lucky_cat', 'ulti_pilot', 'dmail', 'gamic', 'asmatch', 'yooldo', 'galactic_exploration', 'pictographs',
    'bitavatar', 'sendingme', 'abyss_world', 'satoshi_universe', 'gamerboom', 'zace', 'frog_war', 'acg_worlds',
    'micro3', 'bilinear', 'imaginairynfts'
}


@execute
async def create_table():
    s = (f"""CREATE TABLE IF NOT EXISTS linea_park (
                profile_id INT,
                address TEXT NOT NULL,
        """)
    for label in tasks_names:
        s += f'{label} INT DEFAULT 0,\n'
    for label in tasks_names:
        s += f'CONSTRAINT bool_{label} CHECK ({label} = 0 OR {label} = 1),\n'
    return s + """UNIQUE (address)
            )"""


'''
alter table linea_park
    add acg_worlds integer default 0 CONSTRAINT bool_acg_worlds CHECK (acg_worlds = 0 OR acg_worlds = 1);

'''


@execute
async def insert_record(address: str, profile_id: int = None):
    return f'INSERT OR IGNORE INTO linea_park (profile_id, address) VALUES (\'{profile_id}\', \'{address}\')'


@execute
async def select_profile(profile_id: int):
    return f'SELECT * FROM linea_park WHERE profile_id = {profile_id}'


@execute
async def task_done(address: str, task_name: str):
    return f"UPDATE linea_park SET {task_name} = 1 WHERE address = '{address}'"


@execute
async def get_task_status(address: str, task_name: str):
    return f"SELECT {task_name} FROM linea_park WHERE address = '{address}'"


async def main():
    print(await select_profile(118))


if __name__ == '__main__':
    asyncio.run(main())
