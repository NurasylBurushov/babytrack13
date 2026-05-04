from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from database import get_db
from models import User, Child
from auth import get_current_user
from pydantic import BaseModel
from typing import Optional
import uuid

router = APIRouter(prefix="/users", tags=["Пользователи"])

class UpdateUserRequest(BaseModel):
    name: Optional[str] = None
    avatar: Optional[str] = None

class ChildCreate(BaseModel):
    name: str
    birth_date: Optional[str] = None
    notes: Optional[str] = None

def user_to_dict(user: User) -> dict:
    return {
        "_id":       str(user.id),
        "name":      user.name or "",
        "email":     user.email,
        "phone":     user.phone,
        "avatar":    user.avatar,
        "role":      user.role or "parent",
        "createdAt": user.created_at.isoformat() if user.created_at else None,
    }

@router.get("/me")
async def get_profile(current_user: User = Depends(get_current_user)):
    return user_to_dict(current_user)

@router.patch("/me")
async def update_profile(
    body: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if body.name:   current_user.name   = body.name
    if body.avatar: current_user.avatar = body.avatar
    await db.commit()
    await db.refresh(current_user)
    return user_to_dict(current_user)

@router.get("/me/children")
async def get_children(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Child).where(Child.parent_id == current_user.id))
    children = result.scalars().all()
    return [{"_id": str(c.id), "name": c.name, "notes": c.notes} for c in children]

@router.post("/me/children")
async def add_child(
    body: ChildCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    child = Child(parent_id=current_user.id, name=body.name, notes=body.notes)
    db.add(child)
    await db.commit()
    await db.refresh(child)
    return {"_id": str(child.id), "name": child.name}
