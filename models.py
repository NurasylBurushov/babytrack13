from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, Text, ForeignKey, Enum, ARRAY
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


class User(Base):
    __tablename__ = "users"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone       = Column(String(20),  unique=True, nullable=True, index=True)
    email       = Column(String(255), unique=True, nullable=True, index=True)
    password    = Column(String(255), nullable=True)
    google_id   = Column(String(255), unique=True, nullable=True, index=True)
    apple_id    = Column(String(255), unique=True, nullable=True, index=True)
    name        = Column(String(100))
    avatar      = Column(String(500))
    role        = Column(String(50), default="parent")
    is_active   = Column(Boolean, default=True)
    is_verified = Column(Boolean, default=False)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())
    updated_at  = Column(DateTime(timezone=True), onupdate=func.now())

    children       = relationship("Child",   back_populates="parent",   cascade="all, delete-orphan")
    bookings       = relationship("Booking", back_populates="user",      foreign_keys="Booking.user_id")
    favorites      = relationship("Favorite",back_populates="user",      cascade="all, delete-orphan")
    messages_sent  = relationship("Message", back_populates="sender",    foreign_keys="Message.sender_id")
    market_items   = relationship("MarketItem", back_populates="seller", cascade="all, delete-orphan")


class Child(Base):
    __tablename__ = "children"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    parent_id   = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    name        = Column(String(100), nullable=False)
    birth_date  = Column(DateTime)
    notes       = Column(Text)

    parent = relationship("User", back_populates="children")


class Nanny(Base):
    __tablename__ = "nannies"

    id               = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id          = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    name             = Column(String(100), nullable=False)
    age              = Column(Integer)
    bio              = Column(Text)
    avatar_url       = Column(String(500))
    hourly_rate      = Column(Integer, nullable=False, default=2000)
    experience_years = Column(Integer, default=0)
    city             = Column(String(100), default="Астана")
    district         = Column(String(100))
    latitude         = Column(Float)
    longitude        = Column(Float)
    specialties      = Column(ARRAY(String), default=[])
    languages        = Column(ARRAY(String), default=[])
    work_days        = Column(ARRAY(String), default=[])
    rating           = Column(Float, default=0.0)
    review_count     = Column(Integer, default=0)
    is_verified      = Column(Boolean, default=False)
    is_available     = Column(Boolean, default=True)
    is_active        = Column(Boolean, default=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), onupdate=func.now())

    bookings       = relationship("Booking",      back_populates="nanny")
    reviews        = relationship("Review",       back_populates="nanny")
    favorites      = relationship("Favorite",     back_populates="nanny")
    schedule_slots = relationship("ScheduleSlot", back_populates="nanny", cascade="all, delete-orphan")
    locations      = relationship("NannyLocation",back_populates="nanny", cascade="all, delete-orphan")


class ScheduleSlot(Base):
    __tablename__ = "schedule_slots"

    id           = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nanny_id     = Column(UUID(as_uuid=True), ForeignKey("nannies.id"), nullable=False)
    day_of_week  = Column(Integer)
    start_time   = Column(String(5))
    end_time     = Column(String(5))
    is_available = Column(Boolean, default=True)

    nanny = relationship("Nanny", back_populates="schedule_slots")


class Booking(Base):
    __tablename__ = "bookings"

    id             = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id        = Column(UUID(as_uuid=True), ForeignKey("users.id"),   nullable=False)
    nanny_id       = Column(UUID(as_uuid=True), ForeignKey("nannies.id"), nullable=False)
    date           = Column(DateTime(timezone=True), nullable=False)
    start_time     = Column(String(5), nullable=False)
    end_time       = Column(String(5), nullable=False)
    children_count = Column(Integer, default=1)
    notes          = Column(Text)
    status         = Column(Enum(BookingStatus), default=BookingStatus.pending)
    total_cost     = Column(Integer)
    created_at     = Column(DateTime(timezone=True), server_default=func.now())
    updated_at     = Column(DateTime(timezone=True), onupdate=func.now())

    user    = relationship("User",    back_populates="bookings", foreign_keys=[user_id])
    nanny   = relationship("Nanny",   back_populates="bookings")
    review  = relationship("Review",  back_populates="booking",  uselist=False)
    chat    = relationship("Chat",    back_populates="booking",  uselist=False)


class Review(Base):
    __tablename__ = "reviews"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), nullable=False, unique=True)
    nanny_id   = Column(UUID(as_uuid=True), ForeignKey("nannies.id"),  nullable=False)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"),    nullable=False)
    rating     = Column(Float, nullable=False)
    text       = Column(Text)
    child_age  = Column(String(50))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    nanny   = relationship("Nanny",   back_populates="reviews")
    booking = relationship("Booking", back_populates="review")


class Favorite(Base):
    __tablename__ = "favorites"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"),    nullable=False)
    nanny_id   = Column(UUID(as_uuid=True), ForeignKey("nannies.id"),  nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    user  = relationship("User",  back_populates="favorites")
    nanny = relationship("Nanny", back_populates="favorites")


class OTPCode(Base):
    __tablename__ = "otp_codes"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    phone      = Column(String(20), nullable=False, index=True)
    code       = Column(String(6),  nullable=False)
    is_used    = Column(Boolean, default=False)
    attempts   = Column(Integer, default=0)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Chat(Base):
    __tablename__ = "chats"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    booking_id = Column(UUID(as_uuid=True), ForeignKey("bookings.id"), unique=True)
    user_id    = Column(UUID(as_uuid=True), ForeignKey("users.id"),    nullable=False)
    nanny_id   = Column(UUID(as_uuid=True), ForeignKey("nannies.id"),  nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    booking  = relationship("Booking", back_populates="chat")
    messages = relationship("Message", back_populates="chat", order_by="Message.created_at")


class Message(Base):
    __tablename__ = "messages"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    chat_id    = Column(UUID(as_uuid=True), ForeignKey("chats.id"),  nullable=False)
    sender_id  = Column(UUID(as_uuid=True), ForeignKey("users.id"),  nullable=False)
    type       = Column(Enum(MessageType), default=MessageType.text)
    text       = Column(Text)
    image_url  = Column(String(500))
    is_read    = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    chat   = relationship("Chat",    back_populates="messages")
    sender = relationship("User",    back_populates="messages_sent", foreign_keys=[sender_id])


class MarketItem(Base):
    __tablename__ = "market_items"

    id          = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    seller_id   = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    title       = Column(String(200), nullable=False)
    description = Column(Text)
    price       = Column(Integer, nullable=False)
    category    = Column(String(100), nullable=False)
    condition   = Column(String(50), default="used")
    image_url   = Column(String(500))
    is_active   = Column(Boolean, default=True)
    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    seller = relationship("User", back_populates="market_items")


class NannyLocation(Base):
    __tablename__ = "nanny_locations"

    id         = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    nanny_id   = Column(UUID(as_uuid=True), ForeignKey("nannies.id"), nullable=False)
    latitude   = Column(Float, nullable=False)
    longitude  = Column(Float, nullable=False)
    address    = Column(String(500))
    speed      = Column(Float)
    battery    = Column(Integer)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    nanny = relationship("Nanny", back_populates="locations")
