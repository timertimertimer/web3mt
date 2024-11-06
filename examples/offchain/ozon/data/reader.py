import json
from pathlib import Path


def parse_cookies(file_path: Path):
    if file_path.suffix == '.json':
        cookies = json.loads(file_path.read_text('utf-8'))
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
