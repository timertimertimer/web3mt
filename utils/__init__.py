from .logger import logger
from .profile_session import ProfileSession
from .reader import read_json, read_txt, get_config_section, MWD
from .sleeping import sleep
from .windows import set_windows_event_loop_policy

PRICE_FACTOR = 1.1
INCREASE_GAS = 1.1
Z8 = 10 ** 8
Z18 = 10 ** 18
