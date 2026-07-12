"""Стикеры на кнопки.

Один пак (config.STICKER_SET), а соответствие «кнопка → номер стикера» — в
config.STICKER_MAP. Номера можно узнать командой /stickers (бот пришлёт все
стикеры пака с номерами). Загрузка пака кэшируется при первом успешном обращении.
"""

import logging
import time

from config import STICKER_COOLDOWN_SEC, STICKER_MAP, STICKER_SET

log = logging.getLogger("stickers")

_ids: list[str] = []
_last_sent: dict[int, float] = {}  # chat_id -> время последнего стикера (анти-спам)
_last_msg: dict[int, int] = {}     # chat_id -> message_id последнего стикера (для замены)


async def _load(bot) -> None:
    global _ids
    if _ids or not STICKER_SET:
        return
    try:
        ss = await bot.get_sticker_set(STICKER_SET)
        _ids = [s.file_id for s in ss.stickers]
        log.info("Стикеры: загружено %d из пака %r", len(_ids), STICKER_SET)
    except Exception as e:
        log.warning("Стикеры: не удалось загрузить пак %r: %s", STICKER_SET, e)


async def all_ids(bot) -> list[str]:
    await _load(bot)
    return _ids


def has(action: str) -> bool:
    """Есть ли стикер, привязанный к действию (для решения «слать или нет»)."""
    return bool(STICKER_SET) and bool(STICKER_MAP.get(action, 0))


async def send_for(bot, chat_id, action: str) -> bool:
    """Шлёт стикер по STICKER_MAP с анти-спам кулдауном. Возвращает True, если отправил."""
    if not STICKER_SET:
        return False
    idx = STICKER_MAP.get(action, 0)
    if not idx:
        return False  # на эту кнопку стикер не задан
    nowt = time.monotonic()
    if STICKER_COOLDOWN_SEC > 0 and nowt - _last_sent.get(chat_id, 0.0) < STICKER_COOLDOWN_SEC:
        return False  # ещё не прошёл кулдаун — молчим
    await _load(bot)
    i = idx - 1
    if not (0 <= i < len(_ids)):
        log.warning("Стикеры: для %r задан номер %d, но в паке только %d", action, idx, len(_ids))
        return False
    try:
        # удаляем предыдущий стикер этого чата — чтобы они не копились, а заменялись
        prev = _last_msg.get(chat_id)
        if prev:
            try:
                await bot.delete_message(chat_id, prev)
            except Exception:
                pass
        msg = await bot.send_sticker(chat_id, _ids[i])
        _last_msg[chat_id] = msg.message_id
        _last_sent[chat_id] = nowt
        return True
    except Exception as e:
        log.warning("Стикеры: не удалось отправить (%r): %s", action, e)
        return False
