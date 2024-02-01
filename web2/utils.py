from typing import Callable, Any

from aiohttp.client_exceptions import ClientResponseError, ServerDisconnectedError
from better_automation.discord import DiscordClient
from yarl import URL
from logger import logger


class DiscordClientModified(DiscordClient):

    async def oauth_2(
            self,
            *,
            client_id: str,
            redirect_uri: str,
            code_challenge: str,
            code_challenge_method: str,
            scope: str,
            state: str = None,
            response_type: str = "code"
    ):
        url = f"{DiscordClient.BASE_API_URL}/oauth2/authorize"
        params = {
            "client_id": client_id,
            "response_type": response_type,
            "scope": scope,
            "redirect_uri": redirect_uri,
            "code_challenge": code_challenge,
            "code_challenge_method": code_challenge_method
        }
        if state:
            params["state"] = state
        payload = {
            "permissions": "0",
            "authorize": True,
        }
        response, data = await self.request("POST", url, json=payload, params=params)
        bind_url = URL(data["location"])
        bind_code = bind_url.query.get("code")
        return bind_code


def retry(n: int):
    def wrapper(func: Callable) -> Callable:
        async def inner(*args, **kwargs) -> Any:
            for i in range(n):
                try:
                    response, data = await func(*args, **kwargs)
                    response.raise_for_status()
                    return response, data
                except ServerDisconnectedError as e:
                    logger.error(e.message)
                    logger.info(f'Retrying {i + 1}')
                    continue
            else:
                logger.info(f'Tried to retry {n} times. Nothing can do anymore :(')
                return None

        return inner

    return wrapper


__all__ = [
    'DiscordClientModified',
    'retry'
]
