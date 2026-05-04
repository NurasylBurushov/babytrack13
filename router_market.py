from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import MarketItem, NannyLocation, Nanny
from auth import get_current_user
from models import User
from pydantic import BaseModel
from typing import Optional
import uuid

# ══════════════════════════════════════════════════════════
# MARKET
# ══════════════════════════════════════════════════════════
router = APIRouter(prefix="/market", tags=["Маркет"])

class MarketItemCreate(BaseModel):
    title: str
    description: Optional[str] = None
    price: int
    category: str
    condition: str = "used"
    image_url: Optional[str] = None

@router.get("/products")
async def get_products(
    category: Optional[str] = None,
    db: AsyncSession = Depends(get_db)
):
    query = select(MarketItem).where(MarketItem.is_active == True)
    if category:
        query = query.where(MarketItem.category == category)
    result = await db.execute(query.order_by(MarketItem.created_at.desc()))
    items = result.scalars().all()
    return [
        {
            "_id":         str(i.id),
            "title":       i.title,
            "description": i.description,
            "price":       i.price,
            "category":    i.category,
            "condition":   i.condition,
            "image":       i.image_url,
            "sellerId":    str(i.seller_id),
            "createdAt":   i.created_at.isoformat() if i.created_at else None,
        }
        for i in items
    ]

@router.post("/products")
async def create_product(
    body: MarketItemCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    item = MarketItem(
        seller_id   = current_user.id,
        title       = body.title,
        description = body.description,
        price       = body.price,
        category    = body.category,
        condition   = body.condition,
        image_url   = body.image_url,
    )
    db.add(item)
    await db.commit()
    await db.refresh(item)
    return {"_id": str(item.id), "title": item.title, "price": item.price}

@router.delete("/products/{item_id}")
async def delete_product(
    item_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(MarketItem).where(MarketItem.id == uuid.UUID(item_id)))
    item = result.scalar_one_or_none()
    if not item:
        raise HTTPException(404, detail="Товар не найден")
    if item.seller_id != current_user.id:
        raise HTTPException(403, detail="Нет доступа")
    item.is_active = False
    await db.commit()
    return {"success": True}


# ══════════════════════════════════════════════════════════
# TRACKING
# ══════════════════════════════════════════════════════════
tracking_router = APIRouter(prefix="/tracking", tags=["Отслеживание"])

class LocationUpdate(BaseModel):
    latitude: float
    longitude: float
    address: Optional[str] = None
    speed: Optional[float] = None
    battery: Optional[int] = None

@tracking_router.get("/{nanny_id}/location")
async def get_nanny_location(
    nanny_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(
        select(NannyLocation)
        .where(NannyLocation.nanny_id == uuid.UUID(nanny_id))
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

@tracking_router.post("/{nanny_id}/location")
async def update_nanny_location(
    nanny_id: str,
    body: LocationUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    loc = NannyLocation(
        nanny_id  = uuid.UUID(nanny_id),
        latitude  = body.latitude,
        longitude = body.longitude,
        address   = body.address,
        speed     = body.speed,
        battery   = body.battery,
    )
    db.add(loc)
    await db.commit()
    return {"success": True}
