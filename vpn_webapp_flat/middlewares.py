"""Мидлвари: блокировка забаненных пользователей и анти-спам (throttling)."""

import time
from collections import defaultdict

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message

import db
import stickers
from config import ADMIN_IDS


class BanMiddleware(BaseMiddleware):
    """Молча игнорирует апдейты от забаненных пользователей (кроме админов)."""

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None) or data.get("event_from_user")
        if user and user.id not in ADMIN_IDS:
            try:
                if await db.is_banned(user.id):
                    if isinstance(event, CallbackQuery):
                        try:
                            await event.answer("⛔️ Доступ ограничен.", show_alert=True)
                        except Exception:
                            pass
                    return  # не пропускаем дальше
            except Exception:
                pass
        return await handler(event, data)


class ThrottlingMiddleware(BaseMiddleware):
    """Простой анти-спам: не чаще 1 действия в `rate` секунд на пользователя."""

    def __init__(self, rate: float = 0.5):
        self.rate = rate
        self._last: dict[int, float] = defaultdict(float)
        super().__init__()

    async def __call__(self, handler, event, data):
        user = getattr(event, "from_user", None) or data.get("event_from_user")
        if user and user.id not in ADMIN_IDS:
            now = time.monotonic()
            if now - self._last[user.id] < self.rate:
                if isinstance(event, CallbackQuery):
                    try:
                        await event.answer()  # гасим "часики", без спама алертами
                    except Exception:
                        pass
                return
            self._last[user.id] = now
        return await handler(event, data)


class StickerMiddleware(BaseMiddleware):
    """Шлёт стикер при нажатии инлайн-кнопок, у которых задан стикер в STICKER_MAP."""

    async def __call__(self, handler, event, data):
        result = await handler(event, data)
        try:
            if isinstance(event, CallbackQuery) and event.data and event.message:
                bot = data.get("bot")
                if bot is not None:
                    await stickers.send_for(bot, event.message.chat.id, event.data)
        except Exception:
            pass
        return result
