from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update
from typing import List, Dict
from database import get_db
from models import Chat, Message, MessageType, User
from schemas import MessageCreate, MessageResponse, ChatResponse
from auth import get_current_user, decode_token
from routers.nannies import nanny_to_response
from models import Nanny
import json
from datetime import datetime

router = APIRouter(prefix="/chats", tags=["Чат"])


# ── WebSocket Connection Manager ──────────────────────────
class ConnectionManager:
    def __init__(self):
        # chat_id → список подключённых WebSocket-ов
        self.active: Dict[str, List[WebSocket]] = {}

    async def connect(self, chat_id: str, ws: WebSocket):
        await ws.accept()
        self.active.setdefault(chat_id, []).append(ws)

    def disconnect(self, chat_id: str, ws: WebSocket):
        if chat_id in self.active:
            self.active[chat_id].discard(ws) if hasattr(self.active[chat_id], 'discard') \
                else (self.active[chat_id].remove(ws) if ws in self.active[chat_id] else None)

    async def broadcast(self, chat_id: str, data: dict):
        for ws in self.active.get(chat_id, []):
            try:
                await ws.send_json(data)
            except Exception:
                pass


manager = ConnectionManager()


# ── REST эндпоинты ────────────────────────────────────────
@router.get("", response_model=List[ChatResponse], summary="Мои чаты")
async def my_chats(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ✅ ПРОВЕРКА АВТОРИЗАЦИИ
    if not current_user:
        raise HTTPException(status_code=401, detail="Требуется авторизаци��")
    
    result = await db.execute(
        select(Chat)
        .where(Chat.user_id == current_user.id)
        .order_by(Chat.created_at.desc())
    )
    chats = result.scalars().all()

    out = []
    for chat in chats:
        # Последнее сообщение
        msg_r = await db.execute(
            select(Message)
            .where(Message.chat_id == chat.id)
            .order_by(Message.created_at.desc())
            .limit(1)
        )
        last_msg = msg_r.scalar_one_or_none()

        # Непрочитанные
        unread_r = await db.execute(
            select(Message).where(
                Message.chat_id == chat.id,
                Message.sender_id != current_user.id,
                Message.is_read == False,
            )
        )
        unread = len(unread_r.scalars().all())

        nanny_r = await db.execute(select(Nanny).where(Nanny.id == chat.nanny_id))
        nanny = nanny_r.scalar_one()

        out.append(ChatResponse(
            id=chat.id,
            booking_id=chat.booking_id,
            nanny=nanny_to_response(nanny),
            last_message=last_msg.text if last_msg else None,
            unread_count=unread,
            created_at=chat.created_at,
        ))
    return out


@router.get("/{chat_id}/messages", response_model=List[MessageResponse], summary="История сообщений")
async def get_messages(
    chat_id: str,
    limit: int = 50,
    before_id: str = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    # ✅ ПРОВЕРКА АВТОРИЗАЦИИ
    if not current_user:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    
    # Проверяем доступ к чату
    chat_r = await db.execute(select(Chat).where(Chat.id == chat_id))
    chat = chat_r.scalar_one_or_none()
    if not chat or chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к чату")

    query = select(Message).where(Message.chat_id == chat_id)
    if before_id:
        anchor_r = await db.execute(select(Message).where(Message.id == before_id))
        anchor = anchor_r.scalar_one_or_none()
        if anchor:
            query = query.where(Message.created_at < anchor.created_at)

    query = query.order_by(Message.created_at.desc()).limit(limit)
    result = await db.execute(query)
    messages = result.scalars().all()

    # Отмечаем как прочитанные
    await db.execute(
        update(Message)
        .where(
            Message.chat_id == chat_id,
            Message.sender_id != current_user.id,
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
    current_user: User = Depends(get_current_user),
):
    # ✅ ПРОВЕРКА АВТОРИЗАЦИИ
    if not current_user:
        raise HTTPException(status_code=401, detail="Требуется авторизация")
    
    chat_r = await db.execute(select(Chat).where(Chat.id == chat_id))
    chat = chat_r.scalar_one_or_none()
    if not chat or chat.user_id != current_user.id:
        raise HTTPException(status_code=403, detail="Нет доступа к чату")

    msg = Message(
        chat_id=chat_id,
        sender_id=current_user.id,
        type=body.type,
        text=body.text,
    )
    db.add(msg)
    await db.flush()
    await db.commit()

    # Рассылаем по WebSocket
    await manager.broadcast(chat_id, {
        "id": str(msg.id),
        "sender_id": str(msg.sender_id),
        "text": msg.text,
        "type": msg.type.value,
        "created_at": msg.created_at.isoformat() if msg.created_at else datetime.utcnow().isoformat(),
    })

    return msg


# ── WebSocket ─────────────────────────────────────────────
@router.websocket("/{chat_id}/ws")
async def websocket_chat(
    chat_id: str,
    ws: WebSocket,
    token: str = Query(...),
    db: AsyncSession = Depends(get_db),
):
    """
    Подключение: wss://yourserver.com/chats/{chat_id}/ws?token=JWT
    Входящий JSON: {"text": "Привет!", "type": "text"}
    Исходящий JSON: {"id": "...", "sender_id": "...", "text": "...", "created_at": "..."}
    """
    # ✅ ПРОВЕРКА ТОКЕНА
    if not token:
        await ws.close(code=4001, reason="Требуется токен")
        return
    
    user_id = decode_token(token)
    if not user_id:
        await ws.close(code=4001, reason="Некорректный токен")
        return

    user_r = await db.execute(select(User).where(User.id == user_id))
    user = user_r.scalar_one_or_none()
    if not user:
        await ws.close(code=4001, reason="Пользователь не найден")
        return

    await manager.connect(chat_id, ws)
    try:
        while True:
            raw = await ws.receive_text()
            data = json.loads(raw)
            text = data.get("text", "").strip()
            if not text:
                continue

            msg = Message(
                chat_id=chat_id,
                sender_id=user.id,
                type=MessageType.text,
                text=text,
            )
            db.add(msg)
            await db.flush()
            await db.commit()

            await manager.broadcast(chat_id, {
                "id": str(msg.id),
                "sender_id": str(user.id),
                "text": msg.text,
                "type": "text",
                "created_at": datetime.utcnow().isoformat(),
            })

    except WebSocketDisconnect:
        manager.disconnect(chat_id, ws)
    except Exception as e:
        print(f"WebSocket error: {e}")
        manager.disconnect(chat_id, ws)
