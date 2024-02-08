from better_automation.discord import DiscordAccount
from pydantic import Field


class DiscordAccountModified(DiscordAccount):
    auth_token: str = Field(default=None, pattern=r"^[A-Za-z0-9+._-]{70}$|^[A-Za-z0-9+._-]{72}$")
