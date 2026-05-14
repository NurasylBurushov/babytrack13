"""
Устаревшая копия чата (была с current_user и дублем логики).
Используйте только router_chat — он подключён в main.py.
"""
from router_chat import ROUTER_CHAT_SIGNATURE, router

__all__ = ["router", "ROUTER_CHAT_SIGNATURE"]
