"""DTOs de la API (contratos con el frontend)."""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from app.db.models import ActionTaken, Role, UserResponse
from app.domain.categories import HateCategory, MacroCategory

T = TypeVar("T")


class ORM(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# --- Autenticación -----------------------------------------------------------
class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(ORM):
    id: int
    email: str
    full_name: str
    role: Role
    is_active: bool
    created_at: datetime
    last_login_at: datetime | None


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    user: UserOut


class UserCreate(BaseModel):
    email: EmailStr
    full_name: str = Field(min_length=2, max_length=120)
    password: str = Field(min_length=10, max_length=128)
    role: Role = Role.ANALYST


class UserUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=2, max_length=120)
    role: Role | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=10, max_length=128)


# --- Analítica ---------------------------------------------------------------
class Overview(BaseModel):
    analyzed: int
    incidents: int
    incidents_prev: int
    crisis: int
    users_sanctioned: int
    users_banned: int
    active_groups: int
    incident_rate: float
    mean_toxicity: float
    withdrawn: int
    republished: int


class CategorySlice(BaseModel):
    macro: MacroCategory
    category: HateCategory
    count: int


class TimePoint(BaseModel):
    bucket: datetime
    analyzed: int
    incidents: int
    identity_hate: int
    aggression: int
    sexual: int
    crisis: int


class StackedRow(BaseModel):
    id: int
    label: str
    identity_hate: int
    aggression: int
    sexual: int
    crisis: int
    total: int
    extra: dict[str, float | int | bool | None] = {}


class HeatCell(BaseModel):
    weekday: int  # 0 = lunes
    hour: int
    count: int


# --- Grupos ------------------------------------------------------------------
class GroupOut(BaseModel):
    id: int
    title: str
    chat_type: str
    is_active: bool
    toxicity_threshold: float | None
    effective_threshold: float
    last_activity_at: datetime | None
    analyzed: int
    incidents: int
    crisis: int
    banned: int
    incident_rate: float
    bot_status: str | None = None
    can_delete: bool | None = None
    can_restrict: bool | None = None
    member_count: int | None = None
    checked_at: datetime | None = None


class GroupUpdate(BaseModel):
    toxicity_threshold: float | None = Field(default=None, ge=0.05, le=0.99)
    clear_threshold: bool = False
    is_active: bool | None = None


# --- Incidentes --------------------------------------------------------------
class IncidentOut(BaseModel):
    id: int
    created_at: datetime
    message_sent_at: datetime
    group_id: int
    group_title: str
    user_id: int
    user_display: str
    message_text: str
    is_text_redacted: bool
    category: HateCategory
    macro_category: MacroCategory
    toxicity_score: float
    crisis_score: float
    action: ActionTaken
    user_response: UserResponse | None
    providers: list[dict[str, object]]


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    page_size: int
