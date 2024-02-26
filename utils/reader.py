import json
import configparser
from pathlib import Path

config = configparser.ConfigParser()
MWD = Path(__file__).parent.parent


def get_config_section(section: str) -> dict:
    path = MWD / 'config.ini'
    config.read(path)
    return dict(config[section])


def read_json(path: str | Path, encoding: str = None) -> list | dict:
    with open(path, encoding=encoding) as file:
        return json.load(file)


def read_txt(path: str | Path, encoding: str = None) -> str:
    with open(path, encoding=encoding) as file:
        return file.read()
