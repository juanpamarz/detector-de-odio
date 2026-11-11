from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import func, select

from app.api.deps import AdminUser, CurrentUser, DbSession
from app.api.schemas import LoginRequest, TokenOut, UserCreate, UserOut, UserUpdate
from app.core.security import create_access_token, hash_password, verify_password
from app.db.models import DashboardUser
from app.services.accounts import prepare

router = APIRouter(tags=["auth"])
logger = logging.getLogger(__name__)

# Bloqueo temporal ante fuerza bruta: 5 intentos fallidos -> 15 minutos.
MAX_FAILED_LOGINS = 5
LOCKOUT = timedelta(minutes=15)

# Hash ficticio para igualar el tiempo de respuesta cuando el correo no existe.
_DUMMY_HASH = hash_password("timing-attack-guard")


@router.post("/auth/login", response_model=TokenOut)
def login(body: LoginRequest, db: DbSession) -> TokenOut:
    prepare()
    now = datetime.now(tz=UTC)
    user = db.scalar(select(DashboardUser).where(func.lower(DashboardUser.email) == body.email.lower()))
    if user and user.locked_until and user.locked_until > now:
        minutes = max(1, int((user.locked_until - now).total_seconds() // 60) + 1)
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            f"Demasiados intentos fallidos. Espera {minutes} min e intenta de nuevo.")
    valid = verify_password(body.password, user.hashed_password if user else _DUMMY_HASH)
    if not user or not valid or not user.is_active:
        if user:
            user.failed_logins = (user.failed_logins or 0) + 1
            if user.failed_logins >= MAX_FAILED_LOGINS:
                user.locked_until = now + LOCKOUT
                user.failed_logins = 0
                logger.warning("login_locked", extra={"user_id": user.id})
            db.commit()
        logger.warning("login_failed", extra={"email": body.email})
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Correo o contraseña incorrectos")
    user.failed_logins = 0
    user.locked_until = None
    user.last_login_at = now
    db.commit()
    token, expires = create_access_token(str(user.id), user.role.value)
    logger.info("login_ok", extra={"user_id": user.id, "role": user.role.value})
    return TokenOut(access_token=token, expires_in=expires, user=UserOut.model_validate(user))


@router.get("/auth/me", response_model=UserOut)
def me(user: CurrentUser) -> DashboardUser:
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(_: AdminUser, db: DbSession) -> list[DashboardUser]:
    return list(db.scalars(select(DashboardUser).order_by(DashboardUser.created_at)))


@router.post("/users", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def create_user(body: UserCreate, _: AdminUser, db: DbSession) -> DashboardUser:
    if db.scalar(select(DashboardUser).where(func.lower(DashboardUser.email) == body.email.lower())):
        raise HTTPException(status.HTTP_409_CONFLICT, "Ya existe una cuenta con ese correo")
    user = DashboardUser(email=body.email.lower(), full_name=body.full_name,
                         hashed_password=hash_password(body.password), role=body.role, is_active=True)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(user_id: int, body: UserUpdate, admin: AdminUser, db: DbSession) -> DashboardUser:
    user = db.get(DashboardUser, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Usuario no encontrado")
    if user.id == admin.id and (body.is_active is False or (body.role and body.role != admin.role)):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "No puedes desactivar ni cambiar el rol de tu propia cuenta")
    if body.full_name is not None:
        user.full_name = body.full_name
    if body.role is not None:
        user.role = body.role
    if body.is_active is not None:
        user.is_active = body.is_active
    if body.password:
        user.hashed_password = hash_password(body.password)
    db.commit()
    db.refresh(user)
    return user
