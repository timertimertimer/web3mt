import aiosqlite


async def create_table():
    async with aiosqlite.connect("reiki.db") as db:
        cursor = await db.cursor()
        await cursor.execute('''
            CREATE TABLE IF NOT EXISTS tokens (
                address varchar(66) NOT NULL,
                bearer_token text NOT NULL,
                UNIQUE (address)
            )
        ''')

        await db.commit()


async def get_token_by_address(address: str) -> str:
    async with aiosqlite.connect("reiki.db") as db:
        cursor = await db.cursor()
        await cursor.execute('SELECT bearer_token FROM tokens WHERE address = ?', (address,))
        record = await cursor.fetchone()
        return record[0] if record else record


async def insert_record(address: str, bearer_token: str):
    async with aiosqlite.connect("reiki.db") as db:
        cursor = await db.cursor()
        await cursor.execute(
            'INSERT OR REPLACE INTO tokens (address, bearer_token) VALUES (?, ?)',
            (address, bearer_token)
        )
        await db.commit()


__all__ = [
    'create_table',
    'get_token_by_address',
    'insert_record'
]
