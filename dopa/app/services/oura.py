"""Oura Ring API integration service."""
import httpx
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any
from urllib.parse import urlencode
from ..config import get_settings

settings = get_settings()


class OuraService:
    """Service for Oura Ring OAuth and API interactions."""

    def __init__(self):
        self.client_id = settings.oura_client_id
        self.client_secret = settings.oura_client_secret
        self.redirect_uri = settings.oura_redirect_uri
        self.auth_url = settings.oura_auth_url
        self.token_url = settings.oura_token_url
        self.api_url = settings.oura_api_url

    def get_authorization_url(self, state: str) -> str:
        """Generate Oura OAuth authorization URL."""
        params = {
            "client_id": self.client_id,
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "scope": "heartrate",
            "state": state,
        }
        return f"{self.auth_url}?{urlencode(params)}"

    async def exchange_code_for_token(self, code: str) -> Dict[str, Any]:
        """Exchange authorization code for access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": self.redirect_uri,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()

    async def refresh_access_token(self, refresh_token: str) -> Dict[str, Any]:
        """Refresh an expired access token."""
        async with httpx.AsyncClient() as client:
            response = await client.post(
                self.token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                },
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            response.raise_for_status()
            return response.json()

    async def get_heart_rate(
        self,
        access_token: str,
        start_datetime: datetime,
        end_datetime: datetime,
    ) -> List[Dict[str, Any]]:
        """Fetch heart rate data from Oura API."""
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{self.api_url}/usercollection/heartrate",
                params={
                    "start_datetime": start_datetime.isoformat(),
                    "end_datetime": end_datetime.isoformat(),
                },
                headers={"Authorization": f"Bearer {access_token}"},
            )
            response.raise_for_status()
            data = response.json()
            return data.get("data", [])

    async def validate_token(self, access_token: str) -> bool:
        """Validate if an access token is still valid."""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.api_url}/usercollection/personal_info",
                    headers={"Authorization": f"Bearer {access_token}"},
                )
                return response.status_code == 200
        except Exception:
            return False


def get_oura_service() -> OuraService:
    """Dependency for getting Oura service instance."""
    return OuraService()
