from better_automation.discord import DiscordClient
from yarl import URL


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


__all__ = ['DiscordClientModified']
