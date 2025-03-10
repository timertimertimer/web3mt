import pytz
from datetime import datetime
from dateutil.parser import parse
from pathlib import Path

moscow_tz = pytz.timezone("Europe/Moscow")


def format_time_strftime(func):
    def wrapper(*args, **kwargs):
        t = func(*args, **kwargs)
        if t:
            return t.strftime('%Y-%m-%d %H:%M:%S')

    return wrapper


@format_time_strftime
def parse_date(string: str = None, use_moscow_tz: bool = False):
    if string:
        utc_time = parse(string).replace(tzinfo=pytz.utc)
        return utc_time.astimezone(moscow_tz) if use_moscow_tz else utc_time
    return datetime.now(moscow_tz if use_moscow_tz else None)



data_path = Path(__file__).parent.parent.parent / 'data'
photos_path = data_path / 'photos'

if __name__ == '__main__':
    print(parse_date('2024-12-15T18:52:25Z', use_moscow_tz=True))