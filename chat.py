"""
Раньше здесь была старая копия чата с параметром current_user (ломалось на /api/chats).
Все маршруты чата — только в router_chat.py. Этот файл оставлен как совместимый re-export.
"""
from router_chat import router

__all__ = ["router"]
