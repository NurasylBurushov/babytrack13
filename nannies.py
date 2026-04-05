from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, and_, or_
from typing import Optional, List
import math
from database import get_db
from models import Nanny, Review, Favorite
from schemas import NannyResponse, NannyListResponse, ReviewCreate, ReviewResponse
from auth import get_current_user
from models import User

router = APIRouter(prefix="/nannies", tags=["Няни"])


def haversine(lat1, lon1, lat2, lon2) -> float:
    """Расстояние между двумя точками в км"""
    R = 6371
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def nanny_to_response(nanny: Nanny, user_lat=None, user_lng=None, favorites=None) -> NannyResponse:
    distance = None
    if user_lat and user_lng and nanny.latitude and nanny.longitude:
        distance = round(haversine(user_lat, user_lng, nanny.latitude, nanny.longitude), 1)

    data = NannyResponse.model_validate(nanny)
    data.distance_km = distance
    return data


@router.get("", response_model=NannyListResponse, summary="Список нянь с фильтрами")
async def list_nannies(
    city: Optional[str] = None,
    min_rating: Optional[float] = None,
    max_rate: Optional[int] = None,
    specialties: Optional[str] = Query(None, description="через запятую"),
    languages: Optional[str] = Query(None, description="через запятую"),
    is_verified: Optional[bool] = None,
    is_available: Optional[bool] = None,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    sort_by: str = "rating",
    page: int = 1,
    per_page: int = 20,
    db: AsyncSession = Depends(get_db),
):
    query = select(Nanny).where(Nanny.is_active == True)

    if city:
        query = query.where(Nanny.city.ilike(f"%{city}%"))
    if min_rating is not None:
        query = query.where(Nanny.rating >= min_rating)
    if max_rate is not None:
        query = query.where(Nanny.hourly_rate <= max_rate)
    if is_verified is not None:
        query = query.where(Nanny.is_verified == is_verified)
    if is_available is not None:
        query = query.where(Nanny.is_available == is_available)
    if specialties:
        for spec in specialties.split(","):
            query = query.where(Nanny.specialties.any(spec.strip()))
    if languages:
        for lang in languages.split(","):
            query = query.where(Nanny.languages.any(lang.strip()))

    # Сортировка
    if sort_by == "rating":
        query = query.order_by(Nanny.rating.desc())
    elif sort_by == "rate_asc":
        query = query.order_by(Nanny.hourly_rate.asc())
    elif sort_by == "rate_desc":
        query = query.order_by(Nanny.hourly_rate.desc())

    # Подсчёт всего
    count_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(count_q)).scalar()

    # Пагинация
    query = query.offset((page - 1) * per_page).limit(per_page)
    result = await db.execute(query)
    nannies = result.scalars().all()

    items = [nanny_to_response(n, lat, lng) for n in nannies]

    # Сортировка по расстоянию (после получения)
    if sort_by == "distance" and lat and lng:
        items.sort(key=lambda n: n.distance_km or 999)

    return NannyListResponse(nannies=items, total=total, page=page, per_page=per_page)


@router.get("/{nanny_id}", response_model=NannyResponse, summary="Профиль няни")
async def get_nanny(
    nanny_id: str,
    lat: Optional[float] = None,
    lng: Optional[float] = None,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Nanny).where(Nanny.id == nanny_id))
    nanny = result.scalar_one_or_none()
    if not nanny:
        raise HTTPException(status_code=404, detail="Няня не найдена")
    return nanny_to_response(nanny, lat, lng)


@router.get("/{nanny_id}/reviews", response_model=List[ReviewResponse], summary="Отзывы о няне")
async def get_reviews(nanny_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(Review)
        .where(Review.nanny_id == nanny_id)
        .order_by(Review.created_at.desc())
        .limit(50)
    )
    return result.scalars().all()


@router.post("/{nanny_id}/favorite", summary="Добавить/убрать из избранного")
async def toggle_favorite(
    nanny_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Favorite).where(
            Favorite.user_id == current_user.id,
            Favorite.nanny_id == nanny_id,
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        await db.delete(existing)
        return {"is_favorite": False, "nanny_id": nanny_id}
    else:
        fav = Favorite(user_id=current_user.id, nanny_id=nanny_id)
        db.add(fav)
        return {"is_favorite": True, "nanny_id": nanny_id}


@router.get("/me/favorites", response_model=List[NannyResponse], summary="Мои избранные")
async def my_favorites(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Nanny)
        .join(Favorite, Favorite.nanny_id == Nanny.id)
        .where(Favorite.user_id == current_user.id)
    )
    return [nanny_to_response(n) for n in result.scalars().all()]
