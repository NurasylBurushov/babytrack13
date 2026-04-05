from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List, Optional
from database import get_db
from models import Booking, Nanny, BookingStatus, Chat, Review, User
from schemas import BookingCreate, BookingResponse, BookingStatusUpdate, ReviewCreate, ReviewResponse
from auth import get_current_user
from router_nannies import nanny_to_response

router = APIRouter(prefix="/bookings", tags=["Бронирование"])


def calc_hours(start: str, end: str) -> float:
    sh, sm = map(int, start.split(":"))
    eh, em = map(int, end.split(":"))
    return max(0, (eh * 60 + em - sh * 60 - sm) / 60)


@router.post("", response_model=BookingResponse, status_code=status.HTTP_201_CREATED, summary="Создать запись")
async def create_booking(
    body: BookingCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # Проверяем няню
    result = await db.execute(select(Nanny).where(Nanny.id == body.nanny_id))
    nanny = result.scalar_one_or_none()
    if not nanny:
        raise HTTPException(status_code=404, detail="Няня не найдена")
    if not nanny.is_available:
        raise HTTPException(status_code=400, detail="Няня недоступна")

    # Проверяем конфликт времени
    existing = await db.execute(
        select(Booking).where(
            Booking.nanny_id == body.nanny_id,
            Booking.date == body.date,
            Booking.status.in_([BookingStatus.pending, BookingStatus.confirmed]),
        )
    )
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Это время уже занято")

    hours = calc_hours(body.start_time, body.end_time)
    if hours < 1:
        raise HTTPException(status_code=400, detail="Минимальный заказ — 1 час")

    total = int(hours * nanny.hourly_rate)

    booking = Booking(
        user_id=current_user.id,
        nanny_id=body.nanny_id,
        date=body.date,
        start_time=body.start_time,
        end_time=body.end_time,
        children_count=body.children_count,
        notes=body.notes,
        total_cost=total,
        status=BookingStatus.pending,
    )
    db.add(booking)
    await db.flush()

    # Автоматически создаём чат
    chat = Chat(
        booking_id=booking.id,
        user_id=current_user.id,
        nanny_id=nanny.id,
    )
    db.add(chat)

    resp = BookingResponse.model_validate(booking)
    resp.nanny = nanny_to_response(nanny)
    return resp


@router.get("", response_model=List[BookingResponse], summary="Мои записи")
async def my_bookings(
    status_filter: Optional[BookingStatus] = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = (
        select(Booking)
        .where(Booking.user_id == current_user.id)
        .order_by(Booking.date.desc())
    )
    if status_filter:
        query = query.where(Booking.status == status_filter)

    result = await db.execute(query)
    bookings = result.scalars().all()

    out = []
    for b in bookings:
        nanny_r = await db.execute(select(Nanny).where(Nanny.id == b.nanny_id))
        nanny = nanny_r.scalar_one()
        item = BookingResponse.model_validate(b)
        item.nanny = nanny_to_response(nanny)
        out.append(item)
    return out


@router.patch("/{booking_id}/status", response_model=BookingResponse, summary="Изменить статус")
async def update_status(
    booking_id: str,
    body: BookingStatusUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()
    if not booking:
        raise HTTPException(status_code=404, detail="Запись не найдена")

    # Только владелец или няня может менять статус
    if booking.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа")

    booking.status = body.status

    nanny_r = await db.execute(select(Nanny).where(Nanny.id == booking.nanny_id))
    nanny = nanny_r.scalar_one()
    resp = BookingResponse.model_validate(booking)
    resp.nanny = nanny_to_response(nanny)
    return resp


@router.post("/{booking_id}/review", response_model=ReviewResponse, summary="Оставить отзыв")
async def leave_review(
    booking_id: str,
    body: ReviewCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Booking).where(Booking.id == booking_id))
    booking = result.scalar_one_or_none()

    if not booking or booking.user_id != current_user.id:
        raise HTTPException(status_code=404, detail="Запись не найдена")
    if booking.status != BookingStatus.completed:
        raise HTTPException(status_code=400, detail="Можно оставить отзыв только после завершения")

    # Проверяем, нет ли уже отзыва
    existing = await db.execute(select(Review).where(Review.booking_id == booking_id))
    if existing.scalar_one_or_none():
        raise HTTPException(status_code=409, detail="Отзыв уже оставлен")

    review = Review(
        booking_id=booking.id,
        nanny_id=booking.nanny_id,
        user_id=current_user.id,
        rating=body.rating,
        text=body.text,
        child_age=body.child_age,
    )
    db.add(review)
    await db.flush()

    # Пересчитываем рейтинг няни
    reviews_result = await db.execute(
        select(Review).where(Review.nanny_id == booking.nanny_id)
    )
    all_reviews = reviews_result.scalars().all()
    nanny_result = await db.execute(select(Nanny).where(Nanny.id == booking.nanny_id))
    nanny = nanny_result.scalar_one()
    nanny.rating = round(sum(r.rating for r in all_reviews) / len(all_reviews), 2)
    nanny.review_count = len(all_reviews)

    return review
