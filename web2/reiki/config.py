from web2.config import *
from models import Profile

REIKI_URL = 'https://reiki.web3go.xyz/'
REIKI_API = REIKI_URL + 'api/'
headers = {
    'Host': 'reiki.web3go.xyz',
    'Accept': '*/*',
    'Accept-Language': 'en-US,en;q=0.5',
    'Accept-Encoding': 'gzip, deflate, br',
    'Referer': 'https://reiki.web3go.xyz/aiweb/home',
    'Origin': REIKI_URL,
    'Connection': 'keep-alive',
    'Sec-Fetch-Dest': 'empty',
    'Sec-Fetch-Mode': 'no-cors',
    'Sec-Fetch-Site': 'same-origin',
    'app-site-code': 'home',
    'content-type': 'application/json',
    'x-app-channel': 'DIN',
    'x-public-api': 'public-api',
    'Pragma': 'no-cache',
    'Cache-Control': 'no-cache',
    'User-Agent': Profile.user_agent
}
QUIZES = {
    "d5cec2e4-ef2e-4598-9963-4552e9b32ef5": ['A', 'B', 'B', 'A', 'A'],
    "0aeb6c87-8c83-4cc6-a7da-e2b0e786c67c": ['C', 'D', 'D', 'D', 'C'],
    "374a470f-2e87-4408-9817-71531bb876ad": ['A', 'D', 'C', 'B', 'C'],
    "8e4403e6-dc1d-44b3-b80a-bb3ed0f91471": ['A', 'B', 'B', 'A', 'A'],
    "16a58c18-d3c9-4b8d-aedc-937e7e762a5c": ['A', 'D', 'A', 'B', 'D'],
    "631bb81f-035a-4ad5-8824-e219a7ec5ccb": ['', 'B', 'B', 'A', 'B']
}

if __name__ == '__main__':
    print(DATA_FILES)
