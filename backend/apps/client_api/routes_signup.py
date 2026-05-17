"""M3 signup — intentionally deferred (product confirmation pending)."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

router = APIRouter(tags=["signup"])


class SignupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=200)
    business_name: str = Field(min_length=1, max_length=500)


@router.post("/signup", status_code=status.HTTP_501_NOT_IMPLEMENTED)
def signup_deferred(_body: SignupIn) -> None:
    """Blueprint M3 — use dev seed / admin provisioning until OTP signup is approved."""
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail=(
            "M3 signup is deferred. Use backend/tools/setup_dev_logins.py for dev tenants, "
            "or ask Stem to re-open M3 (OTP, team, catalog)."
        ),
    )
