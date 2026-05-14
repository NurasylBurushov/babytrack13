from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from auth import get_current_user
from config import get_settings
from models import User
from r2_storage import Purpose, presign_put

router = APIRouter(prefix="/uploads", tags=["Загрузки"])


class PresignRequest(BaseModel):
    purpose: Purpose = Field(description="user_avatar | nanny_avatar | market_product")
    content_type: str = Field(default="image/jpeg", description="image/jpeg, image/png, image/webp")


class PresignResponse(BaseModel):
    upload_url: str
    public_url: str
    key: str
    required_headers: dict[str, str]


@router.post("/presign", response_model=PresignResponse, summary="Presigned URL для загрузки в R2")
async def presign_upload(
    body: PresignRequest,
    auth_user: User = Depends(get_current_user),
):
    settings = get_settings()
    if not settings.r2_configured:
        raise HTTPException(
            status_code=503,
            detail="Хранилище R2 не настроено на сервере (переменные R2_* и R2_PUBLIC_BASE_URL).",
        )
    try:
        data = presign_put(
            purpose=body.purpose,
            user_id=str(auth_user.id),
            content_type=body.content_type,
        )
        return PresignResponse(**data)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
