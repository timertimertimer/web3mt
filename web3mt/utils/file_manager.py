import asyncio
import aiofiles
import json
from os import stat_result
from pathlib import Path
from aiocsv import AsyncDictReader


class FileManager:

    @staticmethod
    def file_data(path: Path | str) -> stat_result:
        return Path(path).stat()

    @staticmethod
    def file_last_modification_time(path: Path | str) -> float:
        return FileManager.file_data(path).st_mtime

    @staticmethod
    async def write_async(path: Path | str, data: str | dict):
        async with aiofiles.open(path, 'w') as f:
            data = json.dumps(data) if str(path).endswith('.json') else str(data)
            await f.write(data)

    @staticmethod
    async def read_txt_async(path: Path | str):
        async with aiofiles.open(path) as f:
            return await f.read()

    @staticmethod
    async def read_json_async(path: Path | str) -> dict:
        return json.loads(await FileManager.read_txt_async(path))

    @staticmethod
    def read_json(path: str | Path, encoding: str = 'utf-8') -> list | dict:
        with open(path, encoding=encoding) as file:
            return json.load(file)

    @staticmethod
    def read_txt(path: str | Path, encoding: str = 'utf-8') -> str:
        with open(path, encoding=encoding) as file:
            return file.read()

    @staticmethod
    def get_privates(path: str | Path, encoding: str = 'utf-8') -> list[str]:
        return [private for private in FileManager.read_txt(path, encoding).splitlines()]

    @staticmethod
    def read_csv(path: str | Path, encoding: str = 'utf-8'):
        ...

    @staticmethod
    async def read_csv_async(path: str | Path, encoding: str = 'utf-8', delimiter: str = ';'):
        data = []
        async with aiofiles.open(path, encoding=encoding, newline="") as file:
            async for row in AsyncDictReader(file, delimiter=delimiter):
                data.append(row)
        return data


async def main():
    await FileManager.read_csv_async(r'C:\Users\timer\Code\web3mt\data\wallets.csv')


if __name__ == '__main__':
    asyncio.run(main())
