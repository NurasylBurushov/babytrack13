from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List
from database import get_db
from models import User, Child
from schemas import UserResponse, UpdateUserRequest, ChildCreate, ChildResponse
from auth import get_current_user

router = APIRouter(prefix="/users", tags=["Пользователи"])


@router.get("/me", response_model=UserResponse, summary="Мой профиль")
async def get_me(current_user: User = Depends(get_current_user)):
    return current_user


@router.patch("/me", response_model=UserResponse, summary="Обновить профиль")
async def update_me(
    body: UpdateUserRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if body.name is not None:
        current_user.name = body.name
    if body.avatar_url is not None:
        current_user.avatar_url = body.avatar_url
    return current_user


@router.get("/me/children", response_model=List[ChildResponse], summary="Мои дети")
async def get_children(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(select(Child).where(Child.parent_id == current_user.id))
    return result.scalars().all()


@router.post("/me/children", response_model=ChildResponse, status_code=201, summary="Добавить ребёнка")
async def add_child(
    body: ChildCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    child = Child(parent_id=current_user.id, **body.model_dump())
    db.add(child)
    await db.flush()
    return child


@router.delete("/me/children/{child_id}", summary="Удалить ребёнка")
async def delete_child(
    child_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    result = await db.execute(
        select(Child).where(Child.id == child_id, Child.parent_id == current_user.id)
    )
    child = result.scalar_one_or_none()
    if not child:
        raise HTTPException(status_code=404, detail="Ребёнок не найден")
    await db.delete(child)
    return {"ok": True}
