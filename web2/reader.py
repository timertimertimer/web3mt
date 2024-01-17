from pprint import pprint

from better_automation.twitter import TwitterAccount
from eth_account import Account

from config import DATA_FILES, DATA_PATH
from models import Profile, DiscordAccountModified
from utils import get_accounts


def get_profiles():
    data = {}
    for filename in DATA_FILES:
        with open(DATA_PATH / filename, encoding='utf-8') as file:
            data[filename.rstrip('.txt')] = [row.strip() for row in file]

    profiles = [
        Profile(
            discord=DiscordAccountModified(discord),
            email=email,
            twitter=TwitterAccount(twitter),
            proxy=proxy,
            evm_account=Account.from_key(private)
        )
        for discord, email, twitter, proxy, private in zip(
            data['discords'], data['emails'], data['twitters'], data['proxies'], get_accounts()
        )
    ]

    return profiles


if __name__ == '__main__':
    pprint(get_profiles())
