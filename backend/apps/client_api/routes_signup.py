"""M3 signup — create trial tenant + owner user (email/password)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from backend.shared.db import engine
from backend.shared.product_config import load_trial_days_default

from .auth import hash_password

router = APIRouter(tags=["signup"])


class SignupIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    email: str = Field(min_length=3, max_length=320, pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    password: str = Field(min_length=8, max_length=200)
    business_name: str = Field(min_length=1, max_length=500)
    category: str | None = Field(default="general", max_length=200)
    owner_phone_e164: str | None = Field(default=None, max_length=20)
    trial_days: int | None = Field(
        default=None,
        ge=1,
        le=90,
        description="Omit to use ops_runtime_config product.trial_days_default (phase 2 default 3).",
    )


class SignupOut(BaseModel):
    client_id: str
    owner_user_id: str
    email: str
    entitlement_plan: str
    trial_end: str
    message: str


@router.post("/signup", response_model=SignupOut, status_code=status.HTTP_201_CREATED)
def signup(body: SignupIn) -> SignupOut:
    """Create ``api_clients`` (trial) + owner ``api_users`` row. OTP/team/catalog remain future work."""
    email = body.email.strip().lower()
    pw_hash = hash_password(body.password)

    try:
        with engine.begin() as conn:
            trial_days = body.trial_days if body.trial_days is not None else load_trial_days_default(conn)
            trial_end = datetime.now(timezone.utc) + timedelta(days=trial_days)
            exists = conn.execute(
                text("SELECT 1 FROM api_users WHERE lower(email) = :e LIMIT 1"),
                {"e": email},
            ).fetchone()
            if exists:
                raise HTTPException(
                    status_code=status.HTTP_409_CONFLICT,
                    detail="email already registered",
                )

            client_id = conn.execute(
                text(
                    """
                    INSERT INTO api_clients (
                      business_name, category, owner_phone_e164,
                      entitlement_plan, trial_end
                    )
                    VALUES (:bn, :cat, :phone, 'trial', :trial_end)
                    RETURNING id::text
                    """
                ),
                {
                    "bn": body.business_name.strip(),
                    "cat": (body.category or "general").strip(),
                    "phone": body.owner_phone_e164,
                    "trial_end": trial_end,
                },
            ).scalar_one()

            owner_id = conn.execute(
                text(
                    """
                    INSERT INTO api_users (client_id, name, email, role, password_hash)
                    VALUES (
                      CAST(:cid AS uuid),
                      :name,
                      :email,
                      'owner',
                      :pw
                    )
                    RETURNING id::text
                    """
                ),
                {
                    "cid": client_id,
                    "name": body.business_name.strip()[:200],
                    "email": email,
                    "pw": pw_hash,
                },
            ).scalar_one()
    except HTTPException:
        raise
    except IntegrityError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="signup conflict (email or constraint)",
        ) from e

    return SignupOut(
        client_id=client_id,
        owner_user_id=owner_id,
        email=email,
        entitlement_plan="trial",
        trial_end=trial_end.isoformat(),
        message="Account created. Log in with POST /auth/login, then provision WhatsApp via dev_seed or admin tools.",
    )
