from pathlib import Path

with open(Path(__file__).parent / 'proxies.txt') as file:
    proxies = [line.strip() for line in file]

from .reader import parse_cookies
