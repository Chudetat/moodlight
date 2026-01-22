"""Application configuration."""
import os
from functools import lru_cache
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # App
    app_name: str = "Dopa"
    app_url: str = "http://localhost:8000"
    secret_key: str = "change-me-in-production"

    # Database
    database_url: str = "sqlite:///./dopa.db"

    # Oura OAuth
    oura_client_id: str = ""
    oura_client_secret: str = ""
    oura_redirect_uri: str = "http://localhost:8000/auth/oura/callback"
    oura_auth_url: str = "https://cloud.ouraring.com/oauth/authorize"
    oura_token_url: str = "https://api.ouraring.com/oauth/token"
    oura_api_url: str = "https://api.ouraring.com/v2"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
