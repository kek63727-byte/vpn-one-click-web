"""Хендлеры пользователя (RU/EN): язык, меню, покупка, триал, рефералка, оплата."""

import logging

import texts
from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject, CommandStart, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message, PreCheckoutQuery, ReplyKeyboardRemove
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db
import ab
import stickers
from config import (
    ADMIN_IDS, DEVICE_TITLE, PAYMENT_MODE, PERIOD_TITLE, PERIOD_DAYS, PLANS, REF_PERCENT,
    REF_REWARD_DAYS, SALES_LOG_CHAT_ID, TRIAL_DAYS, LOYALTY_TIERS,
    REF_MILESTONES, REF_MIN_PAYOUT, FREEZE_PRICE, FREEZE_DAYS, FREEZE_COOLDOWN_DAYS,
    WINBACK_PROMO_PERCENT, WINBACK_PROMO_DAYS, SUPPORT_USERNAME,
    PRIME_ENABLED, PRIME_PLAN, PRIME_DEVICES, PRIME_PERIOD,
    STICKER_SET, CAPTCHA_ENABLED, BONUS_CHANNEL_ID, CHANNEL_BONUS_DAYS,
    TRIAL_REMINDER_PROMO_PERCENT, TRIAL_REMINDER_PROMO_DAYS, SWITCH_DISCOUNT_PERCENT,
)
from keyboards import (
    back_to_menu_kb, balance_kb, captcha_kb, chanbonus_kb, connection_kb, devices_kb, flag,
    gift_amounts_kb, guide_back_kb, howto_kb, language_kb, locations_kb, main_menu_kb, periods_kb,
    plans_kb, prime_buy_kb, prime_locations_kb, profile_kb, referral_kb, renew_kb, replace_country_kb,
    replace_reasons_kb, reply_menu_kb, REPLY_LABELS, support_kb, sub_activate_kb,
    sub_activate_locations_kb, sub_buy_kb, topup_amounts_kb,
    topup_methods_kb, trial_locations_kb,
)
from payments import (
    check_crypto_invoice, check_lava_invoice, create_crypto_invoice,
    create_lava_invoice, get_usd_rub_rate, invoice_params, loyalty_percent_for, price_rub,
    topup_bonus_for,
)
from utils import make_qr_png
from config import TOPUP_PRESETS

router = Router()
log = logging.getLogger(__name__)


class PromoUser(StatesGroup):
    waiting = State()


class TopupCustom(StatesGroup):
    waiting = State()


class Ticket(StatesGroup):
    waiting = State()


def _tt(lang, ru, en):
    return en if lang == "en" else ru


async def _lang(user_id) -> str:
    return await db.get_lang(user_id)


async def _ensure_admin_commands(bot: Bot, admin_id: int):
    """Проставляет команду /admin персонально админу (на случай, если он
    впервые открыл бота уже после запуска процесса)."""
    try:
        from aiogram.types import BotCommand, BotCommandScopeChat
        cmds = [
            BotCommand(command="start", description="Запустить / Start"),
            BotCommand(command="menu", description="Главное меню / Menu"),
            BotCommand(command="help", description="Помощь / Help"),
            BotCommand(command="admin", description="Панель управления (админ)"),
        ]
        await bot.set_my_commands(cmds, scope=BotCommandScopeChat(chat_id=admin_id))
    except Exception:
        pass


async def _rate(lang) -> float | None:
    """Курс USD только для английской версии (для показа цен в $)."""
    if lang == "en":
        try:
            return await get_usd_rub_rate()
        except Exception:
            return None
    return None


async def _loyalty_pct(user_id) -> int:
    spent = await db.total_spent(user_id)
    return loyalty_percent_for(spent)


def _next_tier(spent: int):
    """Следующий невыполненный уровень лояльности (порог, %) или None."""
    for threshold, percent in LOYALTY_TIERS:
        if spent < threshold:
            return (threshold, percent)
    return None


async def _resolve_discount(user_id, full, promo_code, promo_percent, floor_percent=0):
    """Скидка для заказа. Лояльность/промо/переключение НЕ суммируются — берём бОльшую.
    floor_percent — минимальная скидка (например, 15% за переключение тарифа).
    Возвращает (disc_rub, promo_code_to_consume, eff_percent)."""
    loy = await _loyalty_pct(user_id)
    base = max(loy, floor_percent or 0)
    if promo_percent and promo_percent >= base:
        return full * promo_percent // 100, promo_code, promo_percent
    return full * base // 100, None, base


def _switch_floor(data: dict, plan: str) -> int:
    """15% за переключение, если выбран тариф, отличный от активного."""
    return SWITCH_DISCOUNT_PERCENT if data and data.get("switch_plan") == plan else 0


async def _consume_promo(code, user_id):
    if not code:
        return
    await db.use_promo(code)
    await db.record_promo_redemption(code, user_id)


async def _notify_admins(bot: Bot, text: str, reply_markup=None):
    """Шлёт уведомление всем админам + в лог-канал (если задан в .env)."""
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=reply_markup)
        except Exception:
            pass
    if SALES_LOG_CHAT_ID:
        try:
            await bot.send_message(SALES_LOG_CHAT_ID, text, reply_markup=reply_markup)
        except Exception:
            pass


async def _admin_preorder_alert(bot: Bot, user_id, region, plan, devices, period, rub, po_id=None):
    """Собирает карточку клиента (имя, @username, баланс, время) и шлёт админам
    вместе с кнопками управления (написать / выдать / отменить / бан)."""
    from datetime import datetime
    u = await db.get_user(user_id) or {}
    bal = await db.get_balance(user_id)
    when = datetime.now().strftime("%d.%m %H:%M")
    text = texts.admin_preorder_alert(
        region, plan, devices, period, rub, user_id,
        username=u.get("username"), full_name=u.get("full_name"),
        balance=bal, when=when,
    )
    kb = InlineKeyboardBuilder()
    if po_id is not None:
        kb.button(text="🚚 Выдать", callback_data=f"apo:deliver:{po_id}")
        kb.button(text="❌ Отменить (возврат)", callback_data=f"apo:cancel:{po_id}")
    kb.button(text="✉️ Написать", callback_data=f"amsg:{user_id}")
    kb.button(text="👤 Карточка", callback_data=f"acard:{user_id}")
    kb.button(text="⛔️ Бан", callback_data=f"au:ban:{user_id}")
    kb.adjust(2, 2, 1)
    await _notify_admins(bot, text, reply_markup=kb.as_markup())


# ============ СТАРТ / ЯЗЫК / МЕНЮ ============

@router.message(CommandStart())
async def cmd_start(message: Message, command: CommandObject, bot: Bot):
    is_new = await db.add_user(
        message.from_user.id, message.from_user.username, message.from_user.full_name
    )
    # A/B: фиксируем вариант за пользователем (только если эксперимент включён)
    exp = ab.active_experiment()
    if exp:
        try:
            await db.set_user_ab(message.from_user.id, exp, ab.variant_for(message.from_user.id))
        except Exception:
            pass
    # Если это админ — гарантируем, что у него в меню есть /admin
    if message.from_user.id in ADMIN_IDS:
        await _ensure_admin_commands(bot, message.from_user.id)
    args = command.args or ""
    if is_new and args.startswith("ref_"):
        try:
            await db.set_referrer(message.from_user.id, int(args[4:]))
        except ValueError:
            pass
    # Капча (анти-бот): непроверенным не-админам показываем проверку перед входом
    if (CAPTCHA_ENABLED and message.from_user.id not in ADMIN_IDS
            and not await db.is_verified(message.from_user.id)):
        target, opts = _make_captcha()
        await message.answer(texts.captcha_q(target), reply_markup=captcha_kb(target, opts))
        return
    if is_new:
        await message.answer(texts.choose_language(), reply_markup=language_kb())
    else:
        lang = await _lang(message.from_user.id)
        await message.answer(texts.welcome(lang), reply_markup=main_menu_kb(lang))
        await _ensure_reply_menu(message, lang)


_CAPTCHA_EMOJIS = ["🐶", "🐱", "🦊", "🐰", "🐼", "🐨", "🦁", "🐸", "🐵", "🦄"]


def _make_captcha():
    import random
    opts = random.sample(_CAPTCHA_EMOJIS, 4)
    target = random.choice(opts)
    return target, opts


@router.callback_query(F.data == "capno")
async def cb_captcha_wrong(call: CallbackQuery):
    target, opts = _make_captcha()
    try:
        await call.message.edit_text(texts.captcha_wrong(), reply_markup=captcha_kb(target, opts))
    except Exception:
        pass
    await call.answer("❌")


@router.callback_query(F.data == "capok")
async def cb_captcha_ok(call: CallbackQuery, bot: Bot):
    await db.set_verified(call.from_user.id)
    try:
        await call.message.delete()
    except Exception:
        pass
    await call.message.answer(texts.choose_language(), reply_markup=language_kb())
    await call.answer("✅")


async def _ensure_reply_menu(message: Message, lang: str):
    """Показывает постоянную нижнюю клавиатуру (быстрое меню над полем ввода)."""
    try:
        await message.answer(_tt(lang, "📌 Быстрое меню снизу 👇", "📌 Quick menu below 👇"),
                             reply_markup=reply_menu_kb(lang))
    except Exception:
        pass


# текст кнопки нижнего меню → действие (RU и EN)
_REPLY_TEXT2KEY = {}
for _k, (_ru, _en) in REPLY_LABELS.items():
    _REPLY_TEXT2KEY[_ru] = _k
    _REPLY_TEXT2KEY[_en] = _k


# кэш file_id стикеров — в модуле stickers.py


@router.message(StateFilter(None), F.text.in_(set(_REPLY_TEXT2KEY)))
async def reply_menu_router(message: Message, bot: Bot):
    """Обрабатывает нажатия нижней (reply) клавиатуры — только когда нет активного ввода."""
    lang = await _lang(message.from_user.id)
    key = _REPLY_TEXT2KEY.get(message.text)
    if key == "hide":
        await message.answer(
            _tt(lang, "Меню скрыто. Открыть снова — /menu или кнопкой ⌨️ справа.",
                "Menu hidden. Reopen with /menu or the ⌨️ icon."),
            reply_markup=ReplyKeyboardRemove())
        return
    await stickers.send_for(bot, message.chat.id, key)
    rate = await _rate(lang)
    uid = message.from_user.id
    if key == "buy":
        await message.answer(_tt(lang, "🛒 <b>Выбери тариф:</b>", "🛒 <b>Choose a plan:</b>"),
                             reply_markup=plans_kb(lang, rate))
    elif key == "my":
        await _show_my(message, uid, lang)
    elif key == "profile":
        u = await db.user_card(uid)
        if u:
            pct = loyalty_percent_for(u.get("spent", 0))
            nxt = _next_tier(u.get("spent", 0))
            await message.answer(texts.profile(u, pct, nxt, lang, rate),
                                 reply_markup=profile_kb(bool(u.get("autopay")), lang))
    elif key == "prime":
        if PRIME_ENABLED:
            price = price_rub(PRIME_PLAN, PRIME_DEVICES, PRIME_PERIOD)
            await message.answer(texts.prime_card(price, PRIME_DEVICES, PRIME_PERIOD, lang, rate),
                                 reply_markup=prime_buy_kb(texts.money(price, lang, rate),
                                                           PRIME_PLAN, PRIME_DEVICES, PRIME_PERIOD, lang))
    elif key == "support":
        await message.answer(texts.support(lang), reply_markup=support_kb(lang))
    elif key == "menu":
        await message.answer(texts.welcome(lang), reply_markup=main_menu_kb(lang))


