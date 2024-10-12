import sqlite3
from web3db.base import BaseDBHelper
from web3mt.utils import FileManager

db_name = 'state.db'


def create_table():
    connection = sqlite3.connect(db_name)
    cursor = connection.cursor()
    query = FileManager.read_txt('create_table.sql')
    cursor.execute(query)
    connection.commit()
    connection.close()


class DBHelper(BaseDBHelper):
    def __init__(
            self, url: str = f'sqlite+aiosqlite:///C:/Users/timer/Code/web3mt/examples/dex/evm/basehunt/db/{db_name}',
            echo: bool = False
    ):
        super().__init__(url, echo)


if __name__ == '__main__':
    create_table()
