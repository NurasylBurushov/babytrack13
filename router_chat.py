"""Совместимость: вся логика чата в chat_api.py (импортируйте оттуда в main)."""
from chat_api import ROUTER_CHAT_SIGNATURE, router

__all__ = ["router", "ROUTER_CHAT_SIGNATURE"]
