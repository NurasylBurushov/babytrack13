"""Реализация API чата. Вынесено из router_chat.py, чтобы новый деплой гарантированно подтягивал файл."""
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, or_
from typing import List, Dict
from database import get_db
from models import Chat, Message, MessageType, User
from schemas import MessageCreate, MessageResponse, ChatResponse
from auth import get_current_user, decode_token
from router_nannies import nanny_to_response
from models import Nanny
import json
from datetime import datetime
from uuid import UUID

router = APIRouter(prefix="/chats", tags=["Чат"])

# /health и логи; после деплоя должен быть именно этот маркер.
ROUTER_CHAT_SIGNATURE = "chat_api_module_v3"


# ── WebSocket Connection Manager ──────────────────────────
class ConnectionManager:
    def __init__(self):
        self.active: Dict[str, List[WebSocket]] = {}

    async def connect(self, chat_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(chat_id, []).append(ws)

    def disconnect(self, chat_id: str, ws: WebSocket):
        if chat_id in self.active:
            self.active[chat_id].discard(ws) if hasattr(self.active[chat_id], "discard") else (
                self.active[chat_id].remove(ws) if ws in self.active[chat_id] else None
            )

    async def broadcast(self, chat_id: str, data: dict):
        for ws in self.active.get(chat_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                pass


manager = ConnectionManager()


async def _nanny_for_user(db: AsyncSession, user: User) -> Nanny | None:
    r = await db.execute(select(Nanny).where(Nanny.user_id == user.id))
    return r.scalar_one_or_none()


async def assert_chat_participant(db: AsyncSession, chat: Chat, user: User) -> None:
    """Родитель по брони или привязанная к аккаунту няня."""
    if chat.user_id == user.id:
        return
    nanny = await _nanny_for_user(db, user)
    if nanny and chat.nanny_id == nanny.id:
        return
    raise HTTPException(status_code=403, detail="Нет доступа к чату")


# ── REST эндпоинты ────────────────────────────────────────
@router.get("", response_model=List[ChatResponse], summary="Мои чаты")
async def my_chats(
    db: AsyncSession = Depends(get_db),
    auth_user: User = Depends(get_current_user),
):
    # Не называть параметр current_user — query ?current_user= ломает Depends в FastAPI.
    parent_nanny = await _nanny_for_user(db, auth_user)
    cond = [Chat.user_id == auth_user.id]
    if parent_nanny:
        cond.append(Chat.nanny_id == parent_nanny.id)
    result = await db.execute(
        select(Chat)
        .where(or_(*cond))
        .order_by(Chat.created_at.desc())
    )
    chats = result.scalars().all()

    out = []
    for chat in chats:
        msg_r = await db.execute(
            select(Message)
            .where(Message.chat_id == chat.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_msg = msg_r.scalar_one_or_none()

        unread_r = await db.execute(
            select(Message).where(
                Message.chat_id == chat.id,
                Message.sender_id != auth_user.id,
                Message.is_read == False,
            )
        )
        unread = len(unread_r.scalars().all())

        nanny_r = await db.execute(select(Nanny).where(Nanny.id == chat.nanny_id))
        chat_nanny = nanny_r.scalar_one_or_none()
        if chat_nanny:
            out.append(
                ChatResponse(
                    id=chat.id,
                    booking_id=chat.booking_id,
                    nanny=nanny_to_response(chat_nanny),
                    last_message=last_msg.text if last_msg else None,
                    unread_count=unread,
                    created_at=chat.created_at,
                )
            )
    return out


@router.get("/{chat_id}/messages", response_model=List[MessageResponse], summary="История сообщений")
async def get_messages(
    chat_id: str,
    limit: int = 50,
    before_id: str = None,
    db: AsyncSession = Depends(get_db),
    auth_user: User = Depends(get_current_user),
):
    try:
        chat_uuid = UUID(str(chat_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный id чата")

    chat_r = await db.execute(select(Chat).where(Chat.id == chat_uuid))
    chat = chat_r.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    await assert_chat_participant(db, chat, auth_user)

    query = select(Message).where(Message.chat_id == chat_uuid)
    if before_id:
        try:
            before_uuid = UUID(str(before_id))
        except ValueError:
            raise HTTPException(status_code=400, detail="Некорректный before_id")
        anchor_r = await db.execute(select(Message).where(Message.id == before_uuid))
        anchor = anchor_r.scalar_one_or_none()
        if anchor:
            query = query.where(Message.created_at < anchor.created_at)

    query = query.order_by(Message.created_at.desc()).limit(limit)
    result = await db.execute(query)
    messages = result.scalars().all()

    await db.execute(
        update(Message)
        .where(
            Message.chat_id == chat_uuid,
            Message.sender_id != auth_user.id,
        )
        .values(is_read=True)
    )
    await db.commit()

    return list(reversed(messages))


@router.post("/{chat_id}/messages", response_model=MessageResponse, summary="Отправить сообщение")
async def send_message(
    chat_id: str,
    body: MessageCreate,
    db: AsyncSession = Depends(get_db),
    auth_user: User = Depends(get_current_user),
):
    try:
        chat_uuid = UUID(str(chat_id))
    except ValueError:
        raise HTTPException(status_code=400, detail="Некорректный id чата")

    chat_r = await db.execute(select(Chat).where(Chat.id == chat_uuid))
    chat = chat_r.scalar_one_or_none()
    if not chat:
        raise HTTPException(status_code=404, detail="Чат не найден")
    await assert_chat_participant(db, chat, auth_user)

    msg = Message(
        chat_id=chat_uuid,
        sender_id=auth_user.id,
        type=body.type,
        text=body.text,
    )
    db.add(msg)
    await db.flush()
    await db.commit()

    await manager.broadcast(str(chat_id), {
        "id": str(msg.id),
        "sender_id": str(msg.sender_id),
        "text": msg.text,
        "type": msg.type.value,
        "created_at": msg.created_at.isoformat() if msg.created_at else datetime.utcnow().isoformat(),
    })

    return msg


@router.websocket("/{chat_id}/ws")
async def websocket_chat(
    chat_id: str,
    ws: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Подключение: wss://host/api/chats/{chat_id}/ws?token=JWT
    Входящий JSON: {"text": "Привет!", "type": "text"}
    Исходящий JSON: {"id": "...", "sender_id": "...", "text": "...", "created_at": "..."}
    """
    if not token:
        await ws.close(code=4001)
        return

    user_id_str = decode_token(token)
    if not user_id_str:
        await ws.close(code=4001)
        return

    try:
        user_uuid = UUID(str(user_id_str))
    except ValueError:
        await ws.close(code=4001)
        return

    user_r = await db.execute(select(User).where(User.id == user_uuid))
    user = user_r.scalar_one_or_none()
    if not user:
        await ws.close(code=4001)
        return

    try:
        chat_uuid = UUID(str(chat_id))
    except ValueError:
        await ws.close(code=4004)
        return

    chat_r = await db.execute(select(Chat).where(Chat.id == chat_uuid))
    chat = chat_r.scalar_one_or_none()
    if not chat:
        await ws.close(code=4004)
        return
    try:
        await assert_chat_participant(db, chat, user)
    except HTTPException:
        await ws.close(code=4003)
        return

    await manager.connect(str(chat_id), ws)
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            text = data.get("text", "").strip()
            if not text:
                continue

            msg = Message(
                chat_id=chat_uuid,
                sender_id=user.id,
                type=MessageType.text,
                text=text,
            )
            db.add(msg)
            await db.flush()
            await db.commit()

            await manager.broadcast(str(chat_id), {
                "id": str(msg.id),
                "sender_id": str(user.id),
                "text": msg.text,
                "type": "text",
                "created_at": datetime.utcnow().isoformat(),
            })

    except WebSocketDisconnect:
        manager.disconnect(str(chat_id), ws)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(str(chat_id), ws)
