from __future__ import annotations

from typing import Annotated

from fastapi import Depends

from backend.apps.client_api.auth import ROLE_SUPER_ADMIN
from backend.apps.client_api.deps import CurrentUser, require_roles

SuperAdminUser = Annotated[CurrentUser, Depends(require_roles(ROLE_SUPER_ADMIN))]
