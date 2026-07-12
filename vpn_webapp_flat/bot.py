"""Точка входа: запуск бота, роутеры, фоновые задачи."""

import asyncio
import logging

import texts
from aiogram import Bot, Dispatcher
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.storage.memory import MemoryStorage

import db
import handlers_admin
import handlers_user
from config import (
    ADMIN_IDS,
    AUTORENEW_BEFORE_DAYS,
    BACKUP_EVERY_HOURS,
    BOT_TOKEN,
    CRYPTO_PAY_TOKEN,
    DB_PATH,
    LAVA_SECRET_KEY,
    LAVA_SHOP_ID,
    PAYMENT_MODE,
    PROVIDER_TOKEN,
    REDIS_URL,
    REMIND_BEFORE_DAYS,
    PREORDER_REFUND_HOURS,
    RESTOCK_BATCH,
    RESTOCK_THRESHOLD,
    WINBACK_AFTER_DAYS,
    TRIAL_REMINDER_AFTER_DAYS,
    DIGEST_EVERY_HOURS,
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from keyboards import flag, renew_kb
from middlewares import BanMiddleware, StickerMiddleware, ThrottlingMiddleware

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("vpn_bot")


async def background_worker(bot: Bot) -> None:
    while True:
        try:
            await db.release_stale_orders()

            # истёкшие подписки — уведомить пользователей (на их языке)
            for cfg in await db.expire_configs():
                try:
                    lang = await db.get_lang(cfg["user_id"])
                    rname = texts.region_name(cfg["region"], lang)
                    if lang == "en":
                        txt = (f"⌛️ Your subscription ({flag(cfg['region'])} {rname}) has expired.\n"
                               "Renew to keep your access 👇")
                    else:
                        txt = (f"⌛️ Подписка ({flag(cfg['region'])} {rname}) истекла.\n"
                               "Продли, чтобы не потерять доступ 👇")
                    await bot.send_message(cfg["user_id"], txt, reply_markup=renew_kb(cfg["id"], lang))
                except Exception:
                    pass

            # напоминания об окончании за N дней
            for cfg in await db.expiring_soon(REMIND_BEFORE_DAYS):
                try:
                    lang = await db.get_lang(cfg["user_id"])
                    rname = texts.region_name(cfg["region"], lang)
                    exp = (cfg["expires_at"] or "")[:10]
                    if lang == "en":
                        txt = (f"🔔 Your subscription ({flag(cfg['region'])} {rname}) "
                               f"expires soon — until {exp}.\nRenew now to stay connected 👇")
                    else:
                        txt = (f"🔔 Подписка ({flag(cfg['region'])} {rname}) скоро закончится "
                               f"— до {exp}.\nПродли заранее, чтобы не отключаться 👇")
                    await bot.send_message(cfg["user_id"], txt, reply_markup=renew_kb(cfg["id"], lang))
                    await db.mark_renew_notified(cfg["id"])
                except Exception:
                    pass

            # запасы серверов — уведомить админов
            for region, kind, free in await db.scan_stock_alerts():
                for admin_id in ADMIN_IDS:
                    try:
                        await bot.send_message(admin_id, texts.admin_stock_alert(region, kind, free))
                    except Exception:
                        pass

            # предзаказы: авто-выдача появившихся серверов
            for po in await db.waiting_preorders():
                try:
                    await handlers_user.deliver_preorder(bot, po)
                except Exception:
                    pass

            # предзаказы: авто-возврат, если сервер так и не появился
            for po in await db.preorders_to_refund(PREORDER_REFUND_HOURS):
                try:
                    await handlers_user.refund_preorder(bot, po)
                except Exception:
                    pass

            # автопродление: списываем с баланса за N дней до конца
            for cfg in await db.autorenew_candidates(AUTORENEW_BEFORE_DAYS):
                try:
                    await handlers_user.auto_renew(bot, cfg)
                except Exception:
                    pass

            # предупреждение о нехватке баланса до автопродления (раньше, чем спишем)
            for cfg in await db.lowbal_autopay_candidates(AUTORENEW_BEFORE_DAYS + 2):
                try:
                    await handlers_user.lowbal_warn(bot, cfg)
                except Exception:
                    pass

            # воронка возврата: разовый промокод ушедшим клиентам
            for cand in await db.winback_candidates(WINBACK_AFTER_DAYS):
                try:
                    await handlers_user.send_winback(bot, cand)
                except Exception:
                    pass

            # напоминание после триала: кто пробовал, но не купил
            for cand in await db.trial_reminder_candidates(TRIAL_REMINDER_AFTER_DAYS):
                try:
                    await handlers_user.send_trial_reminder(bot, cand)
                except Exception:
                    pass

            # склад: низкий запас → создать заявку на закупку и пингануть админов
            for r in await db.low_stock_regions(RESTOCK_THRESHOLD):
                try:
                    if await db.restock_open_for_region(r["region"]):
                        continue
                    urgent = r["has_preorder"] or r["free"] <= 4
                    rid = await db.create_restock(r["region"], RESTOCK_BATCH, urgent)
                    mark = "🔥 СРОЧНО" if urgent else "📦"
                    extra = "\n⚠️ Есть оплаченный предзаказ — клиент ждёт!" if r["has_preorder"] else ""
                    kb = InlineKeyboardBuilder()
                    kb.button(text="📦 Открыть заявку", callback_data=f"rs:open:{rid}")
                    for admin_id in ADMIN_IDS:
                        try:
                            await bot.send_message(
                                admin_id,
                                f"{mark} Низкий запас: <b>{r['region']}</b> "
                                f"(🟢 {r['free']} шт). Нужно докупить {RESTOCK_BATCH}.{extra}",
                                reply_markup=kb.as_markup())
                        except Exception:
                            pass
                except Exception:
                    pass
        except Exception as e:
            log.exception("background_worker error: %s", e)
        await asyncio.sleep(120)  # каждые 2 минуты (быстрее ловим предзаказы)


async def backup_worker(bot: Bot) -> None:
    """Раз в BACKUP_EVERY_HOURS часов шлёт копию базы админам в личку."""
    import os
    from aiogram.types import FSInputFile
    if BACKUP_EVERY_HOURS <= 0:
        return
    while True:
        await asyncio.sleep(BACKUP_EVERY_HOURS * 3600)
        try:
            if not os.path.exists(DB_PATH):
                continue
            from datetime import datetime
            stamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            doc = FSInputFile(DB_PATH, filename=f"vpn_bot_{stamp}.db")
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_document(admin_id, doc, caption=f"🗄 Бэкап базы · {stamp}")
                except Exception:
                    pass
        except Exception as e:
            log.exception("backup_worker error: %s", e)


async def digest_worker(bot: Bot) -> None:
    """Раз в DIGEST_EVERY_HOURS часов шлёт админам сводку за сутки."""
    if DIGEST_EVERY_HOURS <= 0:
        return
    while True:
        await asyncio.sleep(DIGEST_EVERY_HOURS * 3600)
        try:
            s = await db.digest_stats()
            text = texts.admin_digest(s)
            for admin_id in ADMIN_IDS:
                try:
                    await bot.send_message(admin_id, text)
                except Exception:
                    pass
        except Exception as e:
            log.exception("digest_worker error: %s", e)


async def _make_storage():
    """Redis-сторедж, если задан REDIS_URL и реально доступен, иначе память."""
    if REDIS_URL:
        try:
            from aiogram.fsm.storage.redis import RedisStorage
            storage = RedisStorage.from_url(REDIS_URL)
            await storage.redis.ping()  # реальная проверка соединения, а не просто создание объекта
            log.info("FSM storage: Redis (%s)", REDIS_URL)
            return storage
        except Exception as e:
            log.warning("REDIS_URL задан, но Redis недоступен (%s) — откат на MemoryStorage.", e)
    return MemoryStorage()


async def main() -> None:
    if not BOT_TOKEN:
        raise RuntimeError("BOT_TOKEN не задан — заполни файл .env")

    await db.init_db()

    import store
    await store.load_from_db()

    if PAYMENT_MODE == "yookassa" and not PROVIDER_TOKEN:
        log.warning("PAYMENT_MODE=yookassa, но PROVIDER_TOKEN пуст — оплата не пройдёт! "
                    "Заполни PROVIDER_TOKEN в .env.")
    if PAYMENT_MODE == "crypto" and not CRYPTO_PAY_TOKEN:
        log.warning("PAYMENT_MODE=crypto, но CRYPTO_PAY_TOKEN пуст — оплата не пройдёт! "
                    "Заполни CRYPTO_PAY_TOKEN в .env.")
    if PAYMENT_MODE == "lava" and not (LAVA_SHOP_ID and LAVA_SECRET_KEY):
        log.warning("PAYMENT_MODE=lava, но LAVA_SHOP_ID/LAVA_SECRET_KEY пусты — оплата не пройдёт! "
                    "Заполни их в .env.")

    bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(
        parse_mode=ParseMode.HTML, link_preview_is_disabled=True))
    try:
        from aiogram.types import (
            BotCommand, BotCommandScopeChat, BotCommandScopeDefault,
        )
        # Команды для всех пользователей (без /admin)
        user_cmds = [
            BotCommand(command="start", description="Запустить / Start"),
            BotCommand(command="menu", description="Главное меню / Menu"),
            BotCommand(command="help", description="Помощь / Help"),
        ]
        await bot.set_my_commands(user_cmds, scope=BotCommandScopeDefault())
        # Команды для админов (с /admin) — задаём персонально каждому
        admin_cmds = user_cmds + [
            BotCommand(command="admin", description="Панель управления (админ)"),
        ]
        for admin_id in ADMIN_IDS:
            try:
                await bot.set_my_commands(admin_cmds, scope=BotCommandScopeChat(chat_id=admin_id))
            except Exception:
                pass
    except Exception:
        pass

    dp = Dispatcher(storage=await _make_storage())

    # анти-спам и блокировка забаненных (внешние мидлвари — до фильтров роутеров)
    dp.message.outer_middleware(BanMiddleware())
    dp.callback_query.outer_middleware(BanMiddleware())
    dp.message.outer_middleware(ThrottlingMiddleware(rate=0.5))
    dp.callback_query.outer_middleware(ThrottlingMiddleware(rate=0.4))
    # Стикеры на инлайн-кнопки отключены: инлайн-экран меняется на месте, а стикер
    # приходил новым сообщением и «ронял» чат вниз. Стикеры остаются на нижней панели.

    # глобальный обработчик ошибок: безобидные шумные — молча, остальные — лог + админам
    _BENIGN = (
        "message is not modified",
        "query is too old",
        "message to edit not found",
        "message can't be deleted",
        "message to delete not found",
        "MESSAGE_ID_INVALID",
    )

    @dp.errors()
    async def on_error(event):
        msg = str(event.exception)
        if any(b in msg for b in _BENIGN):
            return True  # игнорируем — это нормальные гонки интерфейса
        log.exception("Update error: %s", event.exception)
        text = f"⚠️ <b>Ошибка в боте</b>\n<code>{type(event.exception).__name__}: {event.exception}</code>"
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text[:3500])
            except Exception:
                pass
        return True

    dp.include_router(handlers_admin.router)
    dp.include_router(handlers_user.router)

    asyncio.create_task(background_worker(bot))
    asyncio.create_task(backup_worker(bot))
    asyncio.create_task(digest_worker(bot))
    log.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
