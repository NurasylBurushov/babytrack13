from pydantic import BaseModel, Field, field_validator, validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from models import BookingStatus, MessageType
import re


# ── Auth ──────────────────────────────────────────────────
class SendOTPRequest(BaseModel):
    phone: str = Field(..., example="+77011234567")

    @validator("phone")
    def normalize_phone(cls, v):
        digits = re.sub(r"\D", "", v)
        if len(digits) == 11 and digits.startswith("7"):
            return "+" + digits
        if len(digits) == 10:
            return "+7" + digits
        raise ValueError("Неверный формат номера телефона")


class VerifyOTPRequest(BaseModel):
    phone: str
    code: str = Field(..., min_length=4, max_length=6)
    name: Optional[str] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: UUID
    is_new_user: bool


# ── User ──────────────────────────────────────────────────
class UserResponse(BaseModel):
    id: UUID
    phone: str
    name: Optional[str]
    avatar_url: Optional[str]
    is_verified: bool
    created_at: datetime

    class Config:
        from_attributes = True


class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    avatar_url: Optional[str] = None


# ── Child ─────────────────────────────────────────────────
class ChildCreate(BaseModel):
    name: str
    birth_date: Optional[datetime] = None
    notes: Optional[str] = None


class ChildResponse(BaseModel):
    id: UUID
    name: str
    birth_date: Optional[datetime]
    notes: Optional[str]

    class Config:
        from_attributes = True


# ── Nanny ─────────────────────────────────────────────────
class NannyResponse(BaseModel):
    id: UUID
    name: str
    age: Optional[int]
    bio: Optional[str]
    avatar_url: Optional[str]
    hourly_rate: int
    experience_years: int
    city: Optional[str] = None
    district: Optional[str]
    latitude: Optional[float]
    longitude: Optional[float]
    specialties: List[str]
    languages: List[str]
    work_days: List[str]
    rating: float
    review_count: int
    is_verified: bool
    is_available: bool
    distance_km: Optional[float] = None   # вычисляется динамически

    @field_validator("name", mode="before")
    @classmethod
    def name_non_empty(cls, v):
        if v is None or not str(v).strip():
            return "Няня"
        return str(v).strip()

    @field_validator("specialties", "languages", "work_days", mode="before")
    @classmethod
    def none_arrays_to_empty(cls, v):
        """PostgreSQL ARRAY может прийти как NULL — для JSON и Pydantic нужны списки."""
        return v if v is not None else []

    @field_validator("city", mode="before")
    @classmethod
    def city_none_to_default(cls, v):
        if v is None or (isinstance(v, str) and not str(v).strip()):
            return "Астана"
        return str(v)

    class Config:
        from_attributes = True


class NannySelfUpdate(BaseModel):
    """Обновление своего профиля няни (запись Nanny по user_id)."""
    avatar_url: Optional[str] = None


class NannyListResponse(BaseModel):
    nannies: List[NannyResponse]
    total: int
    page: int
    per_page: int


class NannyFilters(BaseModel):
    city: Optional[str] = None
    min_rating: Optional[float] = None
    max_rate: Optional[int] = None
    specialties: Optional[List[str]] = None
    languages: Optional[List[str]] = None
    is_verified: Optional[bool] = None
    is_available: Optional[bool] = None
    lat: Optional[float] = None
    lng: Optional[float] = None
    radius_km: Optional[float] = 10.0
    sort_by: str = "rating"  # rating | rate_asc | rate_desc | distance
    page: int = 1
    per_page: int = 20


# ── Booking ───────────────────────────────────────────────
class BookingCreate(BaseModel):
    nanny_id: UUID
    date: datetime
    start_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    end_time: str = Field(..., pattern=r"^\d{2}:\d{2}$")
    children_count: int = Field(1, ge=1, le=10)
    notes: Optional[str] = None


class BookingResponse(BaseModel):
    id: UUID
    nanny: NannyResponse
    date: datetime
    start_time: str
    end_time: str
    children_count: int
    notes: Optional[str]
    status: BookingStatus
    total_cost: Optional[int]
    created_at: datetime

    class Config:
        from_attributes = True


class BookingStatusUpdate(BaseModel):
    status: BookingStatus


# ── Review ────────────────────────────────────────────────
class ReviewCreate(BaseModel):
    rating: float = Field(..., ge=1, le=5)
    text: Optional[str] = None
    child_age: Optional[str] = None


class ReviewResponse(BaseModel):
    id: UUID
    user_id: UUID
    rating: float
    text: Optional[str]
    child_age: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


# ── Chat & Messages ───────────────────────────────────────
class ChatResponse(BaseModel):
    id: UUID
    booking_id: UUID
    nanny: NannyResponse
    last_message: Optional[str] = None
    unread_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class MessageCreate(BaseModel):
    text: Optional[str] = None
    type: MessageType = MessageType.text


class MessageResponse(BaseModel):
    id: UUID
    chat_id: UUID
    sender_id: UUID
    type: MessageType
    text: Optional[str]
    image_url: Optional[str]
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


# ── Favorites ─────────────────────────────────────────────
class FavoriteToggleResponse(BaseModel):
    is_favorite: bool
    nanny_id: UUID
