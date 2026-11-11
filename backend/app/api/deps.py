"""Dependencias: sesión, usuario autenticado y control de acceso por rol."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import InvalidTokenError, decode_access_token
from app.db.models import DashboardUser, Role
from app.db.session import get_db

DbSession = Annotated[Session, Depends(get_db)]
_bearer = HTTPBearer(auto_error=False)


def get_current_user(
    db: DbSession,
    creds: Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)],
) -> DashboardUser:
    unauthorized = HTTPException(status.HTTP_401_UNAUTHORIZED, "Sesión inválida o expirada",
                                 headers={"WWW-Authenticate": "Bearer"})
    if creds is None:
        raise unauthorized
    try:
        claims = decode_access_token(creds.credentials)
        user = db.get(DashboardUser, int(claims["sub"]))
    except (InvalidTokenError, KeyError, ValueError):
        raise unauthorized from None
    if user is None or not user.is_active:
        raise unauthorized
    return user


CurrentUser = Annotated[DashboardUser, Depends(get_current_user)]


def require_roles(*roles: Role) -> Callable[[DashboardUser], DashboardUser]:
    def checker(user: CurrentUser) -> DashboardUser:
        if user.role not in roles:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "Tu rol no permite esta acción")
        return user

    return checker


AdminUser = Annotated[DashboardUser, Depends(require_roles(Role.ADMIN))]
ModeratorUser = Annotated[DashboardUser, Depends(require_roles(Role.ADMIN, Role.MODERATOR))]