@router.message(Command("stickertest"))
async def cmd_stickertest(message: Message, bot: Bot):
    """Диагностика стикеров + показывает твой ID и статус админа (для настройки ADMIN_IDS)."""
    uid = message.from_user.id
    is_admin = uid in ADMIN_IDS
    head = (f"🆔 Твой ID: <code>{uid}</code>\n"
            f"👮 Админ: {'да ✅' if is_admin else 'нет ❌ — впиши этот ID в ADMIN_IDS в .env и перезапусти'}\n"
            f"🎟 STICKER_SET: <code>{STICKER_SET or '(пусто)'}</code>")
    await message.answer(head)
    if not STICKER_SET:
        await message.answer("⚠️ STICKER_SET пуст — добавь <code>STICKER_SET=Scream</code> в .env и перезапусти.")
        return
    try:
        ss = await bot.get_sticker_set(STICKER_SET)
        await message.answer(f"✅ Пак <b>{STICKER_SET}</b>: стикеров {len(ss.stickers)}. Отправляю первый…")
        await bot.send_sticker(message.chat.id, ss.stickers[0].file_id)
    except Exception as e:
        await message.answer(f"❌ Не удалось получить пак <b>{STICKER_SET}</b>:\n<code>{e}</code>\n\n"
                             "Проверь, что имя пака верное (часть после t.me/addstickers/).")


@router.message(Command("stickers"))
async def cmd_stickers(message: Message, bot: Bot):
    """Показывает все стикеры пака с номерами — чтобы настроить STICKER_MAP (только админ)."""
    if message.from_user.id not in ADMIN_IDS:
        return
    ids = await stickers.all_ids(bot)
    if not ids:
        await message.answer("Пак не загружен. Проверь STICKER_SET в .env и перезапусти бота.")
        return
    await message.answer(f"🎟 В паке <b>{len(ids)}</b> стикеров. Номер под каждым — это значение "
                         f"для STICKER_MAP в config.py:")
    for i, fid in enumerate(ids[:60], 1):
        try:
            await bot.send_sticker(message.chat.id, fid)
            await message.answer(f"№{i}")
        except Exception:
            pass


@router.message(Command("menu"))
async def cmd_menu_command(message: Message):
    await db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    lang = await _lang(message.from_user.id)
    await message.answer(texts.welcome(lang), reply_markup=main_menu_kb(lang))
    await _ensure_reply_menu(message, lang)


@router.message(Command("help"))
async def cmd_help_command(message: Message):
    await db.add_user(message.from_user.id, message.from_user.username, message.from_user.full_name)
    lang = await _lang(message.from_user.id)
    await message.answer(texts.support(lang), reply_markup=back_to_menu_kb(lang))


@router.callback_query(F.data == "lang")
async def cb_lang(call: CallbackQuery):
    await call.message.edit_text(texts.choose_language(), reply_markup=language_kb())
    await call.answer()


@router.callback_query(F.data.startswith("setlang:"))
async def cb_setlang(call: CallbackQuery):
    lang = call.data.split(":", 1)[1]
    await db.set_lang(call.from_user.id, lang)
    lang = await _lang(call.from_user.id)
    await call.message.edit_text(texts.welcome(lang), reply_markup=main_menu_kb(lang))
    await _ensure_reply_menu(call.message, lang)
    await call.answer("✅ English" if lang == "en" else "✅ Русский")


async def _edit(call: CallbackQuery, text, kb):
    # Если на эту кнопку реально ушёл стикер — присылаем экран новым сообщением ВНИЗУ
    # (под стикером), старое удаляем. Если стикера нет (кулдаун/не задан) — меняем на месте.
    sent = False
    if stickers.has(call.data):
        try:
            sent = await stickers.send_for(call.bot, call.message.chat.id, call.data)
        except Exception:
            sent = False
    if sent:
        try:
            await call.message.delete()
        except Exception:
            pass
        await call.message.answer(text, reply_markup=kb, disable_web_page_preview=True)
        return
    try:
        await call.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    except Exception:
        await call.message.answer(text, reply_markup=kb, disable_web_page_preview=True)


