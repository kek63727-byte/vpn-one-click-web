"""Фильтр: только администраторы."""

from aiogram.filters import BaseFilter

from config import ADMIN_IDS


class IsAdmin(BaseFilter):
    async def __call__(self, event) -> bool:
        user = getattr(event, "from_user", None)
        return bool(user and user.id in ADMIN_IDS)
