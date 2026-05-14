from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import NannyLocation
from auth import get_current_user
from models import User
from pydantic import BaseModel
from typing import Optional
import uuid

router = APIRouter(prefix="/tracking", tags=["Отслеживание"])


def _parse_nanny_uuid(nanny_id: str) -> uuid.UUID:
    try:
        return uuid.UUID(str(nanny_id).strip())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail="Некорректный id няни: ожидается UUID (например из профиля няни в API).",
        ) from None


class LocationUpdate(BaseModel):
    latitude: float
    longitude: float
    address: Optional[str] = None
    speed: Optional[float] = None
    battery: Optional[int] = None

@router.get("/{nanny_id}/location")
async def get_nanny_location(
    nanny_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(NannyLocation)
        .where(NannyLocation.nanny_id == _parse_nanny_uuid(nanny_id))
        .order_by(NannyLocation.created_at.desc())
    )
    loc = result.scalars().first()
    if not loc:
        raise HTTPException(404, detail="Местоположение не найдено")
    return {
        "latitude":  loc.latitude,
        "longitude": loc.longitude,
        "address":   loc.address,
        "speed":     loc.speed,
        "battery":   loc.battery,
        "timestamp": loc.created_at.isoformat() if loc.created_at else None,
    }

@router.post("/{nanny_id}/location")
async def update_location(
    nanny_id: str,
    body: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    loc = NannyLocation(
        nanny_id=_parse_nanny_uuid(nanny_id),
        latitude  = body.latitude,
        longitude = body.longitude,
        address   = body.address,
        speed     = body.speed,
        battery   = body.battery,
    )
    db.add(loc)
    await db.commit()
    return {"success": True}
