from dataclasses import dataclass

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token
from app.db.base import get_db
from app.models import UserRole

bearer = HTTPBearer(auto_error=False)


@dataclass
class CurrentUser:
    id: str
    organization_id: str
    role: str


async def get_current_user(
    creds: HTTPAuthorizationCredentials | None = Depends(bearer),
) -> CurrentUser:
    if creds is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Missing credentials")
    payload = decode_token(creds.credentials)
    if not payload:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Invalid or expired token")
    return CurrentUser(
        id=payload["sub"], organization_id=payload["org"], role=payload["role"]
    )


def require_role(*roles: UserRole):
    allowed = {r.value for r in roles}

    async def _checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Insufficient permissions")
        return user

    return _checker


# re-export for routers
__all__ = ["CurrentUser", "get_current_user", "require_role", "get_db", "AsyncSession"]
