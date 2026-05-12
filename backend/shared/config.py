from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_env: str = Field(default="dev", description="dev|staging|prod")
    database_url: str = Field(default="postgresql+psycopg://postgres:postgres@localhost:5432/zysmart")

    meta_app_secret: str = Field(default="", description="Meta app secret for webhook signature validation")
    meta_verify_token: str = Field(default="change-me", description="Meta webhook verify token")
    meta_access_token: str = Field(
        default="",
        description="Required for outbox_sender: Meta Cloud API system-user or long-lived token used to POST /messages",
    )
    meta_graph_version: str = Field(
        default="v22.0",
        description="Required for outbox_sender: Graph API version segment in https://graph.facebook.com/{version}/… (e.g. v22.0)",
    )

    outbox_max_attempts: int = Field(default=15, ge=1, description="Outbox: after this many failed send attempts, row is marked DEAD")
    outbox_sending_lease_seconds: int = Field(
        default=120,
        ge=10,
        description="Outbox: SENDING lease; if a worker dies mid-send, row becomes eligible again after this (see worker comments on duplicates)",
    )


settings = Settings()

