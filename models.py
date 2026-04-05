from sqlalchemy import (
    Column, String, Integer, Float, Boolean, DateTime, Text,
    ForeignKey, Enum, ARRAY, JSON
)
from sqlalchemy.orm import relationship
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from database import Base
import uuid
import enum


class BookingStatus(str, enum.Enum):
    pending = "pending"
    confirmed = "confirmed"
    completed = "completed"
    cancelled = "cancelled"


class MessageType(str, enum.Enum):
    text = "text"
    image = "image"
    system = "system"


# ── User ──────────────────────────────────────────────────
class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), unique=True, nullable=False, index=True)
    name = Column(String(100))
    avatar_url = Column(String(500))
    is_active = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    children = relationship("Child", back_populates="parent", cascade="all, delete-orphan")
    bookings = relationship("Booking", back_populates="user", foreign_keys="Booking.user_id")
    favorites = relationship("Favorite", back_populates="user", cascade="all, delete-orphan")
    messages_sent = relationship("Message", back_populates="sender", foreign_keys="Message.sender_id")


# ── Child ─────────────────────────────────────────────────
class Child(Base):
    __tablename__ = "children"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name = Column(String(100), nullable=False)
    birth_date = Column(DateTime)
    notes = Column(Text)

    parent = relationship("User", back_populates="children")


# ── Nanny ─────────────────────────────────────────────────
class Nanny(Base):
    __tablename__ = "nannies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)

    # Основная информация
    name = Column(String(100), nullable=False)
    age = Column(Integer)
    bio = Column(Text)
    avatar_url = Column(String(500))
    hourly_rate = Column(Integer, nullable=False)
    experience_years = Column(Integer, default=0)

    # Местоположение
    city = Column(String(100), default="Кокшетау")
    district = Column(String(100))
    latitude = Column(Float)
    longitude = Column(Float)

    # Характеристики
    specialties = Column(ARRAY(String), default=[])
    languages = Column(ARRAY(String), default=[])
    work_days = Column(ARRAY(String), default=[])

    # Рейтинг (вычисляется)
    rating = Column(Float, default=0.0)
    review_count = Column(Integer, default=0)

    # Статусы
    is_verified = Column(Boolean, default=False)
    is_available = Column(Boolean, default=True)
    is_active = Column(Boolean, default=True)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    # Связи
    bookings = relationship("Booking", back_populates="nanny")
    reviews = relationship("Review", back_populates="nanny")
    favorites = relationship("Favorite", back_populates="nanny")
    schedule_slots = relationship("ScheduleSlot", back_populates="nanny", cascade="all, delete-orphan")


# ── ScheduleSlot ──────────────────────────────────────────
class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nanny_id = Column(UUID(as_uuid=True), ForeignKey("nannies.id"), nullable=False)
    day_of_week = Column(Integer)          # 0=Пн ... 6=Вс
    start_time = Column(String(5))        # "09:00"
    end_time = Column(String(5))          # "18:00"
    is_available = Column(Boolean, default=True)

    nanny = relationship("Nanny", back_populates="schedule_slots")


# ── Booking ───────────────────────────────────────────────
class Booking(Base):
    __tablename__ = "bookings"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    nanny_id = Column(UUID(as_uuid=True), ForeignKey("nannies.id"), nullable=False)

    date = Column(DateTime(timezone=True), nullable=False)
    start_time = Column(String(5), nullable=False)
    end_time = Column(String(5), nullable=False)
    children_count = Column(Integer, default=1)
    notes = Column(Text)

    status = Column(Enum(BookingStatus), default=BookingStatus.pending)
    total_cost = Column(Integer)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    user = relationship("User", back_populates="bookings", foreign_keys=[user_id])
    nanny = relationship("Nanny", back_populates="bookings")
    review = relationship("Review", back_populates="booking", uselist=False)
    chat = relationship("Chat", back_populates="booking", uselist=False)


# ── Review ────────────────────────────────────────────────
class Review(Base):
    __tablename__ = "reviews"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False, unique=True)
    nanny_id = Column(UUID(as_uuid=True), ForeignKey("nannies.id"), nullable=False)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    rating = Column(Float, nullable=False)
    text = Column(Text)
    child_age = Column(String(50))

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    nanny = relationship("Nanny", back_populates="reviews")
    booking = relationship("Booking", back_populates="review")


# ── Favorite ──────────────────────────────────────────────
class Favorite(Base):
    __tablename__ = "favorites"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    nanny_id = Column(UUID(as_uuid=True), ForeignKey("nannies.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user = relationship("User", back_populates="favorites")
    nanny = relationship("Nanny", back_populates="favorites")


# ── SMS OTP ───────────────────────────────────────────────
class OTPCode(Base):
    __tablename__ = "otp_codes"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone = Column(String(20), nullable=False, index=True)
    code = Column(String(6), nullable=False)
    is_used = Column(Boolean, default=False)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ── Chat ──────────────────────────────────────────────────
class Chat(Base):
    __tablename__ = "chats"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), unique=True)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    nanny_id = Column(UUID(as_uuid=True), ForeignKey("nannies.id"), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    booking = relationship("Booking", back_populates="chat")
    messages = relationship("Message", back_populates="chat", order_by="Message.created_at")


# ── Message ───────────────────────────────────────────────
class Message(Base):
    __tablename__ = "messages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id = Column(UUID(as_uuid=True), ForeignKey("chats.id"), nullable=False)
    sender_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)

    type = Column(Enum(MessageType), default=MessageType.text)
    text = Column(Text)
    image_url = Column(String(500))
    is_read = Column(Boolean, default=False)

    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chat = relationship("Chat", back_populates="messages")
    sender = relationship("User", back_populates="messages_sent", foreign_keys=[sender_id])
