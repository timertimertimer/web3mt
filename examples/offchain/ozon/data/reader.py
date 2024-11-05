import json
from pathlib import Path


def parse_cookies(file_name: str):
    file_path = Path(__file__).parent / file_name
    if file_name.endswith('.json'):
        cookies = json.load(open(file_path, 'r'))
        if 'x-o3-app-name' not in cookies:
            cookies.append({'name': 'x-o3-app-name', 'value': 'ozonapp_ios'})
        if 'x-o3-app-version' not in cookies:
            cookies.append({'name': 'x-o3-app-version', 'value': '17.40.1(876)'})
        if 'MOBILE_APP_TYPE' not in cookies:
            cookies.append({'name': 'MOBILE_APP_TYPE', 'value': 'ozonapp_ios'})
        if 'ob_theme' not in cookies:
            cookies.append({'name': 'ob_theme', 'value': 'DARK'})
        return {cookie["name"]: cookie["value"] for cookie in cookies}
    else:
        with open(file_path) as file:
            return dict(item.split("=", 1) for item in file.read().split("; "))
