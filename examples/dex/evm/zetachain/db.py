import aiosqlite


def execute(func):
    async def wrapper(*args, **kwargs):
        async with aiosqlite.connect("zetachain.db") as db:
            cursor = await db.cursor()
            await cursor.execute(await func(*args, **kwargs))
            await db.commit()
            record = await cursor.fetchone()
            return record[0] if record else record

    return wrapper


@execute
async def create_table():
    return (
        f"""CREATE TABLE IF NOT EXISTS zetachain (
                profile_id INT,
                address TEXT NOT NULL,
                level INT,
                points INT,
                rank INT,
                UNIQUE (address)
            )
        """
    )


@execute
async def insert_record(address: str, profile_id: int = None):
    return f'INSERT OR IGNORE INTO zetachain (profile_id, address) VALUES (\'{profile_id}\', \'{address}\')'


@execute
async def select_profile(profile_id: int):
    return f'SELECT * FROM zetachain WHERE profile_id = {profile_id}'


@execute
async def update_stats(address: str, level: int, points: int, rank: int):
    return f'UPDATE zetachain SET level = {level}, points = {points}, rank = {rank} WHERE address = \'{address}\''
