import json
from pathlib import Path


def read_json(path: str | Path, encoding: str = 'utf-8') -> list | dict:
    with open(path, encoding=encoding) as file:
        return json.load(file)


def read_txt(path: str | Path, encoding: str = 'utf-8') -> str:
    with open(path, encoding=encoding) as file:
        return file.read()


def get_privates(path: str | Path, encoding: str = 'utf-8') -> list[str]:
    return [private for private in read_txt(path, encoding).splitlines()]