@router.callback_query(F.data == "menu")
async def cb_menu(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    await _edit(call, texts.welcome(lang), main_menu_kb(lang))
    await call.answer()


@router.callback_query(F.data == "about")
async def cb_about(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    await _edit(call, texts.about(lang), back_to_menu_kb(lang))
    await call.answer()


@router.callback_query(F.data == "support")
async def cb_support(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    await _edit(call, texts.support(lang), support_kb(lang))
    await call.answer()


@router.callback_query(F.data == "rules")
async def cb_rules(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    await _edit(call, texts.rules(lang), back_to_menu_kb(lang))
    await call.answer()


# ============ ОБРАЩЕНИЕ В ПОДДЕРЖКУ (тикет) ============

@router.callback_query(F.data == "ticket")
async def cb_ticket_start(call: CallbackQuery, state: FSMContext):
    lang = await _lang(call.from_user.id)
    await state.set_state(Ticket.waiting)
    await call.message.answer(texts.support_ticket_ask(lang))
    await call.answer()


@router.message(Ticket.waiting, Command("cancel"))
async def cb_ticket_cancel(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    await state.clear()
    await message.answer(_tt(lang, "Отменено.", "Cancelled."), reply_markup=back_to_menu_kb(lang))


@router.message(Ticket.waiting, F.text)
async def cb_ticket_send(message: Message, state: FSMContext, bot: Bot):
    lang = await _lang(message.from_user.id)
    await state.clear()
    u = await db.get_user(message.from_user.id) or {}
    kb = InlineKeyboardBuilder()
    kb.button(text="✉️ Ответить", callback_data=f"amsg:{message.from_user.id}")
    kb.button(text="👤 Карточка", callback_data=f"acard:{message.from_user.id}")
    kb.adjust(2)
    await _notify_admins(bot, texts.admin_ticket(
        message.from_user.id, message.text[:3500],
        username=u.get("username"), full_name=u.get("full_name")),
        reply_markup=kb.as_markup())
    await message.answer(texts.support_ticket_sent(lang), reply_markup=back_to_menu_kb(lang))


# ============ PRIME-ПОДПИСКА ============

@router.callback_query(F.data == "prime")
async def cb_prime(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    if not PRIME_ENABLED:
        await call.answer()
        return
    price = price_rub(PRIME_PLAN, PRIME_DEVICES, PRIME_PERIOD)
    await _edit(call, texts.prime_card(price, PRIME_DEVICES, PRIME_PERIOD, lang, rate),
                prime_buy_kb(texts.money(price, lang, rate),
                             PRIME_PLAN, PRIME_DEVICES, PRIME_PERIOD, lang))
    await call.answer()


@router.callback_query(F.data.startswith("primeloc:"))
async def cb_prime_loc(call: CallbackQuery, bot: Bot, state: FSMContext):
    # Prime = покупка ultimate / 5 устройств / год: переиспользуем обычный поток покупки
    region = call.data.split(":", 1)[1]
    await _buyloc(call, bot, state, PRIME_PLAN, PRIME_DEVICES, PRIME_PERIOD, region)


@router.callback_query(F.data == "primeauto")
async def cb_prime_auto(call: CallbackQuery, bot: Bot, state: FSMContext):
    """Авто-подбор локации: где сразу хватает на бандл, иначе с максимальным запасом."""
    regions = await db.regions_for_purchase()
    if not regions:
        await call.answer("Локации недоступны", show_alert=True)
        return
    ready = [r for r in regions if r[2] >= PRIME_DEVICES]
    pool = ready if ready else regions
    best = max(pool, key=lambda r: r[2])  # больше всего свободных
    await _buyloc(call, bot, state, PRIME_PLAN, PRIME_DEVICES, PRIME_PERIOD, best[0])


# ============ АКТИВАЦИЯ УСТРОЙСТВ (слот-подписка) ============

@router.callback_query(F.data.startswith("subact:"))
async def cb_subact(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    sub_id = int(call.data.split(":")[1])
    sub = await db.get_subscription(sub_id)
    if not sub or sub["user_id"] != call.from_user.id:
        await call.answer(_tt(lang, "Подписка не найдена.", "Subscription not found."), show_alert=True)
        return
    subs = await db.user_subscriptions(call.from_user.id)
    s = next((x for x in subs if x["id"] == sub_id), None)
    if not s or s["free_slots"] <= 0:
        await call.answer(_tt(lang, "Все устройства уже активированы.", "All devices already activated."), show_alert=True)
        return
    regions = await db.regions_for_purchase()
    avail = [r for r in regions if r[2] >= 1]
    if not avail:
        await call.answer(_tt(lang, "Сейчас нет свободных серверов. Загляни чуть позже.",
                              "No free servers right now. Check back later."), show_alert=True)
        return
    await _edit(call, texts.sub_activate_pick(s, lang), sub_activate_locations_kb(sub_id, avail, lang))
    await call.answer()


@router.callback_query(F.data.startswith("subactloc:"))
async def cb_subactloc(call: CallbackQuery, bot: Bot):
    lang = await _lang(call.from_user.id)
    _, sub_id, region = call.data.split(":", 2)
    cfg = await db.activate_slot(int(sub_id), region, call.from_user.id)
    if not cfg:
        await call.answer(_tt(lang, "Не удалось — нет места или сервера. Выбери другую страну.",
                              "Couldn't activate — no slot or server. Try another country."), show_alert=True)
        return
    await call.answer("✅")
    await call.message.answer(texts.sub_activated(texts.region_name(region, lang), lang))
    from datetime import datetime
    try:
        exp_dt = datetime.fromisoformat((cfg.get("expires_at") or "").replace("Z", ""))
    except Exception:
        exp_dt = datetime.utcnow()
    await _send_config(call.message, cfg, exp_dt, 1, 1, lang)
    await call.message.answer(_tt(lang, "📖 Как подключить — выбери платформу:",
                                  "📖 How to connect — choose a platform:"), reply_markup=howto_kb(lang))


# ============ FAQ ============

@router.callback_query(F.data == "faq")
async def cb_faq(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    await _edit(call, texts.faq(lang), back_to_menu_kb(lang))
    await call.answer()


# ============ ПРОФИЛЬ / ЛОЯЛЬНОСТЬ / АВТОПРОДЛЕНИЕ ============

@router.callback_query(F.data == "profile")
async def cb_profile(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    u = await db.user_card(call.from_user.id)
    if not u:
        await call.answer()
        return
    pct = loyalty_percent_for(u.get("spent", 0))
    nxt = _next_tier(u.get("spent", 0))
    await _edit(call, texts.profile(u, pct, nxt, lang, rate), profile_kb(bool(u.get("autopay")), lang))
    await call.answer()


@router.callback_query(F.data.startswith("autopay:"))
async def cb_autopay(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    on = call.data.split(":", 1)[1] == "on"
    await db.set_autopay(call.from_user.id, on)
    await call.answer(_tt(lang, "Готово", "Done"))
    msg = texts.autopay_on(lang) if on else texts.autopay_off(lang)
    await call.message.answer(msg)
    u = await db.user_card(call.from_user.id)
    pct = loyalty_percent_for(u.get("spent", 0))
    nxt = _next_tier(u.get("spent", 0))
    await _edit(call, texts.profile(u, pct, nxt, lang, rate), profile_kb(on, lang))


# ============ ПОДАРОЧНЫЕ КОДЫ ============

@router.callback_query(F.data == "gift")
async def cb_gift(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    await _edit(call, texts.gift_intro(lang), gift_amounts_kb(TOPUP_PRESETS, lang, rate))
    await call.answer()


@router.callback_query(F.data.startswith("giftamt:"))
async def cb_gift_amount(call: CallbackQuery):
    import secrets
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    amount = int(call.data.split(":", 1)[1])
    bal = await db.get_balance(call.from_user.id)
    if bal < amount:
        await call.answer()
        await _edit(call, texts.need_topup(texts.money(amount, lang, rate),
                                           texts.money(bal, lang, rate), lang), balance_kb(lang))
        return
    if not await db.deduct_balance(call.from_user.id, amount):
        await call.answer(_tt(lang, "Недостаточно средств.", "Not enough balance."), show_alert=True)
        return
    # уникальный код
    code = None
    for _ in range(5):
        candidate = "GIFT" + secrets.token_hex(3).upper()
        if await db.get_promo(candidate) is None:
            code = candidate
            break
    if code is None:
        await db.add_balance(call.from_user.id, amount)  # вернуть, если не смогли
        await call.answer(_tt(lang, "Не удалось создать код, попробуй ещё раз.",
                              "Couldn't create the code, try again."), show_alert=True)
        return
    await db.create_gift_code(code, amount, created_by=call.from_user.id)
    new_bal = await db.get_balance(call.from_user.id)
    await call.answer()
    await _edit(call, texts.gift_created(code, texts.money(amount, lang, rate),
                                         texts.money(new_bal, lang, rate), lang), balance_kb(lang))


# ============ РЕФЕРАЛКА ============

@router.callback_query(F.data == "ref")
async def cb_ref(call: CallbackQuery, bot: Bot):
    lang = await _lang(call.from_user.id)
    me = await bot.me()
    link = f"https://t.me/{me.username}?start=ref_{call.from_user.id}"
    st = await db.referral_stats(call.from_user.id)
    await _edit(call, texts.referral(link, st, lang), referral_kb(lang))
    await call.answer()


# ============ ИСТОРИЯ ПЛАТЕЖЕЙ ============

@router.callback_query(F.data == "history")
async def cb_history(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    items = await db.pay_history(call.from_user.id)
    await _edit(call, texts.pay_history(items, lang, rate), back_to_menu_kb(lang))
    await call.answer()


# ============ ВЫВОД РЕФЕРАЛЬНОГО ЗАРАБОТКА ============

@router.callback_query(F.data == "refwd")
async def cb_ref_withdraw(call: CallbackQuery, bot: Bot):
    lang = await _lang(call.from_user.id)
    cash = await db.get_ref_cash(call.from_user.id)
    if cash < REF_MIN_PAYOUT:
        await _edit(call, texts.payout_min_not_reached(cash, lang), referral_kb(lang))
        await call.answer()
        return
    if await db.has_pending_payout(call.from_user.id):
        await _edit(call, texts.payout_pending_already(lang), referral_kb(lang))
        await call.answer()
        return
    pid = await db.create_payout(call.from_user.id, cash)
    if not pid:
        await call.answer(_tt(lang, "Не удалось создать заявку.", "Could not create request."), show_alert=True)
        return
    await _edit(call, texts.payout_created(cash, lang), back_to_menu_kb(lang))
    await call.answer()
    # уведомляем админов с кнопками «выплачено / отклонить»
    u = await db.get_user(call.from_user.id) or {}
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Выплачено", callback_data=f"apay:done:{pid}")
    kb.button(text="❌ Отклонить", callback_data=f"apay:rej:{pid}")
    kb.button(text="✉️ Написать", callback_data=f"amsg:{call.from_user.id}")
    kb.adjust(2, 1)
    await _notify_admins(bot, texts.admin_payout_alert(
        pid, call.from_user.id, cash,
        username=u.get("username"), full_name=u.get("full_name")),
        reply_markup=kb.as_markup())


# ============ ЗАМОРОЗКА ПОДПИСКИ ============

@router.callback_query(F.data.startswith("frz:"))
async def cb_freeze_ask(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    cid = int(call.data.split(":")[1])
    cfg = await db.get_config(cid)
    if not cfg or cfg.get("user_id") != call.from_user.id:
        await call.answer(_tt(lang, "Подписка не найдена.", "Subscription not found."), show_alert=True)
        return
    bal = await db.get_balance(call.from_user.id)
    region = texts.region_name(cfg["region"], lang)
    kb = InlineKeyboardBuilder()
    kb.button(text=_tt(lang, f"⏸ Заморозить за {FREEZE_PRICE} ₽", f"⏸ Pause for {FREEZE_PRICE} ₽"),
              callback_data=f"frzok:{cid}")
    kb.button(text=_tt(lang, "⬅️ Назад", "⬅️ Back"), callback_data="my")
    kb.adjust(1)
    await _edit(call, texts.freeze_offer(region, texts.money(bal, lang, rate), lang), kb.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("frzok:"))
async def cb_freeze_do(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    cid = int(call.data.split(":")[1])
    cfg = await db.get_config(cid)
    if not cfg or cfg.get("user_id") != call.from_user.id:
        await call.answer(_tt(lang, "Подписка не найдена.", "Subscription not found."), show_alert=True)
        return
    # лимит: не чаще одной заморозки в FREEZE_COOLDOWN_DAYS дней
    ok, nxt = await db.can_freeze(cid, FREEZE_COOLDOWN_DAYS)
    if not ok:
        until = (nxt or "")[:10]
        await _edit(call, texts.freeze_cooldown(until, lang), back_to_menu_kb(lang))
        await call.answer()
        return
    bal = await db.get_balance(call.from_user.id)
    if bal < FREEZE_PRICE:
        await _edit(call, texts.freeze_need_balance(
            texts.money(FREEZE_PRICE, lang, rate), texts.money(bal, lang, rate), lang),
            balance_kb(lang))
        await call.answer()
        return
    if not await db.deduct_balance(call.from_user.id, FREEZE_PRICE):
        await call.answer(_tt(lang, "Недостаточно средств.", "Not enough balance."), show_alert=True)
        return
    new_exp = await db.extend_config(cid, FREEZE_DAYS)
    await db.mark_frozen(cid)
    region = texts.region_name(cfg["region"], lang)
    await _edit(call, texts.freeze_done(region, new_exp.strftime("%d.%m.%Y"), lang),
                back_to_menu_kb(lang))
    await call.answer(_tt(lang, "Готово ⏸", "Done ⏸"))


# ============ ФОНОВЫЕ: предупреждение о балансе и возврат ушедших ============

async def lowbal_warn(bot: Bot, cfg: dict):
    """Предупреждает о нехватке баланса перед автопродлением (один раз на подписку)."""
    user_id = cfg["user_id"]
    plan = cfg["plan"] or "standard"
    period = cfg["period"] if cfg["period"] in ("month", "year") else "month"
    full = price_rub(plan, 1, period)
    loy = loyalty_percent_for(await db.total_spent(user_id))
    to_pay = full - full * loy // 100
    bal = await db.get_balance(user_id)
    if bal >= to_pay:
        return  # хватает — не дёргаем
    await db.mark_lowbal_notified(cfg["id"])
    lang = await db.get_lang(user_id)
    rate = await _rate(lang)
    try:
        await bot.send_message(
            user_id,
            texts.autopay_low_warn(texts.region_name(cfg["region"], lang),
                                   texts.money(to_pay, lang, rate),
                                   texts.money(bal, lang, rate), lang),
            reply_markup=balance_kb(lang))
    except Exception:
        pass


async def send_winback(bot: Bot, cand: dict):
    """Шлёт ушедшему клиенту разовый промокод на скидку и помечает, что уже слали."""
    import random
    import string
    user_id = cand["user_id"]
    await db.mark_winback(cand["id"])
    code = "BACK" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    try:
        await db.create_promo(code, "discount", percent=WINBACK_PROMO_PERCENT, max_uses=1)
        lang = await db.get_lang(user_id)
        await bot.send_message(user_id, texts.winback_msg(
            texts.region_name(cand["region"], lang), code, lang))
    except Exception:
        pass


async def send_trial_reminder(bot: Bot, cand: dict):
    """Кто попробовал триал, но не купил — личный промокод-скидка через N дней."""
    import random
    import string
    user_id = cand["user_id"]
    await db.mark_trial_reminded(user_id)
    code = "TRY" + "".join(random.choices(string.ascii_uppercase + string.digits, k=6))
    try:
        await db.create_promo(code, "discount", percent=TRIAL_REMINDER_PROMO_PERCENT, max_uses=1)
        lang = cand.get("lang") or await db.get_lang(user_id)
        kb = InlineKeyboardBuilder()
        kb.button(text=_tt(lang, "🌐 Купить подписку", "🌐 Buy subscription"), callback_data="buy")
        await bot.send_message(user_id, texts.trial_reminder_msg(
            code, TRIAL_REMINDER_PROMO_PERCENT, TRIAL_REMINDER_PROMO_DAYS, lang),
            reply_markup=kb.as_markup())
    except Exception:
        pass


def _bonus_channel_ref():
    """BONUS_CHANNEL_ID может быть @username или числовой -100... — приводим к нужному типу."""
    cid = (BONUS_CHANNEL_ID or "").strip()
    if not cid:
        return None
    if cid.lstrip("-").isdigit():
        return int(cid)
    return cid if cid.startswith("@") else "@" + cid


@router.callback_query(F.data == "chanbonus")
async def cb_chanbonus(call: CallbackQuery, bot: Bot):
    lang = await _lang(call.from_user.id)
    ref = _bonus_channel_ref()
    if not ref:
        await call.answer(_tt(lang, "Бонус временно недоступен.", "Bonus is unavailable."), show_alert=True)
        return
    if await db.channel_bonus_claimed(call.from_user.id):
        await _edit(call, texts.chanbonus_already(lang), back_to_menu_kb(lang))
        await call.answer()
        return
    # проверяем подписку
    try:
        member = await bot.get_chat_member(ref, call.from_user.id)
        subscribed = member.status in ("member", "administrator", "creator")
    except Exception:
        subscribed = False
    if not subscribed:
        await _edit(call, texts.chanbonus_need_sub(CHANNEL_BONUS_DAYS, "новостной канал", lang),
                    chanbonus_kb(lang))
        await call.answer(_tt(lang, "Подписку пока не вижу.", "Subscription not found yet."))
        return
    applied, region = await db.extend_active(call.from_user.id, CHANNEL_BONUS_DAYS)
    if not applied:
        await _edit(call, texts.chanbonus_no_active(lang), back_to_menu_kb(lang))
        await call.answer()
        return
    await db.set_channel_bonus_claimed(call.from_user.id)
    rname = texts.region_name(region, lang) if region else ""
    await _edit(call, texts.chanbonus_ok(CHANNEL_BONUS_DAYS, rname, lang), back_to_menu_kb(lang))
    await call.answer("✅")


# ============ ПРОБНЫЙ ПЕРИОД ============

@router.callback_query(F.data == "trial")
async def cb_trial(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    user = await db.get_user(call.from_user.id)
    if user and user["trial_used"]:
        await _edit(call, texts.trial_used(lang), plans_kb(lang, rate))
        await call.answer()
        return
    regions = await db.trial_regions()
    if regions:
        await _edit(call, texts.trial_intro(lang), trial_locations_kb(regions, lang))
        await call.answer()
        return
    applied, region = await db.extend_active(call.from_user.id, TRIAL_DAYS)
    if applied:
        await db.mark_trial_used(call.from_user.id)
        await _edit(call, texts.trial_busy_bonus(texts.region_name(region, lang), TRIAL_DAYS, lang), back_to_menu_kb(lang))
    else:
        await _edit(call, texts.trial_busy(lang), plans_kb(lang, rate))
    await call.answer()


@router.callback_query(F.data.startswith("trialloc:"))
async def cb_trialloc(call: CallbackQuery, bot: Bot):
    lang = await _lang(call.from_user.id)
    region = call.data.split(":", 1)[1]
    user = await db.get_user(call.from_user.id)
    if user and user["trial_used"]:
        await call.answer(_tt(lang, "Пробный период уже использован.", "Trial already used."), show_alert=True)
        return
    reserved = await db.reserve_trial(region, call.from_user.id)
    if not reserved:
        await call.answer(_tt(lang, "😔 Сервер закончился, выбери другой.", "😔 Out of stock, pick another."), show_alert=True)
        return
    await call.answer()
    await db.mark_trial_used(call.from_user.id)
    cfg = reserved[0]
    expires = await db.mark_sold(cfg["id"], call.from_user.id, "standard", "trial")
    # A/B: вариант может удлинять триал (extra_days к базовым TRIAL_DAYS)
    extra = int(ab.variant_params(call.from_user.id).get("extra_days", 0) or 0)
    if extra > 0:
        expires = await db.extend_config(cfg["id"], extra)
    await call.message.answer(_tt(lang, "🎁 <b>Пробный доступ активирован!</b>", "🎁 <b>Trial access activated!</b>"))
    full = await db.get_config(cfg["id"])
    await _send_config(call.message, full, expires, 1, 1, lang)
    await call.message.answer(_tt(lang, "📖 Как подключить — выбери платформу:", "📖 How to connect — choose a platform:"), reply_markup=howto_kb(lang))
    # уведомляем админов: кто и где взял пробный доступ
    from datetime import datetime
    u = await db.get_user(call.from_user.id) or {}
    await _notify_admins(bot, texts.admin_trial_alert(
        region, call.from_user.id,
        username=u.get("username"), full_name=u.get("full_name"),
        when=datetime.now().strftime("%d.%m %H:%M"),
    ))


# ============ БАЛАНС ============

@router.callback_query(F.data == "balance")
async def cb_balance(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    bal = await db.get_balance(call.from_user.id)
    await _edit(call, texts.balance_screen(bal, lang, rate), balance_kb(lang))
    await call.answer()


@router.callback_query(F.data == "topup")
async def cb_topup(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    await _edit(call, texts.topup_intro(lang), topup_amounts_kb(TOPUP_PRESETS, lang, rate))
    await call.answer()


@router.callback_query(F.data == "topupcustom")
async def cb_topup_custom(call: CallbackQuery, state: FSMContext):
    lang = await _lang(call.from_user.id)
    await state.set_state(TopupCustom.waiting)
    await call.message.answer(texts.topup_custom_ask(lang))
    await call.answer()


@router.message(TopupCustom.waiting, Command("cancel"))
async def cb_topup_custom_cancel(message: Message, state: FSMContext):
    await state.clear()
    lang = await _lang(message.from_user.id)
    await message.answer(_tt(lang, "Отменено.", "Cancelled."), reply_markup=back_to_menu_kb(lang))


@router.message(TopupCustom.waiting, F.text)
async def cb_topup_custom_amount(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    raw = message.text.strip().replace(",", ".")
    try:
        amount = int(float(raw))
    except ValueError:
        await message.answer(_tt(lang, "Введи число, например 250.", "Enter a number, e.g. 250."))
        return
    if amount < 50:
        await message.answer(_tt(lang, "Минимум 50 ₽.", "Minimum 50 ₽."))
        return
    await state.clear()
    await message.answer(
        _tt(lang, f"Сумма пополнения: <b>{amount} ₽</b>\nВыбери способ оплаты:",
            f"Top-up amount: <b>{amount} ₽</b>\nChoose a payment method:"),
        reply_markup=topup_methods_kb(amount, lang),
    )


@router.callback_query(F.data.startswith("topupamt:"))
async def cb_topup_amount(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    amount = int(call.data.split(":", 1)[1])
    await _edit(call,
                _tt(lang, f"Сумма пополнения: <b>{amount} ₽</b>\nВыбери способ оплаты:",
                    f"Top-up amount: <b>{amount} ₽</b>\nChoose a payment method:"),
                topup_methods_kb(amount, lang))
    await call.answer()


@router.callback_query(F.data.startswith("tmethod:"))
async def cb_topup_method(call: CallbackQuery, bot: Bot):
    lang = await _lang(call.from_user.id)
    _, method, amount = call.data.split(":")
    amount = int(amount)
    topup_id = await db.create_topup(call.from_user.id, amount, method)
    await call.answer()
    await _topup_invoice(call.message, bot, call.from_user.id, topup_id, amount, method, lang)


async def _topup_invoice(target, bot, user_id, topup_id, amount, method, lang):
    title = _tt(lang, f"Пополнение баланса {amount} ₽", f"Balance top-up {amount} ₽")
    err = _tt(lang, "⚠️ Не удалось создать счёт. Попробуй другой способ или напиши в поддержку.",
              "⚠️ Couldn't create the invoice. Try another method or contact support.")
    paid_btn = _tt(lang, "✅ Я оплатил — проверить", "✅ I paid — check")

    if method in ("lava", "sbp", "card"):
        try:
            _iid, pay_url = await create_lava_invoice(topup_id, amount, title)
        except Exception as e:
            log.exception("lava topup error: %s", e)
            await target.answer(err)
            return
        label = _tt(lang, "⚡️ Оплатить через СБП", "⚡️ Pay via SBP") if method == "sbp" \
            else _tt(lang, "💳 Оплатить картой", "💳 Pay by card")
        kb = InlineKeyboardBuilder()
        kb.button(text=label, url=pay_url)
        kb.button(text=paid_btn, callback_data=f"checktl:{topup_id}")
        kb.adjust(1)
        await target.answer(f"💳 <b>{title}</b>\n{texts.LINE}\n" +
                            _tt(lang, "Оплати и нажми «Проверить».", "Pay and tap «Check»."),
                            reply_markup=kb.as_markup())
        return

    if method == "crypto":
        try:
            invoice_id, pay_url = await create_crypto_invoice(topup_id, amount, title)
        except Exception as e:
            log.exception("crypto topup error: %s", e)
            await target.answer(err)
            return
        if not pay_url:
            await target.answer(err)
            return
        kb = InlineKeyboardBuilder()
        kb.button(text=_tt(lang, "🪙 Оплатить криптой", "🪙 Pay with crypto"), url=pay_url)
        kb.button(text=paid_btn, callback_data=f"checktc:{invoice_id}:{topup_id}")
        kb.adjust(1)
        await target.answer(f"🪙 <b>{title}</b>\n{texts.LINE}\n" +
                            _tt(lang, "Оплати в @CryptoBot и нажми «Проверить».",
                                "Pay in @CryptoBot and tap «Check»."),
                            reply_markup=kb.as_markup())
        return


def _resume_kb(lang="ru"):
    kb = InlineKeyboardBuilder()
    kb.button(text=_tt(lang, "✅ Завершить заказ", "✅ Complete order"), callback_data="resume")
    kb.button(text=_tt(lang, "⬅️ В главное меню", "⬅️ Main menu"), callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


async def _credit_topup(target, bot, user_id, topup_id, method_name, ref, lang, state=None):
    topup = await db.get_topup(topup_id)
    if not topup or topup["status"] == "paid":
        return False
    await db.set_topup_paid(topup_id)
    await db.add_balance(user_id, topup["amount_rub"])
    # бонус за пополнение
    bonus, pct = topup_bonus_for(topup["amount_rub"])
    if bonus > 0:
        await db.add_balance(user_id, bonus)
    await db.record_payment(user_id, 0, topup["amount_rub"], method_name, str(ref))
    rate = await _rate(lang)
    bal = await db.get_balance(user_id)
    # если был отложенный заказ (держим сервер) — предложим его завершить
    pending = (await state.get_data()).get("pending") if state else None
    kb = _resume_kb(lang) if pending else balance_kb(lang)
    await target.answer(texts.topup_paid(texts.money(topup["amount_rub"], lang, rate),
                                          texts.money(bal, lang, rate), lang),
                        reply_markup=kb)
    if bonus > 0:
        await target.answer(texts.topup_bonus_note(
            texts.money(bonus, lang, rate), pct, lang))
    # реф-кэшбэк при реальном пополнении
    await _reward_referrer(user_id, topup["amount_rub"], bot)
    await _sales_log_topup(bot, user_id, topup)
    return True


@router.callback_query(F.data.startswith("checktl:"))
async def check_topup_lava(call: CallbackQuery, bot: Bot, state: FSMContext):
    lang = await _lang(call.from_user.id)
    topup_id = int(call.data.split(":", 1)[1])
    try:
        paid = await check_lava_invoice(topup_id)
    except Exception as e:
        log.exception("lava topup check error: %s", e)
        await call.answer(_tt(lang, "Не удалось проверить, попробуй ещё раз.", "Check failed, try again."), show_alert=True)
        return
    if not paid:
        await call.answer(_tt(lang, "Оплата пока не найдена. Подожди минуту.", "Payment not found yet. Wait a minute."), show_alert=True)
        return
    ok = await _credit_topup(call.message, bot, call.from_user.id, topup_id, "LAVA", topup_id, lang, state)
    await call.answer(_tt(lang, "Готово ✅", "Done ✅") if ok else _tt(lang, "Уже зачислено ✅", "Already credited ✅"), show_alert=True)


@router.callback_query(F.data.startswith("checktc:"))
async def check_topup_crypto(call: CallbackQuery, bot: Bot, state: FSMContext):
    lang = await _lang(call.from_user.id)
    _, invoice_id, topup_id = call.data.split(":")
    try:
        paid = await check_crypto_invoice(int(invoice_id))
    except Exception as e:
        log.exception("crypto topup check error: %s", e)
        await call.answer(_tt(lang, "Не удалось проверить, попробуй ещё раз.", "Check failed, try again."), show_alert=True)
        return
    if not paid:
        await call.answer(_tt(lang, "Оплата пока не найдена. Подожди минуту.", "Payment not found yet. Wait a minute."), show_alert=True)
        return
    ok = await _credit_topup(call.message, bot, call.from_user.id, int(topup_id), "CRYPTO", invoice_id, lang, state)
    await call.answer(_tt(lang, "Готово ✅", "Done ✅") if ok else _tt(lang, "Уже зачислено ✅", "Already credited ✅"), show_alert=True)


async def _sales_log_topup(bot, user_id, topup):
    if not SALES_LOG_CHAT_ID:
        return
    try:
        await bot.send_message(SALES_LOG_CHAT_ID,
                               f"💵 <b>Пополнение</b>\nСумма: {topup['amount_rub']} ₽\n"
                               f"Способ: {topup['method']}\nПользователь: <code>{user_id}</code>")
    except Exception:
        pass


# ============ ПОКУПКА ============

@router.callback_query(F.data == "buy")
async def cb_buy(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    active = await db.active_plan(call.from_user.id)
    head = _tt(lang, "🛒 <b>Выбери тариф:</b>", "🛒 <b>Choose a plan:</b>")
    if active and active in PLANS:
        cur_title = PLANS[active]["title"]
        head = (_tt(lang, f"✅ Твой текущий тариф: <b>{cur_title}</b>\n"
                          f"🔁 Переключишься на другой — скидка <b>{SWITCH_DISCOUNT_PERCENT}%</b>!\n\n",
                          f"✅ Your current plan: <b>{cur_title}</b>\n"
                          f"🔁 Switch to another — get <b>{SWITCH_DISCOUNT_PERCENT}%</b> off!\n\n") + head)
    await _edit(call, head, plans_kb(lang, rate))
    await call.answer()


@router.callback_query(F.data.startswith("plan:"))
async def cb_plan(call: CallbackQuery, state: FSMContext):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    plan = call.data.split(":", 1)[1]
    if plan not in PLANS:
        await call.answer()
        return
    active = await db.active_plan(call.from_user.id)
    is_switch = bool(active and active in PLANS and active != plan)
    await state.update_data(switch_plan=plan if is_switch else None)
    card = texts.plan_card(plan, lang, rate)
    if is_switch:
        banner = _tt(lang,
            f"🔁 <b>Переключение с «{PLANS[active]['title']}» — скидка {SWITCH_DISCOUNT_PERCENT}%!</b>\n"
            f"Скидка применится автоматически при оформлении.\n\n",
            f"🔁 <b>Switch from «{PLANS[active]['title']}» — {SWITCH_DISCOUNT_PERCENT}% off!</b>\n"
            f"The discount applies automatically at checkout.\n\n")
        card = banner + card
    await _edit(call, card, devices_kb(plan, lang))
    await call.answer()


@router.callback_query(F.data.startswith("dev:"))
async def cb_devices(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    _, plan, devices = call.data.split(":")
    devices = int(devices)
    p = PLANS[plan]
    head = _tt(lang, "📅 Выбери период:", "📅 Choose a period:")
    text = f"{p['emoji']} <b>{p['title']}</b> · 📱 {texts.dev_title(devices, lang)}\n\n{head}"
    await _edit(call, text, periods_kb(plan, devices, lang, rate))
    await call.answer()


@router.callback_query(F.data.startswith("per:"))
async def cb_period(call: CallbackQuery, state: FSMContext):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    _, plan, devices, period = call.data.split(":")
    devices = int(devices)
    full = price_rub(plan, devices, period)
    loy = await _loyalty_pct(call.from_user.id)
    floor = _switch_floor(await state.get_data(), plan)
    disc_pct = max(loy, floor)
    disc = full * disc_pct // 100
    # Многоустройственный тариф → слот-подписка: регион не выбираем здесь,
    # устройства активируются по одному в «Мои подключения».
    if devices > 1:
        await _edit(call, texts.sub_order_summary(plan, devices, period, full, disc, lang, rate),
                    sub_buy_kb(plan, devices, period, lang))
        await call.answer()
        return
    regions = await db.regions_for_purchase()
    if not regions:
        await call.answer(_tt(lang,
            "😔 Серверов пока нет совсем. Загляни чуть позже.",
            "😔 No servers at all yet. Please check back later."), show_alert=True)
        return
    await _edit(call, texts.order_summary(plan, devices, period, full, disc, lang, rate),
                locations_kb(plan, devices, period, regions, lang))
    await call.answer()


@router.callback_query(F.data.startswith("subbuy:"))
async def cb_subbuy(call: CallbackQuery, bot: Bot, state: FSMContext):
    """Покупка слот-подписки (>1 устройства): оплата с баланса, без выбора региона."""
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    _, plan, devices, period = call.data.split(":")
    devices = int(devices)
    full = price_rub(plan, devices, period)
    data = await state.get_data()
    promo_code = data.get("promo_code")
    promo_percent = data.get("promo_percent", 0)
    if data.get("promo_ctx") != f"{plan}:{devices}:{period}":
        promo_code, promo_percent = None, 0
    promo_disc, promo_code, _eff = await _resolve_discount(call.from_user.id, full, promo_code, promo_percent, _switch_floor(data, plan))
    to_pay = full - promo_disc
    bal = await db.get_balance(call.from_user.id)
    if bal < to_pay:
        await state.update_data(pending={
            "type": "slots", "plan": plan, "devices": devices, "period": period, "region": "",
            "promo_code": promo_code, "promo_percent": promo_percent,
            "full": full, "promo_disc": promo_disc, "to_pay": to_pay,
        })
        await call.answer()
        await _edit(call, texts.need_topup(texts.money(to_pay, lang, rate),
                                           texts.money(bal, lang, rate), lang), balance_kb(lang))
        return
    if not await db.deduct_balance(call.from_user.id, to_pay):
        await call.answer(_tt(lang, "Недостаточно средств.", "Not enough balance."), show_alert=True)
        return
    order_id = await db.create_order(call.from_user.id, plan, devices, period, "", [],
                                     full, promo_disc, to_pay)
    if promo_code:
        await db.set_order_promo(order_id, promo_code)
        await _consume_promo(promo_code, call.from_user.id)
    await state.clear()
    await call.answer()
    order = await db.get_order(order_id)
    await _fulfill(call.message, call.from_user.id, order, bot, paid_money=False, lang=lang)


@router.callback_query(F.data == "locked")
async def cb_locked(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    await call.answer(_tt(lang, "⭐️ Доступно только на Premium и Ultimate.", "⭐️ Available on Premium and Ultimate only."), show_alert=True)


@router.callback_query(F.data.startswith("preok:"))
async def cb_preorder_ok(call: CallbackQuery, bot: Bot, state: FSMContext):
    from config import ADMIN_IDS, PREORDER_PROMISE_MIN, SALES_LOG_CHAT_ID
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    _, plan, devices, period, region = call.data.split(":", 4)
    devices = int(devices)
    full = price_rub(plan, devices, period)

    data = await state.get_data()
    promo_code = data.get("promo_code")
    promo_percent = data.get("promo_percent", 0)
    if data.get("promo_ctx") != f"{plan}:{devices}:{period}":
        promo_code, promo_percent = None, 0
    promo_disc, promo_code, _eff = await _resolve_discount(call.from_user.id, full, promo_code, promo_percent, _switch_floor(data, plan))
    to_pay = full - promo_disc

    # вдруг сервер уже появился — тогда обычная выдача
    reserved = await db.reserve_purchase(region, devices, call.from_user.id)
    if reserved is not None:
        bal = await db.get_balance(call.from_user.id)
        config_ids = [c["id"] for c in reserved]
        # баланса не хватает — держим появившийся сервер за пользователем
        if bal < to_pay:
            from config import ORDER_TTL_MIN
            order_id = await db.create_order(call.from_user.id, plan, devices, period, region,
                                             config_ids, full, promo_disc, to_pay)
            if promo_code:
                await db.set_order_promo(order_id, promo_code)
            await state.update_data(pending={
                "type": "order", "order_id": order_id,
                "plan": plan, "devices": devices, "period": period, "region": region,
                "promo_code": promo_code, "promo_percent": promo_percent,
                "full": full, "promo_disc": promo_disc, "to_pay": to_pay,
            })
            await call.answer()
            await _edit(call, texts.topup_hold(texts.money(to_pay, lang, rate),
                                               texts.money(bal, lang, rate), ORDER_TTL_MIN, lang),
                        balance_kb(lang))
            return
        if not await db.deduct_balance(call.from_user.id, to_pay):
            await db.free_configs(config_ids)
            await call.answer(_tt(lang, "Недостаточно средств.", "Not enough balance."), show_alert=True)
            return
        order_id = await db.create_order(call.from_user.id, plan, devices, period, region,
                                         config_ids, full, promo_disc, to_pay)
        if promo_code:
            await db.set_order_promo(order_id, promo_code)
            await _consume_promo(promo_code, call.from_user.id)
        await state.clear()
        await call.answer()
        order = await db.get_order(order_id)
        await _fulfill(call.message, call.from_user.id, order, bot, paid_money=False, lang=lang)
        return

    # сервера нет — оформляем предзаказ (но сначала убедимся, что хватает баланса)
    bal = await db.get_balance(call.from_user.id)
    if bal < to_pay:
        await state.update_data(pending={
            "type": "preorder",
            "plan": plan, "devices": devices, "period": period, "region": region,
            "promo_code": promo_code, "promo_percent": promo_percent,
            "full": full, "promo_disc": promo_disc, "to_pay": to_pay,
        })
        await call.answer()
        await _edit(call, texts.need_topup(texts.money(to_pay, lang, rate),
                                           texts.money(bal, lang, rate), lang), balance_kb(lang))
        return
    if not await db.deduct_balance(call.from_user.id, to_pay):
        await call.answer(_tt(lang, "Недостаточно средств.", "Not enough balance."), show_alert=True)
        return
    if promo_code:
        await _consume_promo(promo_code, call.from_user.id)
    po_id = await db.create_preorder(call.from_user.id, plan, devices, period, region,
                                     full, promo_disc, to_pay, promo_code, lang)
    await state.clear()
    await call.answer()
    await _edit(call, texts.preorder_created(PREORDER_PROMISE_MIN, lang), back_to_menu_kb(lang))

    await _admin_preorder_alert(bot, call.from_user.id, region, plan, devices, period, to_pay, po_id)


@router.callback_query(F.data == "resume")
async def cb_resume(call: CallbackQuery, bot: Bot, state: FSMContext):
    """Завершить отложенный заказ после пополнения баланса."""
    from config import ADMIN_IDS, ORDER_TTL_MIN, PREORDER_PROMISE_MIN, SALES_LOG_CHAT_ID
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    data = await state.get_data()
    pending = data.get("pending")
    if not pending:
        await call.answer(_tt(lang, "Нечего завершать 🙂", "Nothing to complete 🙂"), show_alert=True)
        return

    plan = pending["plan"]
    devices = int(pending["devices"])
    period = pending["period"]
    region = pending["region"]
    full = pending["full"]
    promo_disc = pending["promo_disc"]
    to_pay = pending["to_pay"]
    promo_code = pending.get("promo_code")

    bal = await db.get_balance(call.from_user.id)
    if bal < to_pay:
        # всё ещё не хватает — снова на пополнение, заказ остаётся в ожидании
        await call.answer()
        await _edit(call, texts.topup_hold(texts.money(to_pay, lang, rate),
                                           texts.money(bal, lang, rate), ORDER_TTL_MIN, lang),
                    balance_kb(lang))
        return

    charged_msg = _tt(lang, f"💳 Списано с баланса: <b>{texts.money(to_pay, lang, rate)}</b>",
                      f"💳 Charged from balance: <b>{texts.money(to_pay, lang, rate)}</b>")

    # 0) Слот-подписка (многоустройственный тариф) — конфиги не бронируем, выдаём слоты
    if pending["type"] == "slots":
        if not await db.deduct_balance(call.from_user.id, to_pay):
            await call.answer(_tt(lang, "Недостаточно средств.", "Not enough balance."), show_alert=True)
            return
        order_id = await db.create_order(call.from_user.id, plan, devices, period, "", [],
                                         full, promo_disc, to_pay)
        if promo_code:
            await db.set_order_promo(order_id, promo_code)
            await _consume_promo(promo_code, call.from_user.id)
        await state.update_data(pending=None)
        await call.answer()
        await call.message.answer(charged_msg)
        order = await db.get_order(order_id)
        await _fulfill(call.message, call.from_user.id, order, bot, paid_money=False, lang=lang)
        return

    # 1) Заранее забронированный сервер ещё держится — просто оплачиваем
    if pending["type"] == "order":
        order = await db.get_order(pending["order_id"])
        if order and order["status"] == "pending":
            if not await db.deduct_balance(call.from_user.id, to_pay):
                await call.answer(_tt(lang, "Недостаточно средств.", "Not enough balance."), show_alert=True)
                return
            if promo_code:
                await _consume_promo(promo_code, call.from_user.id)
            await state.update_data(pending=None)
            await call.answer()
            await call.message.answer(charged_msg)
            await _fulfill(call.message, call.from_user.id, order, bot, paid_money=False, lang=lang)
            return
        # бронь истекла (заказ отменён по таймауту) — пробуем взять сервер заново ниже

    # 2) Бронируем сервер заново (предзаказ или истёкшая бронь)
    reserved = await db.reserve_purchase(region, devices, call.from_user.id)
    if reserved is not None:
        if not await db.deduct_balance(call.from_user.id, to_pay):
            await db.free_configs([c["id"] for c in reserved])
            await call.answer(_tt(lang, "Недостаточно средств.", "Not enough balance."), show_alert=True)
            return
        config_ids = [c["id"] for c in reserved]
        order_id = await db.create_order(call.from_user.id, plan, devices, period, region,
                                         config_ids, full, promo_disc, to_pay)
        if promo_code:
            await db.set_order_promo(order_id, promo_code)
            await _consume_promo(promo_code, call.from_user.id)
        await state.update_data(pending=None)
        await call.answer()
        order = await db.get_order(order_id)
        await call.message.answer(charged_msg)
        await _fulfill(call.message, call.from_user.id, order, bot, paid_money=False, lang=lang)
        return

    # 3) Сервера по-прежнему нет — оформляем предзаказ (баланс уже достаточен)
    if not await db.deduct_balance(call.from_user.id, to_pay):
        await call.answer(_tt(lang, "Недостаточно средств.", "Not enough balance."), show_alert=True)
        return
    if promo_code:
        await _consume_promo(promo_code, call.from_user.id)
    po_id = await db.create_preorder(call.from_user.id, plan, devices, period, region,
                                     full, promo_disc, to_pay, promo_code, lang)
    await state.update_data(pending=None)
    await call.answer()
    await _edit(call, texts.preorder_created(PREORDER_PROMISE_MIN, lang), back_to_menu_kb(lang))
    await _admin_preorder_alert(bot, call.from_user.id, region, plan, devices, period, to_pay, po_id)


async def deliver_preorder(bot: Bot, po: dict) -> bool:
    """Бронирует свободный конфиг и выдаёт предзаказ клиенту. True — выдано."""
    reserved = await db.reserve_purchase(po["region"], po["devices"], po["user_id"])
    if reserved is None:
        return False
    lang = po.get("lang") or "ru"
    config_ids = [c["id"] for c in reserved]
    order_id = await db.create_order(po["user_id"], po["plan"], po["devices"], po["period"],
                                     po["region"], config_ids, po["full_rub"], po["discount"], po["rub"])
    if po.get("promo"):
        await db.set_order_promo(order_id, po["promo"])
    await db.set_preorder_status(po["id"], "fulfilled")

    class _T:
        async def answer(self, *a, **k):
            await bot.send_message(po["user_id"], *a, **k)

        async def answer_document(self, doc, caption=None):
            await bot.send_document(po["user_id"], doc, caption=caption)

        async def answer_photo(self, photo):
            await bot.send_photo(po["user_id"], photo)

    target = _T()
    await target.answer(_tt(lang, "🎉 <b>Сервер готов!</b> Твой предзаказ выдан 👇",
                            "🎉 <b>Server ready!</b> Here's your pre-order 👇"))
    order = await db.get_order(order_id)
    await _fulfill(target, po["user_id"], order, bot, paid_money=False, lang=lang)
    # уведомляем админов, что предзаказ закрыт автоматически
    u = await db.get_user(po["user_id"]) or {}
    await _notify_admins(bot, texts.admin_preorder_delivered(
        po["region"], po["user_id"],
        username=u.get("username"), full_name=u.get("full_name"),
    ))
    return True


async def refund_preorder(bot: Bot, po: dict):
    await db.add_balance(po["user_id"], po["rub"])
    await db.set_preorder_status(po["id"], "refunded")
    lang = po.get("lang") or "ru"
    rate = await _rate(lang)
    try:
        await bot.send_message(po["user_id"],
                               texts.preorder_refunded(texts.money(po["rub"], lang, rate), lang),
                               reply_markup=balance_kb(lang))
    except Exception:
        pass


@router.callback_query(F.data.startswith("promoask:"))
async def cb_promo_ask(call: CallbackQuery, state: FSMContext):
    lang = await _lang(call.from_user.id)
    _, plan, devices, period = call.data.split(":")
    await state.set_state(PromoUser.waiting)
    await state.update_data(promo_ctx=f"{plan}:{devices}:{period}")
    await call.message.answer(_tt(lang,
        "🎟 Пришли промокод одним сообщением (или /cancel).",
        "🎟 Send your promo code in one message (or /cancel)."))
    await call.answer()


@router.message(PromoUser.waiting, Command("cancel"))
async def cb_promo_cancel(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    await state.set_state(None)
    await message.answer(_tt(lang, "Отменено. Вернись к выбору сервера.", "Cancelled. Go back to server selection."))


@router.message(PromoUser.waiting, F.text)
async def cb_promo_apply(message: Message, state: FSMContext):
    lang = await _lang(message.from_user.id)
    rate = await _rate(lang)
    code = message.text.strip()
    promo = await db.get_promo(code)
    data = await state.get_data()
    ctx = data.get("promo_ctx", "")
    if not promo:
        await message.answer(_tt(lang, "❌ Промокод неверный или больше не действует.",
                                 "❌ Invalid or expired promo code."))
        return
    # промокод на баланс (активируется на экране Баланс)
    if ctx == "balance":
        await state.clear()
        if promo["kind"] != "balance":
            await message.answer(_tt(lang, "ℹ️ Это промокод на скидку — введи его при покупке тарифа.",
                                     "ℹ️ This is a discount promo — enter it during purchase."))
            return
        if await db.promo_redeemed_by(promo["code"], message.from_user.id):
            await message.answer(texts.promo_already_used(lang), reply_markup=balance_kb(lang))
            return
        await db.add_balance(message.from_user.id, promo["amount_rub"])
        await db.use_promo(promo["code"])
        await db.record_promo_redemption(promo["code"], message.from_user.id)
        bal = await db.get_balance(message.from_user.id)
        await message.answer(texts.promo_balance_added(texts.money(promo["amount_rub"], lang, rate),
                                                       texts.money(bal, lang, rate), lang),
                             reply_markup=balance_kb(lang))
        return
    if promo["kind"] != "discount":
        await message.answer(_tt(lang, "ℹ️ Это промокод на баланс. Активируй его на экране «💰 Баланс» → «🎟 Промокод».",
                                 "ℹ️ This is a balance promo. Activate it on «💰 Balance» → «🎟 Promo code»."))
        return
    if await db.promo_redeemed_by(promo["code"], message.from_user.id):
        await message.answer(texts.promo_already_used(lang))
        return
    await state.update_data(promo_code=promo["code"], promo_percent=promo["percent"])
    await state.set_state(None)
    try:
        plan, devices, period = ctx.split(":")
        devices = int(devices)
    except Exception:
        await message.answer(_tt(lang, "✅ Промокод принят. Вернись и выбери сервер.",
                                 "✅ Promo accepted. Go back and pick a server."))
        return
    full = price_rub(plan, devices, period)
    promo_disc = full * promo["percent"] // 100
    regions = await db.regions_for_purchase()
    await message.answer(_tt(lang, f"✅ Промокод <b>{promo['code']}</b>: −{promo['percent']}%",
                             f"✅ Promo <b>{promo['code']}</b>: −{promo['percent']}%"))
    if regions:
        await message.answer(texts.order_summary(plan, devices, period, full, promo_disc, lang, rate),
                             reply_markup=locations_kb(plan, devices, period, regions, lang))


@router.callback_query(F.data == "promobal")
async def cb_promo_balance_ask(call: CallbackQuery, state: FSMContext):
    lang = await _lang(call.from_user.id)
    await state.set_state(PromoUser.waiting)
    await state.update_data(promo_ctx="balance")
    await call.message.answer(_tt(lang, "🎟 Пришли промокод одним сообщением (или /cancel).",
                                  "🎟 Send your promo code in one message (or /cancel)."))
    await call.answer()


@router.callback_query(F.data.startswith("buyloc:"))
async def cb_buyloc(call: CallbackQuery, bot: Bot, state: FSMContext):
    _, plan, devices, period, region = call.data.split(":", 4)
    await _buyloc(call, bot, state, plan, int(devices), period, region)


async def _buyloc(call: CallbackQuery, bot: Bot, state: FSMContext, plan, devices, period, region):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    devices = int(devices)
    full = price_rub(plan, devices, period)

    data = await state.get_data()
    promo_code = data.get("promo_code")
    promo_percent = data.get("promo_percent", 0)
    if data.get("promo_ctx") != f"{plan}:{devices}:{period}":
        promo_code, promo_percent = None, 0
    promo_disc, promo_code, _eff = await _resolve_discount(call.from_user.id, full, promo_code, promo_percent, _switch_floor(data, plan))
    to_pay = full - promo_disc

    bal = await db.get_balance(call.from_user.id)

    reserved = await db.reserve_purchase(region, devices, call.from_user.id)
    if reserved is None:
        # сервера нет — сразу предлагаем предзаказ (баланс проверим при подтверждении)
        from config import PREORDER_PROMISE_MIN
        kb = InlineKeyboardBuilder()
        kb.button(text=_tt(lang, "✅ Да, оформить", "✅ Yes, place it"),
                  callback_data=f"preok:{plan}:{devices}:{period}:{region}")
        kb.button(text=_tt(lang, "⬅️ Отмена", "⬅️ Cancel"), callback_data="buy")
        kb.adjust(1)
        await call.answer()
        await _edit(call, texts.preorder_offer(texts.region_name(region, lang), texts.money(to_pay, lang, rate),
                                               PREORDER_PROMISE_MIN, lang), kb.as_markup())
        return

    # сервер есть, но баланса не хватает — ДЕРЖИМ его за пользователем (бронь),
    # чтобы после пополнения он не потерял сервер и не увидел «нет серверов».
    if bal < to_pay:
        from config import ORDER_TTL_MIN
        config_ids = [c["id"] for c in reserved]
        order_id = await db.create_order(
            call.from_user.id, plan, devices, period, region, config_ids, full, promo_disc, to_pay
        )
        if promo_code:
            await db.set_order_promo(order_id, promo_code)
        await state.update_data(pending={
            "type": "order", "order_id": order_id,
            "plan": plan, "devices": devices, "period": period, "region": region,
            "promo_code": promo_code, "promo_percent": promo_percent,
            "full": full, "promo_disc": promo_disc, "to_pay": to_pay,
        })
        await call.answer()
        await _edit(call, texts.topup_hold(texts.money(to_pay, lang, rate),
                                           texts.money(bal, lang, rate), ORDER_TTL_MIN, lang),
                    balance_kb(lang))
        return

    if not await db.deduct_balance(call.from_user.id, to_pay):
        await db.free_configs([c["id"] for c in reserved])
        await call.answer(_tt(lang, "Недостаточно средств.", "Not enough balance."), show_alert=True)
        return

    config_ids = [c["id"] for c in reserved]
    order_id = await db.create_order(
        call.from_user.id, plan, devices, period, region, config_ids, full, promo_disc, to_pay
    )
    if promo_code:
        await db.set_order_promo(order_id, promo_code)
        await _consume_promo(promo_code, call.from_user.id)
    await state.clear()
    await call.answer()
    order = await db.get_order(order_id)
    await call.message.answer(_tt(lang, f"💳 Списано с баланса: <b>{texts.money(to_pay, lang, rate)}</b>",
                                  f"💳 Charged from balance: <b>{texts.money(to_pay, lang, rate)}</b>"))
    await _fulfill(call.message, call.from_user.id, order, bot, paid_money=False, lang=lang)


# ============ ВЫБОР СПОСОБА ОПЛАТЫ ============

def _order_title(order: dict, lang: str) -> tuple[str, str]:
    p = PLANS[order["plan"]]
    title = f"{p['title']} · {texts.dev_title(order['devices'], lang)} · {texts.per_title(order['period'], lang)}"
    rname = texts.region_name(order["region"], lang)
    desc = _tt(lang, f"VPN-доступ ({rname}).", f"VPN access ({rname}).")
    return title, desc


async def _offer_payment(target: Message, bot: Bot, user_id: int, order_id: int, lang: str):
    order = await db.get_order(order_id)
    to_pay = order["rub"]
    if to_pay <= 0:
        await target.answer(_tt(lang, "🎁 <b>Оплачено бонусным балансом!</b>", "🎁 <b>Paid with bonus balance!</b>"))
        await _fulfill(target, user_id, order, bot, paid_money=False, lang=lang)
        return
    if PAYMENT_MODE != "choice":
        await _do_payment(target, bot, user_id, order, PAYMENT_MODE, lang)
        return

    rate = await _rate(lang)
    amount_str = texts.money(to_pay, lang, rate)

    # для англоязычных: карта/СБП — российские методы, поэтому только крипта
    if lang == "en":
        await _do_payment(target, bot, user_id, order, "crypto", lang)
        return

    kb = InlineKeyboardBuilder()
    kb.button(text="💳 Банковская карта", callback_data=f"pay:lava:{order_id}")
    kb.button(text="⚡️ СБП", callback_data=f"pay:sbp:{order_id}")
    kb.button(text="🪙 Криптовалюта", callback_data=f"pay:crypto:{order_id}")
    kb.adjust(1)
    await target.answer(
        f"💰 <b>К оплате: {amount_str}</b>\n{texts.LINE}\nВыбери удобный способ оплаты 👇",
        reply_markup=kb.as_markup(),
    )


@router.callback_query(F.data.startswith("pay:"))
async def cb_pay(call: CallbackQuery, bot: Bot):
    lang = await _lang(call.from_user.id)
    _, method, order_id = call.data.split(":")
    order = await db.get_order(int(order_id))
    if not order or order["status"] == "paid":
        await call.answer(_tt(lang, "Заказ уже обработан.", "Order already processed."), show_alert=True)
        return
    await call.answer()
    await _do_payment(call.message, bot, call.from_user.id, order, method, lang)


async def _do_payment(target: Message, bot: Bot, user_id: int, order: dict, method: str, lang: str):
    title, desc = _order_title(order, lang)
    to_pay = order["rub"]
    order_id = order["id"]
    rate = await _rate(lang)
    amount_str = texts.money(to_pay, lang, rate)
    err = _tt(lang, "⚠️ Не удалось создать счёт. Попробуй другой способ или напиши в поддержку.",
              "⚠️ Couldn't create the invoice. Try another method or contact support.")
    paid_btn = _tt(lang, "✅ Я оплатил — проверить", "✅ I paid — check")
    steps_card = _tt(lang, "1️⃣ Нажми кнопку оплаты и заверши платёж\n2️⃣ Вернись и нажми «Я оплатил — проверить»",
                     "1️⃣ Tap the pay button and finish the payment\n2️⃣ Come back and tap «I paid — check»")

    if method in ("lava", "sbp", "card"):
        try:
            _iid, pay_url = await create_lava_invoice(order_id, to_pay, title)
        except Exception as e:
            log.exception("lava invoice error: %s", e)
            await target.answer(err)
            return
        if method == "sbp":
            label = _tt(lang, "⚡️ Оплатить через СБП", "⚡️ Pay via SBP")
        else:
            label = _tt(lang, "💳 Оплатить картой", "💳 Pay by card")
        kb = InlineKeyboardBuilder()
        kb.button(text=label, url=pay_url)
        kb.button(text=paid_btn, callback_data=f"check_lava:{order_id}")
        kb.adjust(1)
        head = _tt(lang, f"💳 <b>Оплата {amount_str}</b>", f"💳 <b>Payment {amount_str}</b>")
        await target.answer(f"{head}\n{texts.LINE}\n{steps_card}", reply_markup=kb.as_markup())
        return

    if method == "crypto":
        try:
            invoice_id, pay_url = await create_crypto_invoice(order_id, to_pay, title)
        except Exception as e:
            log.exception("crypto invoice error: %s", e)
            await target.answer(err)
            return
        if not pay_url:
            await target.answer(err)
            return
        kb = InlineKeyboardBuilder()
        kb.button(text=_tt(lang, "🪙 Оплатить криптой", "🪙 Pay with crypto"), url=pay_url)
        kb.button(text=paid_btn, callback_data=f"check_crypto:{invoice_id}:{order_id}")
        kb.adjust(1)
        head = _tt(lang, f"🪙 <b>Оплата {amount_str} криптовалютой</b>", f"🪙 <b>Payment {amount_str} in crypto</b>")
        steps = _tt(lang, "1️⃣ Нажми «Оплатить криптой» и оплати в @CryptoBot\n2️⃣ Вернись и нажми «Я оплатил — проверить»",
                    "1️⃣ Tap «Pay with crypto» and pay in @CryptoBot\n2️⃣ Come back and tap «I paid — check»")
        await target.answer(f"{head}\n{texts.LINE}\n{steps}", reply_markup=kb.as_markup())
        return

    await bot.send_invoice(chat_id=user_id, **invoice_params(title, desc, f"order:{order_id}", to_pay))


@router.callback_query(F.data.startswith("check_lava:"))
async def check_lava_payment(call: CallbackQuery, bot: Bot):
    lang = await _lang(call.from_user.id)
    order_id = call.data.split(":", 1)[1]
    try:
        paid = await check_lava_invoice(int(order_id))
    except Exception as e:
        log.exception("lava check error: %s", e)
        await call.answer(_tt(lang, "Не удалось проверить, попробуй ещё раз.", "Check failed, try again."), show_alert=True)
        return
    await _after_check(call, bot, paid, int(order_id), "LAVA", str(order_id), lang)


@router.callback_query(F.data.startswith("check_crypto:"))
async def check_crypto_payment(call: CallbackQuery, bot: Bot):
    lang = await _lang(call.from_user.id)
    _, invoice_id, order_id = call.data.split(":")
    try:
        paid = await check_crypto_invoice(int(invoice_id))
    except Exception as e:
        log.exception("crypto check error: %s", e)
        await call.answer(_tt(lang, "Не удалось проверить, попробуй ещё раз.", "Check failed, try again."), show_alert=True)
        return
    await _after_check(call, bot, paid, int(order_id), "CRYPTO", str(invoice_id), lang)


async def _after_check(call, bot, paid, order_id, method_name, ref, lang):
    if not paid:
        await call.answer(_tt(lang, "Оплата пока не найдена. Подожди минуту и нажми снова.",
                              "Payment not found yet. Wait a minute and tap again."), show_alert=True)
        return
    order = await db.get_order(order_id)
    if not order or order["status"] == "paid":
        await call.answer(_tt(lang, "Заказ уже обработан ✅", "Order already processed ✅"), show_alert=True)
        return
    await call.answer(_tt(lang, "Оплата найдена ✅", "Payment found ✅"), show_alert=True)
    await db.record_payment(call.from_user.id, order["id"], order["rub"], method_name, ref)
    await _fulfill(call.message, call.from_user.id, order, bot, paid_money=True, lang=lang)


# ============ Stars / ЮKassa ============

@router.pre_checkout_query()
async def pre_checkout(pcq: PreCheckoutQuery):
    await pcq.answer(ok=True)


@router.message(F.successful_payment)
async def on_paid(message: Message, bot: Bot):
    lang = await _lang(message.from_user.id)
    sp = message.successful_payment
    _, _, raw = sp.invoice_payload.partition(":")
    order = await db.get_order(int(raw))
    if not order or order["status"] == "paid":
        return
    await db.record_payment(message.from_user.id, order["id"], sp.total_amount, sp.currency,
                            sp.telegram_payment_charge_id)
    await _fulfill(message, message.from_user.id, order, bot, paid_money=True, lang=lang)


# ============ ВЫДАЧА ============

async def _fulfill(target: Message, user_id: int, order: dict, bot: Bot, paid_money: bool, lang: str = "ru"):
    await db.set_order_status(order["id"], "paid")
    if order.get("discount", 0) > 0:
        await db.use_ref_balance(user_id, order["discount"])
    config_ids = [int(x) for x in order["config_ids"].split(",") if x]
    total = len(config_ids)
    # Слот-заказ (многоустройственный тариф): конфигов нет — выдаём подписку со слотами,
    # устройства клиент активирует по одному в «Мои подключения».
    if total == 0:
        sub_id = await db.create_subscription(user_id, order["plan"], order["devices"], order["period"])
        await target.answer(texts.sub_created(order["devices"], lang), reply_markup=main_menu_kb(lang))
        if paid_money:
            if order.get("promo"):
                await _consume_promo(order["promo"], user_id)
            await _reward_referrer(user_id, order["full_rub"], bot)
            await _sales_log(bot, user_id, order)
        return
    if lang == "en":
        await target.answer(f"🎉 <b>Done!</b> Sending your {'config' if total == 1 else f'{total} configs'} 👇")
    else:
        await target.answer(f"🎉 <b>Готово!</b> Высылаю {'конфиг' if total == 1 else f'{total} конфига'} 👇")
    for idx, cid in enumerate(config_ids, start=1):
        expires = await db.mark_sold(cid, user_id, order["plan"], order["period"])
        cfg = await db.get_config(cid)
        await _send_config(target, cfg, expires, idx, total, lang)
    await target.answer(_tt(lang, "📖 Как подключить — выбери платформу:", "📖 How to connect — choose a platform:"), reply_markup=howto_kb(lang))
    applied, _region = await db.apply_bonus(user_id)
    if applied:
        await target.answer(_tt(lang, f"🎁 К твоей подписке добавлено <b>{applied}</b> бонусных дней!",
                                f"🎁 <b>{applied}</b> bonus days added to your subscription!"))
    if paid_money:
        if order.get("promo"):
            await _consume_promo(order["promo"], user_id)
        await _reward_referrer(user_id, order["full_rub"], bot)
        await _sales_log(bot, user_id, order)


async def _reward_referrer(buyer_id: int, full_rub: int, bot: Bot):
    buyer = await db.get_user(buyer_id)
    ref_id = buyer and buyer.get("referred_by")
    if not ref_id:
        return
    rlang = await db.get_lang(ref_id)
    cashback = full_rub * REF_PERCENT // 100
    if cashback > 0:
        # 15% идёт на выводимый реферальный баланс (реальные деньги)
        await db.add_ref_cash(ref_id, cashback)
    await db.add_bonus_days(ref_id, REF_REWARD_DAYS)
    applied, region = await db.apply_bonus(ref_id)
    region_disp = texts.region_name(region, rlang)
    try:
        if rlang == "en":
            msg = ["🎉 Your friend topped up / bought!"]
            if cashback > 0:
                msg.append(f"💰 +{cashback} ₽ to your withdrawable balance")
            msg.append(f"🎁 +{applied} days to subscription ({region_disp})" if applied
                       else f"🎁 +{REF_REWARD_DAYS} bonus days (applied on purchase)")
        else:
            msg = ["🎉 Твой друг пополнил баланс / купил!"]
            if cashback > 0:
                msg.append(f"💰 +{cashback} ₽ на выводимый баланс")
            msg.append(f"🎁 +{applied} дней к подписке ({region_disp})" if applied
                       else f"🎁 +{REF_REWARD_DAYS} бонусных дней (добавятся при покупке)")
        await bot.send_message(ref_id, "\n".join(msg))
    except Exception:
        pass
    await _check_ref_milestones(ref_id, rlang, bot)


async def _check_ref_milestones(ref_id: int, rlang: str, bot: Bot):
    """Разовые бонусы за число приглашённых (5/10/25/50...)."""
    try:
        st = await db.referral_stats(ref_id)
        invited = st.get("invited", 0)
        already = await db.get_ref_milestone(ref_id)
        highest = already
        for threshold, bonus in sorted(REF_MILESTONES):
            if invited >= threshold > already:
                await db.add_ref_cash(ref_id, bonus)
                highest = max(highest, threshold)
                try:
                    await bot.send_message(ref_id, texts.ref_milestone_msg(threshold, bonus, rlang))
                except Exception:
                    pass
        if highest > already:
            await db.set_ref_milestone(ref_id, highest)
    except Exception:
        pass


async def _sales_log(bot: Bot, user_id: int, order: dict):
    if not SALES_LOG_CHAT_ID:
        return
    try:
        p = PLANS.get(order["plan"], {})
        title = p.get("title", order["plan"])
        promo = f" · 🎟{order['promo']}" if order.get("promo") else ""
        text = (f"💰 <b>Продажа</b>\n"
                f"Тариф: {title} · {order['devices']} устр · {order['period']}\n"
                f"Регион: {order['region']}\n"
                f"Сумма: {order['rub']} ₽{promo}\n"
                f"Покупатель: <code>{user_id}</code>")
        await bot.send_message(SALES_LOG_CHAT_ID, text)
    except Exception:
        pass


async def send_config_to(bot: Bot, user_id: int, cfg: dict, lang: str = "ru"):
    """Отправляет конфиг конкретному пользователю по user_id (для админских действий)."""
    region = cfg["region"]
    text = cfg["config_text"]
    filename = f"{texts.region_slug(region)}_{cfg['id']}.conf"
    try:
        exp = datetime.fromisoformat((cfg.get("expires_at") or "").replace("Z", ""))
    except (ValueError, TypeError):
        exp = now()
    caption = texts.delivery_caption(flag(region), texts.region_name(region, lang),
                                     exp.strftime("%d.%m.%Y %H:%M UTC"), 1, 1, lang)
    await bot.send_document(user_id, BufferedInputFile(text.encode(), filename=filename), caption=caption)
    await bot.send_photo(user_id, BufferedInputFile(make_qr_png(text), filename="qr.png"))


async def _send_config(target: Message, cfg: dict, expires, idx, total, lang="ru"):
    region = cfg["region"]
    text = cfg["config_text"]
    filename = f"{texts.region_slug(region)}_{cfg['id']}.conf"
    caption = texts.delivery_caption(flag(region), texts.region_name(region, lang),
                                     expires.strftime("%d.%m.%Y %H:%M UTC"), idx, total, lang)
    await target.answer_document(BufferedInputFile(text.encode(), filename=filename), caption=caption)
    await target.answer_photo(BufferedInputFile(make_qr_png(text), filename="qr.png"))


# ============ МОИ ПОДКЛЮЧЕНИЯ ============

@router.message(Command("myconfigs"))
async def cmd_my(message: Message):
    lang = await _lang(message.from_user.id)
    await _show_my(message, message.from_user.id, lang)


@router.callback_query(F.data == "my")
async def cb_my(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    await call.answer()
    await _show_my(call.message, call.from_user.id, lang)


async def _show_my(message: Message, user_id: int, lang: str):
    subs = await db.user_subscriptions(user_id)
    configs = await db.user_configs(user_id)
    # В списке показываем ТОЛЬКО активные конфиги. Истёкшие (status != 'sold')
    # не выводим вовсе, чтобы не засоряли «Мои подключения».
    # (Заморозка статус не меняет — замороженные остаются 'sold' и показываются.)
    active_configs = [c for c in configs if c["status"] == "sold"]
    # Только ОДИН тариф — самый свежий. user_subscriptions отдаёт подписки по id
    # по убыванию, поэтому subs[0] — последняя купленная. Старые в списке не показываем:
    # купил новую — старая сразу «пропадает» из «Мои подключения» (из базы не удаляется).
    latest_sub = subs[0] if subs else None
    free_subs = [latest_sub] if (latest_sub and latest_sub["free_slots"] > 0) else []
    if not free_subs and not active_configs:
        await message.answer(_tt(lang, "📁 У тебя пока нет активных подключений.",
                                 "📁 You have no active connections yet."),
                             reply_markup=back_to_menu_kb(lang))
        return
    # подписки на несколько устройств — со свободными слотами для активации
    for s in free_subs:
        await message.answer(texts.sub_slot_block(s, lang),
                             reply_markup=sub_activate_kb(s["id"], s["free_slots"], lang))
    if active_configs:
        await message.answer(_tt(lang, "📁 <b>Твои подключения:</b>", "📁 <b>Your connections:</b>"))
        for cfg in active_configs:
            status = _tt(lang, "✅ активен", "✅ active")
            exp = cfg["expires_at"][:10] if cfg["expires_at"] else "—"
            until = _tt(lang, "до", "until")
            await message.answer(
                f"{flag(cfg['region'])} <b>{texts.region_name(cfg['region'], lang)}</b> — {status}\n⏳ {until}: <code>{exp}</code>",
                reply_markup=connection_kb(cfg["id"], lang),
            )


# ============ ИНСТРУКЦИИ ============

@router.callback_query(F.data == "howto")
async def cb_howto(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    await _edit(call, texts.howto_intro(lang), howto_kb(lang))
    await call.answer()


@router.callback_query(F.data.startswith("guide:"))
async def cb_guide(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    platform = call.data.split(":", 1)[1]
    await _edit(call, texts.guide(platform, lang), guide_back_kb(lang))
    await call.answer()


# ============ ПРОДЛЕНИЕ ============

@router.callback_query(F.data.startswith("renew:"))
async def cb_renew(call: CallbackQuery, bot: Bot):
    lang = await _lang(call.from_user.id)
    rate = await _rate(lang)
    config_id = int(call.data.split(":", 1)[1])
    cfg = await db.get_config(config_id)
    if not cfg or cfg["user_id"] != call.from_user.id:
        await call.answer(_tt(lang, "Конфиг не найден 😔", "Config not found 😔"), show_alert=True)
        return
    plan = cfg["plan"] or "standard"
    period = cfg["period"] if cfg["period"] in ("month", "year") else "month"
    full = price_rub(plan, 1, period)
    loy = await _loyalty_pct(call.from_user.id)
    to_pay = full - full * loy // 100

    bal = await db.get_balance(call.from_user.id)
    if bal < to_pay:
        await call.answer()
        await _edit(call, texts.need_topup(texts.money(to_pay, lang, rate),
                                           texts.money(bal, lang, rate), lang), balance_kb(lang))
        return
    if not await db.deduct_balance(call.from_user.id, to_pay):
        await call.answer(_tt(lang, "Недостаточно средств.", "Not enough balance."), show_alert=True)
        return

    order_id = await db.create_order(
        call.from_user.id, plan, 1, period, cfg["region"], [config_id], full, 0, to_pay
    )
    await call.answer()
    order = await db.get_order(order_id)
    await call.message.answer(_tt(lang, f"💳 Списано с баланса: <b>{texts.money(to_pay, lang, rate)}</b>",
                                  f"💳 Charged from balance: <b>{texts.money(to_pay, lang, rate)}</b>"))
    await _fulfill(call.message, call.from_user.id, order, bot, paid_money=False, lang=lang)


# ============ АВТОПРОДЛЕНИЕ (фоновое) ============

async def auto_renew(bot: Bot, cfg: dict) -> bool:
    """Пытается автоматически продлить подписку cfg с баланса пользователя."""
    user_id = cfg["user_id"]
    plan = cfg["plan"] or "standard"
    period = cfg["period"] if cfg["period"] in ("month", "year") else "month"
    full = price_rub(plan, 1, period)
    loy = loyalty_percent_for(await db.total_spent(user_id))
    to_pay = full - full * loy // 100
    lang = await db.get_lang(user_id)
    rate = await _rate(lang)

    if not await db.deduct_balance(user_id, to_pay):
        # не хватило баланса — помечаем, чтобы не дёргать каждый цикл, и зовём продлить вручную
        await db.mark_renew_notified(cfg["id"])
        try:
            await bot.send_message(
                user_id,
                texts.autorenew_failed(texts.region_name(cfg["region"], lang),
                                       texts.money(to_pay, lang, rate), lang),
                reply_markup=renew_kb(cfg["id"], lang),
            )
        except Exception:
            pass
        return False

    new_exp = await db.extend_config(cfg["id"], PERIOD_DAYS[period])
    try:
        await bot.send_message(
            user_id,
            texts.autorenew_done(texts.region_name(cfg["region"], lang),
                                 texts.money(to_pay, lang, rate),
                                 new_exp.strftime("%d.%m.%Y %H:%M UTC"), lang),
        )
    except Exception:
        pass
    if SALES_LOG_CHAT_ID:
        try:
            await bot.send_message(
                SALES_LOG_CHAT_ID,
                f"🔁 <b>Автопродление</b>\nРегион: {cfg['region']}\n"
                f"Сумма: {to_pay} ₽\nПользователь: <code>{user_id}</code>",
            )
        except Exception:
            pass
    return True


# ============ ЗАМЕНА КОНФИГА ============

_REASON_RU = {
    "dead": "🚫 не работает / не подключается",
    "slow": "🐢 медленно / нестабильно",
    "blocked": "📱 заблокировал провайдер",
    "country": "🌍 смена страны",
    "other": "✍️ другое",
}


@router.callback_query(F.data.startswith("rep:"))
async def cb_replace(call: CallbackQuery):
    lang = await _lang(call.from_user.id)
    config_id = int(call.data.split(":", 1)[1])
    cfg = await db.get_config(config_id)
    if not cfg or cfg["user_id"] != call.from_user.id or cfg["status"] != "sold":
        await call.answer(_tt(lang, "Активный конфиг не найден 😔", "Active config not found 😔"), show_alert=True)
        return
    await _edit(call, _tt(lang,
        "🔁 <b>Замена конфига</b>\n\nЧто случилось? Это поможет нам выдать тебе рабочий вариант:",
        "🔁 <b>Replace config</b>\n\nWhat happened? This helps us give you a working one:"),
        replace_reasons_kb(config_id, lang))
    await call.answer()


@router.callback_query(F.data.startswith("repr:"))
async def cb_replace_reason(call: CallbackQuery, bot: Bot):
    lang = await _lang(call.from_user.id)
    _, cid, reason = call.data.split(":")
    config_id = int(cid)
    cfg = await db.get_config(config_id)
    if not cfg or cfg["user_id"] != call.from_user.id or cfg["status"] != "sold":
        await call.answer(_tt(lang, "Активный конфиг не найден 😔", "Active config not found 😔"), show_alert=True)
        return

    if reason == "country":
        # Смена страны — только через одобрение админа. Сразу регион не выдаём.
        req_id = await db.create_region_change(call.from_user.id, config_id, cfg["region"])
        u = await db.get_user(call.from_user.id) or {}
        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Одобрить", callback_data=f"rcq:ok:{req_id}")
        kb.button(text="❌ Отклонить", callback_data=f"rcq:no:{req_id}")
        kb.button(text="👤 Карточка", callback_data=f"acard:{call.from_user.id}")
        kb.adjust(2, 1)
        await _notify_admins(bot, texts.admin_region_change(
            call.from_user.id, config_id, cfg["region"],
            username=u.get("username"), full_name=u.get("full_name")),
            reply_markup=kb.as_markup())
        await _edit(call, texts.region_change_requested(lang), back_to_menu_kb(lang))
        await call.answer()
        return

    # та же страна — выдаём другой конфиг из склада
    await _do_replace(call, bot, config_id, cfg["region"], reason, lang)


@router.callback_query(F.data.startswith("repc:"))
async def cb_replace_country(call: CallbackQuery, bot: Bot):
    lang = await _lang(call.from_user.id)
    _, cid, region = call.data.split(":", 2)
    config_id = int(cid)
    cfg = await db.get_config(config_id)
    if not cfg or cfg["user_id"] != call.from_user.id or cfg["status"] != "sold":
        await call.answer(_tt(lang, "Активный конфиг не найден 😔", "Active config not found 😔"), show_alert=True)
        return
    await _do_replace(call, bot, config_id, region, "country", lang)


async def _do_replace(call: CallbackQuery, bot: Bot, config_id: int, region: str, reason: str, lang: str):
    new = await db.replace_config(config_id, region, reason)
    if not new:
        await call.answer()
        await _edit(call, _tt(lang,
            f"😔 В регионе сейчас нет свободных конфигов для замены. "
            f"Попробуй другую страну или загляни чуть позже.",
            f"😔 No free configs to replace right now. Try another country or check back later."),
            replace_reasons_kb(config_id, lang))
        # сообщим админам, что нужен запас под замену
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id,
                    f"⚠️ Замена не удалась: нет свободных в <b>{region}</b>. Клиент ждёт замену.")
            except Exception:
                pass
        return

    await call.answer(_tt(lang, "Готово! Выдаю новый конфиг.", "Done! Sending a new config."))
    try:
        exp = datetime.fromisoformat(new["expires_at"]) if new.get("expires_at") else now()
    except (ValueError, TypeError):
        exp = now()
    await _edit(call, _tt(lang, "✅ <b>Конфиг заменён!</b> Срок действия сохранён.",
                          "✅ <b>Config replaced!</b> Your expiry date is kept."),
                back_to_menu_kb(lang))
    await _send_config(call.message, new, exp, 1, 1, lang)

    # пинг админу: какой аккаунт-источник дал плохой конфиг
    src = new.get("old_source") or "не указан"
    reason_txt = _REASON_RU.get(reason, reason)
    note = ""
    if new.get("old_region") and new["old_region"] != region:
        note = f"\n🌍 Страна изменена: {new['old_region']} → {region}"
    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id,
                f"🔁 <b>Замена конфига</b>\n"
                f"Клиент: <code>{call.from_user.id}</code>\n"
                f"Старый #{config_id} ({new.get('old_region')}) · аккаунт-источник: <b>{src}</b>\n"
                f"Причина: {reason_txt}{note}\n"
                f"Выдан новый #{new['id']} ({region}).\n"
                f"<i>Замени испорченный конфиг на аккаунте «{src}» в WireCat.</i>")
        except Exception:
            pass
