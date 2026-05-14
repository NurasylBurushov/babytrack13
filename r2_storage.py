"""Presigned PUT в Cloudflare R2 (S3-совместимый API)."""
from __future__ import annotations

import uuid
from typing import Literal

import boto3
from botocore.client import Config

from config import get_settings

Purpose = Literal["user_avatar", "nanny_avatar", "market_product"]

_CT_EXT = {
    "image/jpeg": "jpg",
    "image/jpg": "jpg",
    "image/png": "png",
    "image/webp": "webp",
}


def _s3_client():
    s = get_settings()
    if not s.r2_configured:
        raise RuntimeError("R2 is not configured")
    return boto3.client(
        "s3",
        endpoint_url=s.R2_ENDPOINT,
        aws_access_key_id=s.R2_ACCESS_KEY,
        aws_secret_access_key=s.R2_SECRET_KEY,
        config=Config(signature_version="s3v4", s3={"addressing_style": "path"}),
        region_name="auto",
    )


def build_object_key(purpose: Purpose, user_id: str, content_type: str) -> str:
    ct = content_type.split(";")[0].strip().lower()
    ext = _CT_EXT.get(ct)
    if not ext:
        raise ValueError(f"Unsupported content type: {content_type}")
    uid = uuid.uuid4().hex
    if purpose == "user_avatar":
        return f"avatars/{user_id}/{uid}.{ext}"
    if purpose == "nanny_avatar":
        return f"nannies/{user_id}/{uid}.{ext}"
    return f"market/{user_id}/{uid}.{ext}"


def public_url_for_key(key: str) -> str:
    s = get_settings()
    base = (s.R2_PUBLIC_BASE_URL or "").rstrip("/")
    if not base:
        raise RuntimeError("R2_PUBLIC_BASE_URL is not set (публичный URL для чтения фото)")
    return f"{base}/{key}"


def presign_put(*, purpose: Purpose, user_id: str, content_type: str) -> dict:
    """
    Возвращает URL для PUT загрузки и публичный URL после загрузки.
    Клиент обязан отправить заголовок Content-Type ровно как в required_headers.
    """
    s = get_settings()
    if not s.r2_configured:
        raise RuntimeError("R2 is not configured")

    ct = content_type.split(";")[0].strip().lower()
    if ct not in _CT_EXT:
        raise ValueError("Допустимы только image/jpeg, image/png, image/webp")

    key = build_object_key(purpose, user_id, ct)
    client = _s3_client()

    url = client.generate_presigned_url(
        ClientMethod="put_object",
        Params={
            "Bucket": s.R2_BUCKET,
            "Key": key,
            "ContentType": ct,
        },
        ExpiresIn=900,
        HttpMethod="PUT",
    )

    return {
        "upload_url": url,
        "public_url": public_url_for_key(key),
        "key": key,
        "required_headers": {"Content-Type": ct},
    }
