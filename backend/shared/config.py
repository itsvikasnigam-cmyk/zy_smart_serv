from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="dev", description="dev|staging|prod")
    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@localhost:5432/zysmart")

    meta_app_secret: str = Field(default="", description="Meta app secret for webhook signature validation")
    meta_verify_token: str = Field(default="change-me", description="Meta webhook verify token")
    meta_access_token: str = Field(default="", description="Meta Cloud API access token")
    meta_graph_version: str = Field(default="v22.0", description="Meta Graph API version, pinned")


settings = Settings()

