"""Админка с кнопочной панелью: статистика, серверы, промокоды, рассылка."""

import asyncio
import csv
import io
import logging

from aiogram import Bot, F, Router
from aiogram.filters import Command, CommandObject
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import BufferedInputFile, CallbackQuery, Message
from aiogram.utils.keyboard import InlineKeyboardBuilder

import db
import store
import ab
import texts
from config import PERIOD_DAYS, PLAN_ORDER, PLANS
from filters import IsAdmin

router = Router()
router.message.filter(IsAdmin())
router.callback_query.filter(IsAdmin())
log = logging.getLogger(__name__)


class AddConfig(StatesGroup):
    name = State()
    source = State()
    waiting = State()


class Broadcast(StatesGroup):
    waiting = State()


class PromoCreate(StatesGroup):
    waiting = State()


class PromoWiz(StatesGroup):
    value = State()
    code = State()


class UserAdmin(StatesGroup):
    lookup = State()
    custom = State()


class MsgUser(StatesGroup):
    waiting = State()


class PriceEdit(StatesGroup):
    waiting = State()


class RegionAdmin(StatesGroup):
    add = State()
    rename = State()


class Restock(StatesGroup):
    amount = State()
    url = State()
    source = State()
    configs = State()


# ============ ПАНЕЛЬ ============

def panel_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="📊 Статистика", callback_data="ap:stats")
    kb.button(text="🌍 Серверы", callback_data="ap:servers")
    kb.button(text="➕ Добавить серверы", callback_data="ap:add")
    kb.button(text="🗑 Удалить серверы", callback_data="ap:del")
    kb.button(text="🎟 Промокоды", callback_data="ap:promo")
    kb.button(text="📣 Рассылка", callback_data="ap:bcast")
    kb.button(text="👤 Юзеры", callback_data="ap:users")
    kb.button(text="📨 Предзаказы", callback_data="ap:preorders")
    kb.button(text="💸 Выплаты", callback_data="ap:payouts")
    kb.button(text="📈 Топ рефералов", callback_data="ap:topref")
    kb.button(text="📥 Экспорт CSV", callback_data="ap:export")
    kb.button(text="💲 Цены", callback_data="ap:prices")
    kb.button(text="🗂 Регионы", callback_data="ap:regions")
    kb.button(text="📊 Метрики", callback_data="ap:metrics")
    kb.button(text="🧪 A/B", callback_data="ap:ab")
    kb.button(text="📦 Закупки", callback_data="ap:restock")
    kb.button(text="🔄 Обновить", callback_data="ap:home")
    kb.adjust(2, 2, 2, 2, 2, 2, 2, 2, 1)
    return kb.as_markup()


def back_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В админку", callback_data="ap:home")
    return kb.as_markup()


PANEL_TITLE = "🛠 <b>Панель управления</b>\n\nВыбери раздел 👇"


@router.message(Command("admin"))
async def cmd_admin(message: Message):
    await message.answer(PANEL_TITLE, reply_markup=panel_kb())


@router.callback_query(F.data == "ap:home")
async def ap_home(call: CallbackQuery, state: FSMContext):
    await state.clear()
    try:
        await call.message.edit_text(PANEL_TITLE, reply_markup=panel_kb())
    except Exception:
        await call.message.answer(PANEL_TITLE, reply_markup=panel_kb())
    await call.answer()


# ---- статистика ----

def _fmt_money(s, c):
    return f"{s} ₽ ({c})"


@router.callback_query(F.data == "ap:stats")
async def ap_stats(call: CallbackQuery):
    st = await db.stats_extended()
    lines = ["📊 <b>Статистика</b>\n"]
    lines.append("💰 <b>Выручка (₽):</b>")
    lines.append(f"• Сегодня: <b>{_fmt_money(*st['day'])}</b>")
    lines.append(f"• 7 дней: <b>{_fmt_money(*st['week'])}</b>")
    lines.append(f"• 30 дней: <b>{_fmt_money(*st['month'])}</b>")
    lines.append(f"• Всего: <b>{_fmt_money(*st['all'])}</b>")
    # Stars отдельно, если были
    stars = [x for x in st["by_currency"] if x["currency"] == "XTR"]
    if stars:
        lines.append(f"⭐️ Stars всего: <b>{stars[0]['s']}</b> ({stars[0]['c']})")
    lines.append("")
    lines.append(f"👥 Пользователей: <b>{st['users']}</b>")
    lines.append(f"💼 Остаток баланса у всех (₽): <b>{st.get('total_balance', 0)}</b>")
    lines.append(f"📨 Активных предзаказов: <b>{st.get('pending_preorders', 0)}</b>")
    lines.append(f"✅ Активных подписок: <b>{st['active_subs']}</b>")
    lines.append(f"🟢 Свободно серверов: <b>{st['free_paid']}</b> (платных) · <b>{st['free_trial']}</b> (пробных)")
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb())
    await call.answer()


# ---- A/B эксперименты ----

@router.callback_query(F.data == "ap:ab")
async def ap_ab(call: CallbackQuery):
    exp = ab.active_experiment()
    if not exp:
        await call.message.edit_text(
            "🧪 <b>A/B тесты</b>\n\nСейчас эксперимент выключен.\n"
            "Включи его в <code>.env</code>: <code>AB_EXPERIMENT=trial_len</code> "
            "(и перезапусти бота).\n\n"
            "Бакетинг 50/50 по user_id, вариант фиксируется при первом старте.",
            reply_markup=back_kb())
        await call.answer()
        return
    rows = await db.ab_report(exp)
    lines = [f"🧪 <b>A/B: {ab.experiment_title(exp)}</b>",
             f"Метрика: {ab.AB_EXPERIMENTS[exp].get('metric', 'конверсия в оплату')}", "➖➖➖➖➖➖➖➖➖➖"]
    if not rows:
        lines.append("Пока нет данных — нужны новые пользователи после включения теста.")
    else:
        for r in rows:
            users = r["users"] or 0
            trials = r["trials"] or 0
            paid = r["paid"] or 0
            conv = (paid / users * 100) if users else 0
            conv_t = (paid / trials * 100) if trials else 0
            params = ab.AB_EXPERIMENTS[exp]["variants"].get(r["variant"], {})
            ptxt = ", ".join(f"{k}={v}" for k, v in params.items()) or "—"
            lines.append(
                f"<b>Вариант {r['variant']}</b> ({ptxt})\n"
                f"   👥 юзеров: {users} · 🧪 триал: {trials} · 💳 оплатили: {paid}\n"
                f"   📈 конверсия: <b>{conv:.1f}%</b> от всех · {conv_t:.1f}% от взявших триал")
        lines.append("➖➖➖➖➖➖➖➖➖➖")
        lines.append("<i>Победитель — у кого выше конверсия при сопоставимом числе юзеров.</i>")
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb())
    await call.answer()

@router.callback_query(F.data == "ap:servers")
async def ap_servers(call: CallbackQuery):
    per_region, _, _, _ = await db.stats()
    lines = ["🌍 <b>Серверы по регионам</b>\n"]
    if not per_region:
        lines.append("Пока нет ни одного сервера. Жми «➕ Добавить серверы».")
    else:
        for r in per_region:
            mark = "⭐️" if r["prem"] else ("🧪" if r["tr"] else "▫️")
            lines.append(f"{mark} <b>{r['region']}</b>: 🟢{r['free']} 🟡{r['reserved']} 🔴{r['sold']} ⚫️{r['expired']}")
        lines.append("\n<i>🟢свободно 🟡бронь 🔴продано ⚫️истёк · ⭐️premium 🧪trial</i>")
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb())
    await call.answer()


# ---- добавление серверов ----

async def _add_pick_kb(mode: str):
    """mode: 'paid' — обычный/premium из каталога; 'trial' — в триал-пул."""
    rows = await db.catalog_with_stock()
    kb = InlineKeyboardBuilder()
    prefix = "addtpick" if mode == "trial" else "addpick"
    for r in rows:
        star = "⭐️" if r["is_premium"] else "▫️"
        kb.button(text=f"{star} {r['region']} (🟢{r['free']})", callback_data=f"{prefix}:{r['region']}")
    if mode == "paid":
        kb.button(text="🧪 В триал-пул", callback_data="ap:addtrial")
        kb.button(text="✏️ Другой регион (ввести вручную)", callback_data="ap:addtype")
    else:
        kb.button(text="⬅️ К обычным регионам", callback_data="ap:add")
    kb.button(text="⬅️ В админку", callback_data="ap:home")
    kb.adjust(2)
    return kb.as_markup()


@router.callback_query(F.data == "ap:add")
async def ap_add(call: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = await _add_pick_kb("paid")
    await call.message.edit_text(
        "➕ <b>Добавление серверов</b>\n\n"
        "Выбери регион из каталога — premium определится автоматически. "
        "После выбора просто пришли <code>.conf</code> файлы.",
        reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "ap:addtrial")
async def ap_add_trial(call: CallbackQuery, state: FSMContext):
    await state.clear()
    kb = await _add_pick_kb("trial")
    await call.message.edit_text(
        "🧪 <b>Триал-пул</b>\n\nВыбери регион, в который зальём пробные конфиги "
        "(их получают только в бесплатном пробном периоде):",
        reply_markup=kb)
    await call.answer()


async def _start_upload(call: CallbackQuery, state: FSMContext, region: str, premium: bool, trial: bool):
    await state.set_state(AddConfig.source)
    await state.update_data(region=region, premium=premium, trial=trial, count=0)
    tags = []
    if premium:
        tags.append("⭐️ PREMIUM")
    if trial:
        tags.append("🧪 TRIAL")
    tag = ", ".join(tags) if tags else "обычный"
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Без источника", callback_data="ap:srcskip")
    kb.button(text="⬅️ В админку", callback_data="ap:home")
    kb.adjust(1)
    await call.message.edit_text(
        f"📥 Регион: <b>{region}</b> ({tag})\n\n"
        "👤 С какого <b>аккаунта</b> ты берёшь эти конфиги? Напиши имя/метку "
        "(например <code>acc_1</code> или <code>+79991234567</code>) — "
        "потом увидишь её при замене и поймёшь, куда идти за новым.\n\n"
        "Или нажми «⏭ Без источника».",
        reply_markup=kb.as_markup())
    await call.answer()


async def _ask_configs(target, state: FSMContext):
    data = await state.get_data()
    await state.set_state(AddConfig.waiting)
    src = data.get("source")
    src_line = f"👤 Источник: <b>{src}</b>\n" if src else ""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Готово", callback_data="ap:adddone")
    kb.button(text="⬅️ В админку", callback_data="ap:home")
    kb.adjust(1)
    await target.answer(
        f"📥 Регион: <b>{data.get('region')}</b>\n{src_line}\n"
        "Присылай <code>.conf</code> файлы или текст — каждое сообщение = 1 конфиг. "
        "Невалидные WireGuard-конфиги не попадут в продажу.\n"
        "Когда закончишь — «✅ Готово» или /done.",
        reply_markup=kb.as_markup())


@router.callback_query(F.data == "ap:srcskip")
async def ap_src_skip(call: CallbackQuery, state: FSMContext):
    await state.update_data(source=None)
    await _ask_configs(call.message, state)
    await call.answer()


@router.message(AddConfig.source, Command("cancel"))
async def add_source_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=panel_kb())


@router.message(AddConfig.source, F.text)
async def add_source(message: Message, state: FSMContext):
    await state.update_data(source=message.text.strip())
    await _ask_configs(message, state)


@router.callback_query(F.data.startswith("addpick:"))
async def add_pick(call: CallbackQuery, state: FSMContext):
    region = call.data.split(":", 1)[1]
    await _start_upload(call, state, region, store.is_premium_region(region), False)


@router.callback_query(F.data.startswith("addtpick:"))
async def add_trial_pick(call: CallbackQuery, state: FSMContext):
    region = call.data.split(":", 1)[1]
    await _start_upload(call, state, region, False, True)


@router.callback_query(F.data == "ap:adddone")
async def add_done_btn(call: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    await call.message.edit_text(
        f"✅ Готово. Добавлено: <b>{data.get('count', 0)}</b> в <b>{data.get('region')}</b>.",
        reply_markup=back_kb())
    await call.answer()


@router.callback_query(F.data == "ap:addtype")
async def ap_add_type(call: CallbackQuery, state: FSMContext):
    await state.set_state(AddConfig.name)
    await call.message.edit_text(
        "✏️ <b>Свой регион</b>\n\n"
        "Напиши название региона. Для особых — добавь тег:\n"
        "• <code>Испания</code> — обычный\n"
        "• <code>Япония premium</code> — premium-сервер\n"
        "• <code>Тест trial</code> — пробный (для триала)\n\n"
        "Или /cancel для отмены.",
        reply_markup=back_kb(),
    )
    await call.answer()


@router.message(AddConfig.name, F.text, ~F.text.startswith("/"))
async def add_name(message: Message, state: FSMContext):
    parts = message.text.strip().split()
    is_premium = is_trial = False
    while parts and parts[-1].lower() in ("premium", "прем", "премиум", "trial", "триал", "тест", "пробный"):
        fl = parts.pop().lower()
        if fl in ("premium", "прем", "премиум"):
            is_premium = True
        else:
            is_trial = True
    region = " ".join(parts).strip()
    if not region:
        await message.answer("Укажи название региона.")
        return
    await state.set_state(AddConfig.source)
    await state.update_data(region=region, premium=is_premium, trial=is_trial, count=0)
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Без источника", callback_data="ap:srcskip")
    kb.adjust(1)
    await message.answer(
        f"📥 Регион: <b>{region}</b>\n\n"
        "👤 С какого <b>аккаунта</b> ты берёшь эти конфиги? Напиши имя/метку — "
        "увидишь её при замене. Или «⏭ Без источника».",
        reply_markup=kb.as_markup())


@router.message(AddConfig.waiting, Command("done"))
async def add_done(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В админку", callback_data="ap:home")
    await message.answer(
        f"✅ Готово. Добавлено: <b>{data.get('count', 0)}</b> в <b>{data.get('region')}</b>.",
        reply_markup=kb.as_markup(),
    )


@router.message(AddConfig.waiting, Command("cancel"))
@router.message(AddConfig.name, Command("cancel"))
async def add_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=panel_kb())


@router.message(AddConfig.waiting, F.document)
async def add_doc(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    buf = await bot.download(message.document)
    text = buf.read().decode(errors="replace").strip()
    if not text:
        await message.answer("Пустой файл, пропускаю.")
        return
    _, valid = await db.add_config(data["region"], text, data["premium"], data["trial"], data.get("source"))
    if not valid:
        await message.answer("⏭ Пропущен: это не похоже на рабочий WireGuard-конфиг (в продажу не пойдёт).")
        return
    count = data.get("count", 0) + 1
    await state.update_data(count=count)
    await message.answer(f"➕ Добавлен #{count} ({data['region']}). /done — закончить.")


@router.message(AddConfig.waiting, F.text, ~F.text.startswith("/"))
async def add_text(message: Message, state: FSMContext):
    data = await state.get_data()
    _, valid = await db.add_config(data["region"], message.text.strip(), data["premium"],
                                   data["trial"], data.get("source"))
    if not valid:
        await message.answer("⏭ Пропущен: это не похоже на рабочий WireGuard-конфиг (в продажу не пойдёт).")
        return
    count = data.get("count", 0) + 1
    await state.update_data(count=count)
    await message.answer(f"➕ Добавлен #{count} ({data['region']}). /done — закончить.")


# ---- удаление серверов ----

@router.callback_query(F.data == "ap:del")
async def ap_del(call: CallbackQuery):
    regions = await db.all_regions()
    kb = InlineKeyboardBuilder()
    if not regions:
        await call.message.edit_text("Нечего удалять — серверов нет.", reply_markup=back_kb())
        await call.answer()
        return
    for r in regions:
        kb.button(text=f"🗑 {r}", callback_data=f"adelpick:{r}")
    kb.button(text="⬅️ В админку", callback_data="ap:home")
    kb.adjust(1)
    await call.message.edit_text(
        "🗑 <b>Удаление свободных конфигов</b>\n\nВыбери регион (удалятся только свободные, проданные не тронем):",
        reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("adelpick:"))
async def ap_del_pick(call: CallbackQuery):
    region = call.data.split(":", 1)[1]
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Да, удалить", callback_data=f"adel:{region}")
    kb.button(text="⬅️ Отмена", callback_data="ap:del")
    kb.adjust(1)
    await call.message.edit_text(f"Удалить все свободные конфиги <b>{region}</b>?", reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("adel:"))
async def cb_delete(call: CallbackQuery):
    region = call.data.split(":", 1)[1]
    n = await db.delete_free_configs(region)
    await call.message.edit_text(f"🗑 Удалено: <b>{n}</b> ({region}).", reply_markup=back_kb())
    await call.answer()


# ---- промокоды ----

async def _promo_text_kb():
    promos = await db.list_promos()
    lines = ["🎟 <b>Промокоды</b>\n"]
    kb = InlineKeyboardBuilder()
    if not promos:
        lines.append("Пока нет ни одного промокода.")
    else:
        for p in promos:
            state = "🟢" if p["active"] else "🔴"
            uses = f"{p['used']}/{p['max_uses']}" if p["max_uses"] else f"{p['used']}/∞"
            if p["kind"] == "balance":
                val = f"+{p['amount_rub']} ₽ на баланс"
            else:
                val = f"−{p['percent']}% скидка"
            lines.append(f"{state} <code>{p['code']}</code> — {val} · {uses}")
            kb.button(text=f"{'⏸' if p['active'] else '▶️'} {p['code']}", callback_data=f"prtg:{p['code']}")
            kb.button(text=f"🗑 {p['code']}", callback_data=f"prdel:{p['code']}")
        kb.adjust(2)
    kb.button(text="➕ Создать промокод", callback_data="prnew")
    kb.button(text="⬅️ В админку", callback_data="ap:home")
    kb.adjust(2, 1, 1)
    return "\n".join(lines), kb.as_markup()


@router.callback_query(F.data == "ap:promo")
async def ap_promo(call: CallbackQuery):
    text, kb = await _promo_text_kb()
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


def _gen_promo_code(n=7):
    import random
    import string
    return "".join(random.choices(string.ascii_uppercase + string.digits, k=n))


def _pw_type_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="💯 Скидка %", callback_data="pw:t:discount")
    kb.button(text="💰 На баланс ₽", callback_data="pw:t:balance")
    kb.button(text="✍️ Ввести вручную (текстом)", callback_data="prmanual")
    kb.button(text="⬅️ Назад", callback_data="ap:promo")
    kb.adjust(2, 1, 1)
    return kb.as_markup()


def _pw_value_kb(kind):
    kb = InlineKeyboardBuilder()
    presets = [10, 15, 20, 25, 30, 50] if kind == "discount" else [50, 100, 200, 500, 1000]
    for v in presets:
        label = f"−{v}%" if kind == "discount" else f"+{v} ₽"
        kb.button(text=label, callback_data=f"pw:v:{kind}:{v}")
    kb.button(text="✍️ Своё значение", callback_data=f"pw:vc:{kind}")
    kb.button(text="⬅️ Назад", callback_data="prnew")
    kb.adjust(3, 3, 1, 1)
    return kb.as_markup()


def _pw_limit_kb(kind, value):
    kb = InlineKeyboardBuilder()
    for lim in (1, 10, 50, 100):
        kb.button(text=f"{lim} шт.", callback_data=f"pw:l:{kind}:{value}:{lim}")
    kb.button(text="♾ Без лимита", callback_data=f"pw:l:{kind}:{value}:0")
    kb.button(text="⬅️ Назад", callback_data=f"pw:t:{kind}")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


def _pw_code_kb(kind, value, lim):
    kb = InlineKeyboardBuilder()
    kb.button(text="🎲 Сгенерировать код", callback_data=f"pw:gen:{kind}:{value}:{lim}")
    kb.button(text="✍️ Задать свой код", callback_data=f"pw:code:{kind}:{value}:{lim}")
    kb.button(text="⬅️ Назад", callback_data=f"pw:v:{kind}:{value}")
    kb.adjust(1)
    return kb.as_markup()


def _pw_summary(kind, value, lim):
    v = f"скидка −{value}%" if kind == "discount" else f"+{value} ₽ на баланс"
    limit_s = f"{lim} активаций" if lim else "без лимита"
    return f"<b>{v}</b>, {limit_s}"


async def _create_and_show(message_or_call, code, kind, value, lim):
    code = code.upper()
    if kind == "discount":
        await db.create_promo(code, "discount", percent=value, max_uses=lim)
    else:
        await db.create_promo(code, "balance", amount_rub=value, max_uses=lim)
    text, kb = await _promo_text_kb()
    note = f"✅ Промокод <code>{code}</code> создан — {_pw_summary(kind, value, lim)}."
    target = message_or_call.message if isinstance(message_or_call, CallbackQuery) else message_or_call
    await target.answer(note)
    await target.answer(text, reply_markup=kb)


@router.callback_query(F.data == "prnew")
async def promo_new(call: CallbackQuery, state: FSMContext):
    await state.clear()
    await call.message.edit_text(
        "➕ <b>Новый промокод</b>\n\nВыбери тип 👇", reply_markup=_pw_type_kb())
    await call.answer()


@router.callback_query(F.data == "prmanual")
async def promo_manual(call: CallbackQuery, state: FSMContext):
    await state.set_state(PromoCreate.waiting)
    await call.message.edit_text(
        "✍️ <b>Промокод вручную</b>\n\n"
        "<b>Скидка %:</b> <code>КОД скидка ПРОЦЕНТ ЛИМИТ</code>\n"
        "  напр. <code>SALE20 скидка 20 100</code>\n\n"
        "<b>На баланс ₽:</b> <code>КОД баланс СУММА ЛИМИТ</code>\n"
        "  напр. <code>GIFT100 баланс 100 50</code>\n\n"
        "ЛИМИТ = сколько раз можно активировать (0 = без лимита).\n"
        "/cancel — отмена.",
        reply_markup=back_kb())
    await call.answer()


@router.callback_query(F.data.startswith("pw:t:"))
async def pw_type(call: CallbackQuery):
    kind = call.data.split(":")[2]
    title = "💯 Скидка" if kind == "discount" else "💰 Бонус на баланс"
    await call.message.edit_text(f"{title}\n\nВыбери значение 👇", reply_markup=_pw_value_kb(kind))
    await call.answer()


@router.callback_query(F.data.startswith("pw:vc:"))
async def pw_value_custom(call: CallbackQuery, state: FSMContext):
    kind = call.data.split(":")[2]
    await state.set_state(PromoWiz.value)
    await state.update_data(kind=kind)
    unit = "процент скидки (1–100)" if kind == "discount" else "сумму в рублях"
    await call.message.edit_text(f"✍️ Введи {unit} числом:\n/cancel — отмена.", reply_markup=back_kb())
    await call.answer()


@router.message(PromoWiz.value, Command("cancel"))
async def pw_value_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=panel_kb())


@router.message(PromoWiz.value, F.text)
async def pw_value_typed(message: Message, state: FSMContext):
    data = await state.get_data()
    kind = data.get("kind", "discount")
    try:
        value = int(message.text.strip())
    except ValueError:
        await message.answer("Нужно число. Попробуй ещё раз или /cancel.")
        return
    if kind == "discount" and not (1 <= value <= 100):
        await message.answer("Процент — от 1 до 100. Ещё раз или /cancel.")
        return
    if kind == "balance" and value < 1:
        await message.answer("Сумма должна быть больше 0. Ещё раз или /cancel.")
        return
    await state.clear()
    await message.answer(f"Значение: {_pw_summary(kind, value, 0).split(',')[0]}\n\nТеперь выбери лимит 👇",
                         reply_markup=_pw_limit_kb(kind, value))


@router.callback_query(F.data.startswith("pw:v:"))
async def pw_value(call: CallbackQuery):
    _, _, kind, value = call.data.split(":")
    await call.message.edit_text(
        f"{_pw_summary(kind, int(value), 0).split(',')[0]}\n\nТеперь выбери лимит 👇",
        reply_markup=_pw_limit_kb(kind, int(value)))
    await call.answer()


@router.callback_query(F.data.startswith("pw:l:"))
async def pw_limit(call: CallbackQuery):
    _, _, kind, value, lim = call.data.split(":")
    await call.message.edit_text(
        f"Почти готово: {_pw_summary(kind, int(value), int(lim))}\n\nКакой код у промокода?",
        reply_markup=_pw_code_kb(kind, int(value), int(lim)))
    await call.answer()


@router.callback_query(F.data.startswith("pw:gen:"))
async def pw_gen(call: CallbackQuery):
    _, _, kind, value, lim = call.data.split(":")
    await _create_and_show(call, _gen_promo_code(), kind, int(value), int(lim))
    await call.answer("✅")


@router.callback_query(F.data.startswith("pw:code:"))
async def pw_code_custom(call: CallbackQuery, state: FSMContext):
    _, _, kind, value, lim = call.data.split(":")
    await state.set_state(PromoWiz.code)
    await state.update_data(kind=kind, value=int(value), lim=int(lim))
    await call.message.edit_text("✍️ Введи код промокода (буквы/цифры):\n/cancel — отмена.",
                                 reply_markup=back_kb())
    await call.answer()


@router.message(PromoWiz.code, Command("cancel"))
async def pw_code_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=panel_kb())


@router.message(PromoWiz.code, F.text)
async def pw_code_typed(message: Message, state: FSMContext):
    data = await state.get_data()
    code = message.text.strip().split()[0]
    if not code.replace("_", "").isalnum():
        await message.answer("Код — только буквы и цифры. Ещё раз или /cancel.")
        return
    await state.clear()
    await _create_and_show(message, code, data["kind"], data["value"], data["lim"])


@router.message(PromoCreate.waiting, Command("cancel"))
async def promo_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=panel_kb())


@router.message(PromoCreate.waiting, F.text)
async def promo_save(message: Message, state: FSMContext):
    parts = message.text.strip().split()
    if len(parts) < 3:
        await message.answer("Формат: <code>КОД скидка 20 100</code> или <code>КОД баланс 100 50</code>")
        return
    code = parts[0]
    kind_raw = parts[1].lower()
    try:
        value = int(parts[2])
        max_uses = int(parts[3]) if len(parts) > 3 else 0
    except ValueError:
        await message.answer("Значение и лимит — числа. Пример: <code>SALE20 скидка 20 100</code>")
        return
    if kind_raw in ("скидка", "discount", "%"):
        if not (1 <= value <= 100):
            await message.answer("Процент скидки — от 1 до 100.")
            return
        await db.create_promo(code, "discount", percent=value, max_uses=max_uses)
        info = f"скидка −{value}%"
    elif kind_raw in ("баланс", "balance", "₽"):
        if value < 1:
            await message.answer("Сумма должна быть больше 0.")
            return
        await db.create_promo(code, "balance", amount_rub=value, max_uses=max_uses)
        info = f"+{value} ₽ на баланс"
    else:
        await message.answer("Тип: <b>скидка</b> или <b>баланс</b>. Пример: <code>SALE20 скидка 20 100</code>")
        return
    await state.clear()
    text, kb = await _promo_text_kb()
    await message.answer(f"✅ Промокод <code>{code.upper()}</code> создан ({info}).")
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("prtg:"))
async def promo_toggle(call: CallbackQuery):
    await db.toggle_promo(call.data.split(":", 1)[1])
    text, kb = await _promo_text_kb()
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("Переключено")


@router.callback_query(F.data.startswith("prdel:"))
async def promo_delete(call: CallbackQuery):
    await db.delete_promo(call.data.split(":", 1)[1])
    text, kb = await _promo_text_kb()
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("Удалён")


# ---- рассылка ----

@router.callback_query(F.data == "ap:bcast")
async def ap_bcast(call: CallbackQuery, state: FSMContext):
    await state.set_state(Broadcast.waiting)
    await call.message.edit_text(
        "📣 <b>Рассылка</b>\n\nПришли сообщение (текст/фото/видео) — оно уйдёт всем пользователям.\n/cancel — отмена.",
        reply_markup=back_kb())
    await call.answer()


@router.message(Broadcast.waiting, Command("cancel"))
async def bcast_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Рассылка отменена.", reply_markup=panel_kb())


@router.message(Broadcast.waiting)
async def bcast_run(message: Message, state: FSMContext, bot: Bot):
    await state.clear()
    user_ids = await db.all_user_ids()
    await message.answer(f"📣 Отправляю {len(user_ids)} пользователям…")
    ok = fail = 0
    for uid in user_ids:
        try:
            await bot.copy_message(uid, message.chat.id, message.message_id)
            ok += 1
        except Exception:
            fail += 1
        await asyncio.sleep(0.05)
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ В админку", callback_data="ap:home")
    await message.answer(f"✅ Доставлено: {ok}\n❌ Ошибок: {fail}", reply_markup=kb.as_markup())


# ============ КОМАНДЫ-АЛИАСЫ (на случай привычки) ============

@router.message(Command("stats"))
async def cmd_stats(message: Message):
    await message.answer(PANEL_TITLE, reply_markup=panel_kb())


@router.message(Command("add_config"))
async def cmd_add_alias(message: Message, command: CommandObject, state: FSMContext):
    args = (command.args or "").strip()
    if not args:
        await message.answer("Открой панель: /admin → ➕ Добавить серверы")
        return
    # старое поведение для совместимости
    fake = Message.model_construct(text=args)
    parts = args.split()
    is_premium = is_trial = False
    while parts and parts[-1].lower() in ("premium", "прем", "премиум", "trial", "триал", "тест", "пробный"):
        fl = parts.pop().lower()
        if fl in ("premium", "прем", "премиум"):
            is_premium = True
        else:
            is_trial = True
    region = " ".join(parts).strip()
    if not region:
        await message.answer("Укажи регион.")
        return
    await state.set_state(AddConfig.waiting)
    await state.update_data(region=region, premium=is_premium, trial=is_trial, count=0)
    await message.answer(f"📥 Регион: <b>{region}</b>. Присылай конфиги, /done — закончить.")


# ============ УПРАВЛЕНИЕ ПОЛЬЗОВАТЕЛЯМИ ============

def _flag_status(u: dict) -> str:
    marks = []
    if u.get("banned"):
        marks.append("⛔️ забанен")
    if u.get("autopay"):
        marks.append("🔁 автоплатёж")
    return (" · ".join(marks)) if marks else "—"


async def _user_card(uid: int):
    u = await db.user_card(uid)
    if not u:
        return None, None
    name = u.get("full_name") or "—"
    uname = f"@{u['username']}" if u.get("username") else "—"
    lines = [
        f"👤 <b>{name}</b> ({uname})",
        f"🆔 <code>{u['user_id']}</code>",
        "",
        f"💰 Баланс: <b>{u.get('balance_rub', 0)} ₽</b>",
        f"🎁 Бонус-дни: <b>{u.get('bonus_days', 0)}</b>",
        f"💳 Всего потрачено: <b>{u.get('spent', 0)} ₽</b>",
        f"👥 Приглашено: <b>{u.get('invited', 0)}</b> · реф-доход {u.get('ref_earned_rub', 0)} ₽",
        f"💵 Реф-баланс к выводу: <b>{u.get('ref_cash_rub', 0)} ₽</b>",
        f"🧪 Триал: {'использован' if u.get('trial_used') else 'нет'}",
        f"⚙️ Статус: {_flag_status(u)}",
        "",
        "<b>Подписки:</b>",
    ]
    subs = u.get("subs", [])
    if not subs:
        lines.append("— нет")
    else:
        for s in subs[:10]:
            st = "✅" if s["status"] == "sold" else "⛔️"
            exp = (s["expires_at"] or "")[:10]
            lines.append(f"{st} {s['region']} — до {exp}")

    kb = InlineKeyboardBuilder()
    kb.button(text="➕ 7 дней", callback_data=f"au:d7:{uid}")
    kb.button(text="➕ 30 дней", callback_data=f"au:d30:{uid}")
    kb.button(text="➕ 100 ₽", callback_data=f"au:b100:{uid}")
    kb.button(text="➕ 500 ₽", callback_data=f"au:b500:{uid}")
    if u.get("banned"):
        kb.button(text="✅ Разбанить", callback_data=f"au:unban:{uid}")
    else:
        kb.button(text="⛔️ Забанить", callback_data=f"au:ban:{uid}")
    kb.button(text="💸 Рефанд последнего", callback_data=f"au:refund:{uid}")
    kb.button(text="👑 Откл. премиум", callback_data=f"au:noprem:{uid}")
    kb.button(text="✉️ Написать", callback_data=f"amsg:{uid}")
    kb.button(text="✏️ Своя сумма/дни", callback_data=f"au:custom:{uid}")
    kb.button(text="⬅️ К списку", callback_data="ap:users")
    kb.adjust(2, 2, 1, 1, 1, 1, 1)
    return "\n".join(lines), kb.as_markup()


async def _users_page(offset: int = 0, per: int = 8):
    total = await db.count_users()
    rows = await db.list_users(per, offset)
    lines = [f"👤 <b>Пользователи</b> — всего {total}\n",
             "<i>Выбери юзера, чтобы открыть карточку и управлять им.</i>\n"]
    kb = InlineKeyboardBuilder()
    for u in rows:
        name = u.get("full_name") or "—"
        uname = f"@{u['username']}" if u.get("username") else f"<code>{u['user_id']}</code>"
        lines.append(f"• {name} ({uname}) · 💰{u.get('balance_rub', 0)} ₽")
        label = (u.get("full_name") or (f"@{u['username']}" if u.get("username") else str(u["user_id"])))[:24]
        kb.button(text=f"👤 {label}", callback_data=f"acard:{u['user_id']}")
    nav = []
    if offset > 0:
        kb.button(text="⬅️ Назад", callback_data=f"ausers:{max(offset - per, 0)}")
        nav.append(1)
    if offset + per < total:
        kb.button(text="➡️ Дальше", callback_data=f"ausers:{offset + per}")
        nav.append(1)
    kb.button(text="🔎 Найти по ID / @username", callback_data="ausearch")
    kb.button(text="⬅️ В админку", callback_data="ap:home")
    rows_n = len(rows)
    sizes = [1] * rows_n + ([len(nav)] if nav else []) + [1, 1]
    kb.adjust(*sizes)
    return "\n".join(lines), kb.as_markup()


@router.callback_query(F.data == "ap:users")
async def ap_users(call: CallbackQuery, state: FSMContext):
    await state.clear()
    text, kb = await _users_page(0)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("ausers:"))
async def ap_users_page(call: CallbackQuery):
    offset = int(call.data.split(":")[1])
    text, kb = await _users_page(offset)
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        pass
    await call.answer()


@router.callback_query(F.data == "ausearch")
async def ap_users_search(call: CallbackQuery, state: FSMContext):
    await state.set_state(UserAdmin.lookup)
    await call.message.edit_text(
        "🔎 <b>Поиск пользователя</b>\n\nПришли <b>ID</b> или <b>@username</b>.\n/cancel — отмена.",
        reply_markup=back_kb())
    await call.answer()


@router.message(Command("user"))
async def cmd_user(message: Message, command: CommandObject):
    q = (command.args or "").strip()
    if not q:
        await message.answer("Использование: <code>/user 123456</code> или <code>/user @username</code>")
        return
    await _show_user_by_query(message, q)


@router.message(UserAdmin.lookup, Command("cancel"))
async def user_lookup_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=panel_kb())


@router.message(UserAdmin.lookup, F.text)
async def user_lookup(message: Message, state: FSMContext):
    await state.clear()
    await _show_user_by_query(message, message.text.strip())


async def _show_user_by_query(message: Message, q: str):
    u = await db.find_user(q)
    if not u:
        await message.answer("Пользователь не найден. Проверь ID или @username.", reply_markup=back_kb())
        return
    text, kb = await _user_card(u["user_id"])
    await message.answer(text, reply_markup=kb)


async def _refresh_card(call: CallbackQuery, uid: int):
    text, kb = await _user_card(uid)
    if text:
        try:
            await call.message.edit_text(text, reply_markup=kb)
        except Exception:
            await call.message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("au:"))
async def admin_user_action(call: CallbackQuery, state: FSMContext, bot: Bot):
    parts = call.data.split(":")
    action = parts[1]
    uid = int(parts[2])

    if action in ("d7", "d30"):
        days = 7 if action == "d7" else 30
        applied, region = await db.extend_active(uid, days)
        if not applied:
            await db.add_bonus_days(uid, days)
            note = f"добавлено {days} бонус-дней (применятся при покупке)"
        else:
            note = f"+{days} дней к подписке ({region})"
        try:
            await bot.send_message(uid, f"🎁 Администратор начислил тебе <b>{days}</b> дней!")
        except Exception:
            pass
        await call.answer(f"✅ {note}", show_alert=True)
        await _refresh_card(call, uid)
        return

    if action in ("b100", "b500"):
        amount = 100 if action == "b100" else 500
        await db.add_balance(uid, amount)
        try:
            await bot.send_message(uid, f"💰 Администратор начислил тебе <b>{amount} ₽</b> на баланс!")
        except Exception:
            pass
        await call.answer(f"✅ +{amount} ₽ на баланс", show_alert=True)
        await _refresh_card(call, uid)
        return

    if action == "ban":
        await db.set_banned(uid, True)
        await call.answer("⛔️ Забанен", show_alert=True)
        await _refresh_card(call, uid)
        return

    if action == "unban":
        await db.set_banned(uid, False)
        await call.answer("✅ Разбанен", show_alert=True)
        await _refresh_card(call, uid)
        return

    if action == "noprem":
        premium_plans = [k for k, v in PLANS.items() if v.get("premium_access")]
        n = await db.disable_premium(uid, premium_plans)
        try:
            await bot.send_message(uid, "ℹ️ Администратор отключил премиум-доступ на твоём аккаунте.")
        except Exception:
            pass
        await call.answer(f"👑 Премиум отключён (затронуто записей: {n})", show_alert=True)
        await _refresh_card(call, uid)
        return

    if action == "refund":
        order = await db.last_paid_order(uid)
        if not order:
            await call.answer("Нет оплаченных заказов для возврата.", show_alert=True)
            return
        await db.add_balance(uid, order["rub"])
        await db.set_order_status(order["id"], "refunded")
        try:
            await bot.send_message(uid, f"💸 Возврат <b>{order['rub']} ₽</b> зачислен на твой баланс.")
        except Exception:
            pass
        await call.answer(f"✅ Возвращено {order['rub']} ₽", show_alert=True)
        await _refresh_card(call, uid)
        return

    if action == "custom":
        await state.set_state(UserAdmin.custom)
        await state.update_data(uid=uid)
        await call.message.answer(
            "✏️ Формат: <code>дни 14</code> или <code>баланс 250</code>.\n"
            "Можно списывать: <code>дни -7</code>, <code>баланс -100</code>.\n/cancel — отмена.")
        await call.answer()
        return


@router.message(UserAdmin.custom, Command("cancel"))
async def user_custom_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=panel_kb())


@router.message(UserAdmin.custom, F.text)
async def user_custom_apply(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    uid = data.get("uid")
    await state.clear()
    parts = message.text.strip().split()
    if len(parts) < 2:
        await message.answer("Формат: <code>дни 14</code> или <code>баланс 250</code>.")
        return
    kind = parts[0].lower()
    try:
        val = int(parts[1])
    except ValueError:
        await message.answer("Значение должно быть числом.")
        return
    if kind in ("дни", "days", "день"):
        applied, region = await db.extend_active(uid, val)
        if val > 0 and not applied:
            await db.add_bonus_days(uid, val)
        verb = "начислено" if val >= 0 else "списано"
        await message.answer(f"✅ Дни обновлены ({verb} {abs(val)}) у <code>{uid}</code>.")
        try:
            if val >= 0:
                await bot.send_message(uid, f"🎁 Администратор начислил тебе <b>{val}</b> дней!")
            else:
                await bot.send_message(uid, f"ℹ️ Срок подписки изменён администратором (−{abs(val)} дн.).")
        except Exception:
            pass
    elif kind in ("баланс", "balance", "₽"):
        if val >= 0:
            await db.add_balance(uid, val)
        else:
            await db.deduct_balance(uid, -val)
        await message.answer(f"✅ Баланс изменён на {val} ₽ у <code>{uid}</code>.")
        try:
            sign = "начислил" if val >= 0 else "списал"
            await bot.send_message(uid, f"💰 Администратор {sign} <b>{abs(val)} ₽</b> на твоём балансе.")
        except Exception:
            pass
    else:
        await message.answer("Тип: <b>дни</b> или <b>баланс</b>.")
        return
    text, kb = await _user_card(uid)
    if text:
        await message.answer(text, reply_markup=kb)


# ============ НАПИСАТЬ СООБЩЕНИЕ ПОЛЬЗОВАТЕЛЮ ============

@router.callback_query(F.data.startswith("amsg:"))
async def admin_msg_start(call: CallbackQuery, state: FSMContext):
    uid = int(call.data.split(":")[1])
    u = await db.get_user(uid) or {}
    uname = f"@{u['username']}" if u.get("username") else "—"
    name = u.get("full_name") or "—"
    await state.set_state(MsgUser.waiting)
    await state.update_data(target_uid=uid)
    await call.message.answer(
        f"✉️ <b>Сообщение пользователю</b>\n{name} ({uname}) · <code>{uid}</code>\n\n"
        "Пришли текст одним сообщением — я отправлю его пользователю от имени бота.\n"
        "/cancel — отмена.")
    await call.answer()


@router.message(MsgUser.waiting, Command("cancel"))
async def admin_msg_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=panel_kb())


@router.message(MsgUser.waiting, F.text)
async def admin_msg_send(message: Message, state: FSMContext, bot: Bot):
    data = await state.get_data()
    uid = data.get("target_uid")
    await state.clear()
    try:
        await bot.send_message(uid, message.text)
        await message.answer(f"✅ Отправлено пользователю <code>{uid}</code>.", reply_markup=back_kb())
    except Exception as e:
        await message.answer(
            f"⚠️ Не удалось отправить (<code>{uid}</code>): {e}\n"
            "Возможно, пользователь не запускал бота или заблокировал его.",
            reply_markup=back_kb())


# ============ ПРЕДЗАКАЗЫ (брони) ============

@router.callback_query(F.data == "ap:preorders")
async def ap_preorders(call: CallbackQuery):
    pos = await db.waiting_preorders()
    if not pos:
        await call.message.edit_text(
            "📨 <b>Активные предзаказы</b>\n\nСейчас открытых броней нет.",
            reply_markup=back_kb())
        await call.answer()
        return
    lines = [f"📨 <b>Активные предзаказы — {len(pos)}</b>\n"]
    kb = InlineKeyboardBuilder()
    for po in pos:
        u = await db.get_user(po["user_id"]) or {}
        uname = f"@{u['username']}" if u.get("username") else "—"
        name = u.get("full_name") or "—"
        when = (po.get("created_at") or "")[:16].replace("T", " ")
        lines.append(
            f"#{po['id']} · <b>{po['region']}</b> · {po['plan']} · {po['rub']} ₽\n"
            f"   👤 {name} ({uname}) · <code>{po['user_id']}</code> · 🕒 {when}")
        kb.button(text=f"🚚 Выдать #{po['id']}", callback_data=f"apo:deliver:{po['id']}")
        kb.button(text=f"❌ Отменить #{po['id']}", callback_data=f"apo:cancel:{po['id']}")
        kb.button(text=f"✉️ Написать #{po['id']}", callback_data=f"amsg:{po['user_id']}")
    kb.button(text="🔄 Обновить", callback_data="ap:preorders")
    kb.button(text="⬅️ В админку", callback_data="ap:home")
    kb.adjust(3)
    await call.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("apo:cancel:"))
async def apo_cancel(call: CallbackQuery, bot: Bot):
    po_id = int(call.data.split(":")[2])
    po = await db.get_preorder(po_id)
    if not po or po["status"] != "waiting":
        await call.answer("Этот предзаказ уже обработан.", show_alert=True)
        return
    # возвращаем деньги на баланс и закрываем бронь
    await db.add_balance(po["user_id"], po["rub"])
    await db.set_preorder_status(po_id, "cancelled")
    lang = po.get("lang") or "ru"
    try:
        if lang == "en":
            txt = (f"😔 Your pre-order for <b>{po['region']}</b> was cancelled.\n"
                   f"We've refunded <b>{po['rub']} ₽</b> back to your balance.")
        else:
            txt = (f"😔 Твой предзаказ на <b>{po['region']}</b> отменён.\n"
                   f"Мы вернули <b>{po['rub']} ₽</b> на твой баланс.")
        await bot.send_message(po["user_id"], txt)
    except Exception:
        pass
    await call.answer(f"✅ Отменён, возвращено {po['rub']} ₽", show_alert=True)
    try:
        await call.message.edit_text(
            f"❌ Предзаказ #{po_id} ({po['region']}) отменён.\n"
            f"Возвращено <b>{po['rub']} ₽</b> пользователю <code>{po['user_id']}</code>.",
            reply_markup=back_kb())
    except Exception:
        pass


@router.callback_query(F.data.startswith("apo:deliver:"))
async def apo_deliver(call: CallbackQuery, bot: Bot):
    po_id = int(call.data.split(":")[2])
    po = await db.get_preorder(po_id)
    if not po or po["status"] != "waiting":
        await call.answer("Этот предзаказ уже обработан.", show_alert=True)
        return
    import handlers_user
    ok = await handlers_user.deliver_preorder(bot, po)
    if ok:
        await call.answer("✅ Выдано клиенту", show_alert=True)
        try:
            await call.message.edit_text(
                f"🚚 Предзаказ #{po_id} ({po['region']}) выдан "
                f"пользователю <code>{po['user_id']}</code>.",
                reply_markup=back_kb())
        except Exception:
            pass
    else:
        try:
            free = (await db.free_counts_by_region()).get(po["region"], 0)
        except Exception:
            free = 0
        need = po.get("devices", 1)
        await call.answer(
            f"⚠️ Не хватает конфигов в регионе «{po['region']}».\n"
            f"Нужно: {need} · свободно: {free}.\n"
            f"Загрузи ещё {max(need - free, 0)} конфиг(ов) в этот регион и нажми «Выдать».",
            show_alert=True)


@router.callback_query(F.data.startswith("acard:"))
async def admin_card(call: CallbackQuery):
    uid = int(call.data.split(":")[1])
    text, kb = await _user_card(uid)
    if not text:
        await call.answer("Пользователь не найден.", show_alert=True)
        return
    try:
        await call.message.edit_text(text, reply_markup=kb)
    except Exception:
        await call.message.answer(text, reply_markup=kb)
    await call.answer()


# ============ ЗАЯВКИ НА ВЫВОД РЕФЕРАЛЬНЫХ ============

# ============ ЗАЯВКИ НА ВЫВОД РЕФЕРАЛЬНЫХ ============

@router.callback_query(F.data == "ap:payouts")
async def ap_payouts(call: CallbackQuery):
    reqs = await db.pending_payouts()
    if not reqs:
        await call.message.edit_text(
            "💸 <b>Заявки на вывод</b>\n\nОжидающих выплат нет.", reply_markup=back_kb())
        await call.answer()
        return
    lines = [f"💸 <b>Заявки на вывод — {len(reqs)}</b>\n"]
    kb = InlineKeyboardBuilder()
    for r in reqs:
        u = await db.get_user(r["user_id"]) or {}
        uname = f"@{u['username']}" if u.get("username") else "—"
        name = u.get("full_name") or "—"
        when = (r.get("created_at") or "")[:16].replace("T", " ")
        lines.append(f"#{r['id']} · <b>{r['amount_rub']} ₽</b> · {name} ({uname}) · "
                     f"<code>{r['user_id']}</code> · 🕒 {when}")
        kb.button(text=f"✅ #{r['id']}", callback_data=f"apay:done:{r['id']}")
        kb.button(text=f"❌ #{r['id']}", callback_data=f"apay:rej:{r['id']}")
        kb.button(text=f"✉️ #{r['id']}", callback_data=f"amsg:{r['user_id']}")
    kb.button(text="🔄 Обновить", callback_data="ap:payouts")
    kb.button(text="⬅️ В админку", callback_data="ap:home")
    kb.adjust(3)
    await call.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("apay:"))
async def admin_payout_action(call: CallbackQuery, bot: Bot):
    _, action, pid_s = call.data.split(":")
    pid = int(pid_s)
    po = await db.get_payout(pid)
    if not po or po["status"] != "pending":
        await call.answer("Эта заявка уже обработана.", show_alert=True)
        return
    uid = po["user_id"]
    amount = po["amount_rub"]
    lang = await db.get_lang(uid)
    if action == "done":
        await db.set_payout_status(pid, "paid")
        try:
            await bot.send_message(uid, texts.payout_done_user(amount, lang))
        except Exception:
            pass
        await call.answer("✅ Отмечено как выплачено", show_alert=True)
        try:
            await call.message.edit_text(
                f"✅ Заявка #{pid} на <b>{amount} ₽</b> (<code>{uid}</code>) — выплачено.",
                reply_markup=back_kb())
        except Exception:
            pass
    elif action == "rej":
        await db.set_payout_status(pid, "rejected", refund=True)
        try:
            await bot.send_message(uid, texts.payout_rejected_user(amount, lang))
        except Exception:
            pass
        await call.answer("↩️ Отклонено, сумма возвращена", show_alert=True)
        try:
            await call.message.edit_text(
                f"❌ Заявка #{pid} на <b>{amount} ₽</b> (<code>{uid}</code>) — отклонена, "
                f"сумма возвращена на реф-баланс.",
                reply_markup=back_kb())
        except Exception:
            pass


# ============ ТОП РЕФЕРАЛОВ ============

@router.callback_query(F.data == "ap:topref")
async def ap_topref(call: CallbackQuery):
    rows = await db.top_referrers(10)
    lines = ["📈 <b>Топ рефереров</b>\n"]
    if not rows:
        lines.append("Пока никто не приглашал друзей.")
    else:
        medals = ["🥇", "🥈", "🥉"] + ["▫️"] * 7
        for i, r in enumerate(rows):
            name = r.get("username") and f"@{r['username']}" or (r.get("full_name") or str(r["user_id"]))
            lines.append(f"{medals[i]} {name} — <b>{r['invited']}</b> приглош. · {r['ref_earned_rub']} ₽")
    await call.message.edit_text("\n".join(lines), reply_markup=back_kb())
    await call.answer()


# ============ ЭКСПОРТ CSV ============

def _to_csv(rows: list[dict]) -> bytes:
    if not rows:
        return "нет данных\n".encode("utf-8-sig")
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue().encode("utf-8-sig")


@router.callback_query(F.data == "ap:export")
async def ap_export(call: CallbackQuery, bot: Bot):
    await call.answer("Готовлю файлы…")
    users = await db.export_users()
    payments = await db.export_payments()
    await bot.send_document(
        call.from_user.id,
        BufferedInputFile(_to_csv(users), filename="users.csv"),
        caption=f"👥 Пользователи: {len(users)}")
    await bot.send_document(
        call.from_user.id,
        BufferedInputFile(_to_csv(payments), filename="payments.csv"),
        caption=f"💰 Платежи: {len(payments)}")


# ============ РЕДАКТИРОВАНИЕ ЦЕН ============

_PERIOD_RU = {"month": "1 мес", "year": "1 год"}


def _prices_plans_kb():
    kb = InlineKeyboardBuilder()
    for key in PLAN_ORDER:
        p = PLANS[key]
        kb.button(text=f"{p['emoji']} {p['title']}", callback_data=f"pp:plan:{key}")
    kb.button(text="⬅️ В админку", callback_data="ap:home")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data == "ap:prices")
async def ap_prices(call: CallbackQuery):
    await call.message.edit_text(
        "💲 <b>Цены тарифов</b>\n\nВыбери тариф для редактирования. "
        "Изменения применяются сразу, без перезапуска.",
        reply_markup=_prices_plans_kb())
    await call.answer()


def _plan_prices_kb(plan):
    kb = InlineKeyboardBuilder()
    prices = store.plan_prices(plan)
    for dev in (1, 2):
        for per in ("month", "year"):
            rub = prices.get((dev, per))
            if rub is None:
                continue
            kb.button(text=f"📱{dev} · {_PERIOD_RU[per]} — {rub} ₽",
                      callback_data=f"pp:edit:{plan}:{dev}:{per}")
    kb.button(text="⬅️ К тарифам", callback_data="ap:prices")
    kb.adjust(1)
    return kb.as_markup()


@router.callback_query(F.data.startswith("pp:plan:"))
async def pp_plan(call: CallbackQuery):
    plan = call.data.split(":")[2]
    if plan not in PLANS:
        await call.answer()
        return
    p = PLANS[plan]
    await call.message.edit_text(
        f"💲 <b>{p['emoji']} {p['title']} — цены (₽)</b>\n\nНажми на позицию, чтобы изменить цену:",
        reply_markup=_plan_prices_kb(plan))
    await call.answer()


@router.callback_query(F.data.startswith("pp:edit:"))
async def pp_edit(call: CallbackQuery, state: FSMContext):
    _, _, plan, dev, per = call.data.split(":")
    await state.set_state(PriceEdit.waiting)
    await state.update_data(plan=plan, dev=int(dev), per=per)
    cur = store.get_price(plan, int(dev), per)
    await call.message.answer(
        f"💲 Новая цена для <b>{PLANS[plan]['title']} · {dev} устр · {_PERIOD_RU[per]}</b>\n"
        f"Текущая: <b>{cur} ₽</b>\n\nПришли новое число (₽). /cancel — отмена.")
    await call.answer()


@router.message(PriceEdit.waiting, Command("cancel"))
async def pp_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=panel_kb())


@router.message(PriceEdit.waiting, F.text)
async def pp_save(message: Message, state: FSMContext):
    data = await state.get_data()
    try:
        rub = int(message.text.strip())
        if rub < 0:
            raise ValueError
    except ValueError:
        await message.answer("Цена — целое число ≥ 0. Пример: 199")
        return
    plan, dev, per = data["plan"], data["dev"], data["per"]
    await db.save_price(plan, dev, per, rub)
    store.set_price_cache(plan, dev, per, rub)
    await state.clear()
    await message.answer(f"✅ Цена обновлена: <b>{PLANS[plan]['title']} · {dev} устр · {_PERIOD_RU[per]}</b> → <b>{rub} ₽</b>")
    await message.answer(f"💲 <b>{PLANS[plan]['title']} — цены (₽)</b>", reply_markup=_plan_prices_kb(plan))


# ============ КАТАЛОГ РЕГИОНОВ ============

async def _regions_kb():
    rows = await db.catalog_with_stock()
    kb = InlineKeyboardBuilder()
    lines = ["🗂 <b>Каталог регионов</b>\n",
             "<i>Регионы всегда видны при покупке. Если свободных конфигов 0 — "
             "клиенту предложат предзаказ.</i>\n"]
    for r in rows:
        star = "⭐️" if r["is_premium"] else "▫️"
        lines.append(f"{star} <b>{r['region']}</b> — 🟢{r['free']} / всего {r['total']}")
        kb.button(text=f"{star} {r['region']} ({r['free']})", callback_data=f"rc:pick:{r['region']}")
    kb.button(text="➕ Добавить регион", callback_data="rc:new")
    kb.button(text="⬅️ В админку", callback_data="ap:home")
    kb.adjust(1)
    return "\n".join(lines), kb.as_markup()


@router.callback_query(F.data == "ap:regions")
async def ap_regions(call: CallbackQuery):
    text, kb = await _regions_kb()
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data.startswith("rc:pick:"))
async def rc_pick(call: CallbackQuery):
    region = call.data.split(":", 2)[2]
    prem = store.is_premium_region(region)
    kb = InlineKeyboardBuilder()
    if prem:
        kb.button(text="▫️ Снять premium", callback_data=f"rc:prem:{region}:0")
    else:
        kb.button(text="⭐️ Сделать premium", callback_data=f"rc:prem:{region}:1")
    kb.button(text="✏️ Переименовать", callback_data=f"rc:ren:{region}")
    kb.button(text="🗑 Удалить из каталога", callback_data=f"rc:del:{region}")
    kb.button(text="⬅️ К регионам", callback_data="ap:regions")
    kb.adjust(1)
    await call.message.edit_text(
        f"🗂 Регион <b>{region}</b>\n{'⭐️ premium' if prem else '▫️ обычный'}\n\nЧто сделать?",
        reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("rc:prem:"))
async def rc_prem(call: CallbackQuery):
    _, _, region, val = call.data.split(":", 3)
    await db.catalog_set_premium(region, val == "1")
    await store.load_from_db()
    await call.answer("✅ Обновлено")
    text, kb = await _regions_kb()
    await call.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data.startswith("rc:del:"))
async def rc_del(call: CallbackQuery):
    region = call.data.split(":", 2)[2]
    await db.catalog_remove(region)
    await store.load_from_db()
    await call.answer("🗑 Удалён из каталога")
    text, kb = await _regions_kb()
    await call.message.edit_text(text, reply_markup=kb)


@router.callback_query(F.data == "rc:new")
async def rc_new(call: CallbackQuery, state: FSMContext):
    await state.set_state(RegionAdmin.add)
    await call.message.edit_text(
        "➕ <b>Новый регион</b>\n\nПришли название. Для premium добавь тег:\n"
        "• <code>Испания</code> — обычный\n• <code>Япония premium</code> — premium\n\n/cancel — отмена.",
        reply_markup=back_kb())
    await call.answer()


@router.message(RegionAdmin.add, Command("cancel"))
async def rc_add_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=panel_kb())


@router.message(RegionAdmin.add, F.text)
async def rc_add(message: Message, state: FSMContext):
    await state.clear()
    parts = message.text.strip().split()
    is_prem = False
    while parts and parts[-1].lower() in ("premium", "прем", "премиум"):
        parts.pop()
        is_prem = True
    region = " ".join(parts).strip()
    if not region:
        await message.answer("Укажи название региона.")
        return
    await db.catalog_add(region, is_prem)
    await store.load_from_db()
    text, kb = await _regions_kb()
    await message.answer(f"✅ Регион <b>{region}</b> добавлен ({'premium' if is_prem else 'обычный'}).")
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("rc:ren:"))
async def rc_rename_ask(call: CallbackQuery, state: FSMContext):
    region = call.data.split(":", 2)[2]
    await state.set_state(RegionAdmin.rename)
    await state.update_data(old=region)
    await call.message.answer(
        f"✏️ Переименовать <b>{region}</b>.\nПришли новое название (конфиги и статистика "
        f"переедут на новое имя). /cancel — отмена.")
    await call.answer()


@router.message(RegionAdmin.rename, Command("cancel"))
async def rc_rename_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=panel_kb())


@router.message(RegionAdmin.rename, F.text)
async def rc_rename(message: Message, state: FSMContext):
    data = await state.get_data()
    old = data.get("old")
    new = message.text.strip()
    await state.clear()
    if not new:
        await message.answer("Пустое название.")
        return
    await db.catalog_rename(old, new)
    await store.load_from_db()
    text, kb = await _regions_kb()
    await message.answer(f"✅ <b>{old}</b> → <b>{new}</b>")
    await message.answer(text, reply_markup=kb)


# ============ МЕТРИКИ / ГРАФИКИ ============

def _revenue_chart_png(rev_rows, days=14):
    """PNG-график выручки по дням. Возвращает bytes или None, если matplotlib недоступен."""
    try:
        import io as _io
        from datetime import datetime, timedelta, timezone
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None
    # непрерывный ряд дат
    data = {d: s for d, s in rev_rows}
    today = datetime.now(timezone.utc).date()
    labels, values = [], []
    for i in range(days - 1, -1, -1):
        d = (today - timedelta(days=i)).isoformat()
        labels.append(d[5:])  # MM-DD
        values.append(data.get(d, 0))
    fig, ax = plt.subplots(figsize=(9, 4.2))
    ax.bar(labels, values, color="#3b82f6")
    ax.set_title(f"Выручка по дням, ₽ (за {days} дн.)")
    ax.set_ylabel("₽")
    ax.grid(axis="y", alpha=0.3)
    plt.xticks(rotation=45, ha="right", fontsize=8)
    plt.tight_layout()
    buf = _io.BytesIO()
    fig.savefig(buf, format="png", dpi=120)
    plt.close(fig)
    return buf.getvalue()


@router.callback_query(F.data == "ap:metrics")
async def ap_metrics(call: CallbackQuery, bot: Bot):
    await call.answer("Считаю метрики…")
    # MRR
    breakdown = await db.active_subs_breakdown()
    mrr = 0.0
    for plan, period, c in breakdown:
        price = store.get_price(plan, 1, period)
        monthly = price if period == "month" else (price / 12 if period == "year" else 0)
        mrr += monthly * c
    conv = await db.trial_conversion()
    churn = await db.churn_30d()
    st = await db.stats_extended()

    lines = [
        "📊 <b>Метрики</b>\n",
        f"💵 <b>MRR</b> (мес. регулярная выручка): <b>{mrr:,.0f} ₽</b>".replace(",", " "),
        f"✅ Активных подписок: <b>{st['active_subs']}</b>",
        "",
        f"🎯 <b>Конверсия триал→оплата:</b> <b>{conv['rate']:.1f}%</b>",
        f"   ({conv['converted']} из {conv['trials']} триальщиков купили)",
        "",
        f"📉 <b>Отток за 30 дней:</b> <b>{churn['rate']:.1f}%</b>",
        f"   (истекло {churn['expired']}, не продлили {churn['churned']})",
        "",
        f"💰 Выручка: сегодня {st['day'][0]} ₽ · 7д {st['week'][0]} ₽ · 30д {st['month'][0]} ₽",
    ]
    text = "\n".join(lines)

    rev = await db.revenue_by_day(14)
    png = _revenue_chart_png(rev, 14)
    if png:
        await bot.send_photo(call.from_user.id, BufferedInputFile(png, "revenue.png"), caption=text)
    else:
        await call.message.answer(text + "\n\n<i>(график недоступен: установи matplotlib)</i>")
    await call.message.answer("🛠 Назад в панель:", reply_markup=panel_kb())


# ============ СКЛАД / ЗАКУПКИ ============

from config import RESTOCK_BATCH, RESTOCK_THRESHOLD  # noqa: E402
from utils import is_valid_wg  # noqa: E402

_RS_STATUS = {
    "new": "🆕 новая",
    "awaiting_payment": "⏳ ждёт оплаты",
    "paid": "💸 оплачено — нужны конфиги",
    "done": "✅ закрыта",
    "canceled": "❌ отменена",
}


def _split_configs(text: str) -> list[str]:
    """Делит вставленный текст на отдельные WireGuard-конфиги по блокам [Interface]."""
    text = (text or "").replace("\r", "")
    low = text.lower()
    if low.count("[interface]") <= 1:
        return [text.strip()] if text.strip() else []
    blocks, cur = [], []
    for line in text.split("\n"):
        if line.strip().lower() == "[interface]" and cur:
            blocks.append("\n".join(cur).strip())
            cur = [line]
        else:
            cur.append(line)
    if cur:
        blocks.append("\n".join(cur).strip())
    return [b for b in blocks if b]


async def _restock_card(rid: int):
    o = await db.get_restock(rid)
    if not o:
        return None, None
    free = (await db.free_counts_by_region()).get(o["region"], 0)
    status = _RS_STATUS.get(o["status"], o["status"])
    lines = [
        f"📦 <b>Заявка #{o['id']}</b> {'🔥' if o['urgent'] else ''}",
        f"🌍 Регион: <b>{o['region']}</b>",
        f"🟢 Свободно сейчас: <b>{free}</b> · нужно докупить: <b>{o['need']}</b>",
        f"📊 Статус: {status}",
    ]
    if o["amount_rub"]:
        lines.append(f"💰 Сумма пополнения: <b>{o['amount_rub']} ₽</b>")
    if o["pay_url"]:
        lines.append(f"🔗 Ссылка оплаты: сохранена")
    if o["status"] == "paid":
        lines.append(f"📥 Добавлено конфигов: <b>{o['added']}</b> / {o['need']}")

    kb = InlineKeyboardBuilder()
    if o["status"] in ("new", "awaiting_payment"):
        amt = f" ({o['amount_rub']} ₽)" if o["amount_rub"] else ""
        kb.button(text=f"✏️ Сумма{amt}", callback_data=f"rs:amount:{rid}")
        kb.button(text="🔗 Ссылка оплаты" if not o["pay_url"] else "🔗 Изменить ссылку",
                  callback_data=f"rs:url:{rid}")
        if o["pay_url"]:
            kb.button(text="💳 Оплатить", url=o["pay_url"])
            kb.button(text="✅ Оплатил", callback_data=f"rs:paid:{rid}")
        kb.button(text="❌ Отменить заявку", callback_data=f"rs:cancel:{rid}")
    elif o["status"] == "paid":
        kb.button(text="📥 Вставить конфиги (.conf)", callback_data=f"rs:configs:{rid}")
        kb.button(text="✅ Завершить заявку", callback_data=f"rs:done:{rid}")
        kb.button(text="❌ Отменить заявку", callback_data=f"rs:cancel:{rid}")
    kb.button(text="⬅️ К заявкам", callback_data="ap:restock")
    kb.adjust(2, 2, 1, 1)
    return "\n".join(lines), kb.as_markup()


@router.callback_query(F.data == "ap:restock")
async def ap_restock(call: CallbackQuery, state: FSMContext):
    await state.clear()
    orders = await db.list_restock(active_only=True)
    low = await db.low_stock_regions(RESTOCK_THRESHOLD)
    lines = ["📦 <b>Закупки / склад</b>\n",
             f"<i>Порог запаса: {RESTOCK_THRESHOLD} конфигов на регион. "
             f"Партнёр выдаёт по {RESTOCK_BATCH} за покупку.</i>\n"]
    kb = InlineKeyboardBuilder()
    if orders:
        lines.append("<b>Активные заявки:</b>")
        for o in orders:
            mark = "🔥" if o["urgent"] else "•"
            lines.append(f"{mark} #{o['id']} {o['region']} — {_RS_STATUS.get(o['status'], o['status'])}")
            kb.button(text=f"{mark} #{o['id']} {o['region']}", callback_data=f"rs:open:{o['id']}")
    else:
        lines.append("Активных заявок нет.")
    if low:
        lines.append("\n<b>Низкий запас:</b>")
        for r in low:
            lines.append(f"⚠️ {r['region']} — 🟢{r['free']}" + (" · есть предзаказ!" if r["has_preorder"] else ""))
    kb.button(text="🧹 Проверить склад (битые)", callback_data="rs:scan")
    kb.button(text="➕ Новая заявка", callback_data="rs:new")
    kb.button(text="⬅️ В админку", callback_data="ap:home")
    kb.adjust(1)
    await call.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(F.data == "rs:scan")
async def rs_scan(call: CallbackQuery):
    await call.answer("Проверяю конфиги…")
    n = await db.validate_free_stock()
    broken = await db.broken_counts()
    lines = [f"🧹 <b>Проверка склада завершена</b>\n\nПомечено битыми сейчас: <b>{n}</b>."]
    if broken:
        lines.append("\n<b>Битые по регионам (не продаются):</b>")
        for region, cnt in sorted(broken.items()):
            lines.append(f"🔴 {region}: {cnt}")
        lines.append("\n<i>Замени их на аккаунтах-источниках и удали через «🗑 Удаление».</i>")
    else:
        lines.append("\nБитых конфигов нет 👍")
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ К закупкам", callback_data="ap:restock")
    await call.message.edit_text("\n".join(lines), reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("rs:open:"))
async def rs_open(call: CallbackQuery):
    rid = int(call.data.split(":")[2])
    text, kb = await _restock_card(rid)
    if not text:
        await call.answer("Заявка не найдена.", show_alert=True)
        return
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer()


@router.callback_query(F.data == "rs:new")
async def rs_new(call: CallbackQuery):
    rows = await db.catalog_with_stock()
    kb = InlineKeyboardBuilder()
    for r in rows:
        star = "⭐️" if r["is_premium"] else "▫️"
        kb.button(text=f"{star} {r['region']} (🟢{r['free']})", callback_data=f"rs:newr:{r['region']}")
    kb.button(text="⬅️ К заявкам", callback_data="ap:restock")
    kb.adjust(2)
    await call.message.edit_text("➕ <b>Новая заявка</b>\n\nВыбери регион:", reply_markup=kb.as_markup())
    await call.answer()


@router.callback_query(F.data.startswith("rs:newr:"))
async def rs_new_region(call: CallbackQuery):
    region = call.data.split(":", 2)[2]
    rid = await db.create_restock(region, RESTOCK_BATCH, urgent=False)
    text, kb = await _restock_card(rid)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("Заявка создана")


@router.callback_query(F.data.startswith("rs:amount:"))
async def rs_amount_ask(call: CallbackQuery, state: FSMContext):
    rid = int(call.data.split(":")[2])
    await state.set_state(Restock.amount)
    await state.update_data(rid=rid)
    await call.message.answer("💰 Пришли сумму пополнения в ₽ (число). /cancel — отмена.")
    await call.answer()


@router.message(Restock.amount, Command("cancel"))
async def rs_amount_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=panel_kb())


@router.message(Restock.amount, F.text)
async def rs_amount_save(message: Message, state: FSMContext):
    data = await state.get_data()
    rid = data.get("rid")
    try:
        amount = int(message.text.strip())
        if amount <= 0:
            raise ValueError
    except ValueError:
        await message.answer("Сумма — целое число > 0. Пример: 600")
        return
    await db.set_restock(rid, amount_rub=amount)
    await state.clear()
    text, kb = await _restock_card(rid)
    await message.answer(f"✅ Сумма сохранена: {amount} ₽")
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("rs:url:"))
async def rs_url_ask(call: CallbackQuery, state: FSMContext):
    rid = int(call.data.split(":")[2])
    await state.set_state(Restock.url)
    await state.update_data(rid=rid)
    await call.message.answer(
        "🔗 Пришли https-ссылку на страницу оплаты от WireCat.\n/cancel — отмена.")
    await call.answer()


@router.message(Restock.url, Command("cancel"))
async def rs_url_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=panel_kb())


@router.message(Restock.url, F.text)
async def rs_url_save(message: Message, state: FSMContext):
    data = await state.get_data()
    rid = data.get("rid")
    url = message.text.strip()
    if not url.lower().startswith("https://"):
        await message.answer("Это не похоже на https-ссылку. Пришли ссылку, начинающуюся с https://")
        return
    await db.set_restock(rid, pay_url=url, status="awaiting_payment")
    await state.clear()
    text, kb = await _restock_card(rid)
    await message.answer("✅ Ссылка сохранена.")
    await message.answer(text, reply_markup=kb)


@router.callback_query(F.data.startswith("rs:paid:"))
async def rs_paid(call: CallbackQuery):
    rid = int(call.data.split(":")[2])
    await db.set_restock(rid, status="paid")
    text, kb = await _restock_card(rid)
    await call.message.edit_text(text, reply_markup=kb)
    await call.answer("Отмечено как оплачено. Теперь вставь конфиги.")


@router.callback_query(F.data.startswith("rs:cancel:"))
async def rs_cancel(call: CallbackQuery):
    rid = int(call.data.split(":")[2])
    await db.set_restock(rid, status="canceled")
    await call.answer("Заявка отменена")
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ К заявкам", callback_data="ap:restock")
    await call.message.edit_text("❌ Заявка отменена.", reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("rs:done:"))
async def rs_done(call: CallbackQuery):
    rid = int(call.data.split(":")[2])
    o = await db.get_restock(rid)
    await db.set_restock(rid, status="done")
    await call.answer("Заявка закрыта")
    kb = InlineKeyboardBuilder()
    kb.button(text="⬅️ К заявкам", callback_data="ap:restock")
    await call.message.edit_text(
        f"✅ Заявка #{rid} закрыта. Добавлено конфигов: <b>{o['added'] if o else 0}</b> "
        f"в <b>{o['region'] if o else '—'}</b>.\n\n"
        "<i>Предзаказы по этому региону будут выданы автоматически в ближайшую минуту.</i>",
        reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("rs:configs:"))
async def rs_configs_ask(call: CallbackQuery, state: FSMContext):
    rid = int(call.data.split(":")[2])
    o = await db.get_restock(rid)
    if not o:
        await call.answer("Заявка не найдена.", show_alert=True)
        return
    await state.set_state(Restock.source)
    await state.update_data(rid=rid, region=o["region"])
    kb = InlineKeyboardBuilder()
    kb.button(text="⏭ Без источника", callback_data=f"rs:srcskip:{rid}")
    kb.adjust(1)
    await call.message.answer(
        f"👤 С какого <b>аккаунта</b> эти конфиги для <b>{o['region']}</b>? "
        f"Напиши имя/метку — увидишь её при замене. Или «⏭ Без источника».",
        reply_markup=kb.as_markup())
    await call.answer()


async def _rs_ask_configs(target, state: FSMContext):
    data = await state.get_data()
    await state.set_state(Restock.configs)
    src = data.get("source")
    src_line = f"👤 Источник: <b>{src}</b>\n" if src else ""
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Готово", callback_data=f"rs:open:{data.get('rid')}")
    await target.answer(
        f"📥 Присылай <code>.conf</code> файлы или текст для <b>{data.get('region')}</b> "
        f"(по одному или пачкой).\n{src_line}Невалидные конфиги пропущу.\n"
        f"Когда закончишь — «✅ Готово» или /done.",
        reply_markup=kb.as_markup())


@router.callback_query(F.data.startswith("rs:srcskip:"))
async def rs_src_skip(call: CallbackQuery, state: FSMContext):
    await state.update_data(source=None)
    await _rs_ask_configs(call.message, state)
    await call.answer()


@router.message(Restock.source, Command("cancel"))
async def rs_source_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Отменено.", reply_markup=panel_kb())


@router.message(Restock.source, F.text)
async def rs_source(message: Message, state: FSMContext):
    await state.update_data(source=message.text.strip())
    await _rs_ask_configs(message, state)


async def _restock_add_blocks(message, state, blocks: list[str]):
    data = await state.get_data()
    rid, region = data.get("rid"), data.get("region")
    source = data.get("source")
    premium = store.is_premium_region(region)
    added, skipped = await db.add_configs_bulk(region, premium, False, blocks, source)
    if added:
        await db.restock_inc_added(rid, added)
        o = await db.get_restock(rid)
        msg = f"➕ Добавлено: <b>{added}</b> (всего по заявке {o['added']}/{o['need']})."
    else:
        msg = "⚠️ Ни одного валидного WireGuard-конфига не найдено."
    if skipped:
        msg += f"\n⏭ Пропущено невалидных: {skipped}."
    await message.answer(msg)


@router.message(Restock.configs, Command("cancel"))
async def rs_configs_cancel(message: Message, state: FSMContext):
    await state.clear()
    await message.answer("❌ Приём конфигов остановлен.", reply_markup=panel_kb())


@router.message(Restock.configs, Command("done"))
async def rs_configs_done(message: Message, state: FSMContext):
    data = await state.get_data()
    await state.clear()
    rid = data.get("rid")
    kb = InlineKeyboardBuilder()
    kb.button(text="📦 Открыть заявку", callback_data=f"rs:open:{rid}")
    await message.answer("✅ Приём конфигов завершён.", reply_markup=kb.as_markup())


@router.message(Restock.configs, F.document)
async def rs_configs_doc(message: Message, state: FSMContext, bot: Bot):
    buf = await bot.download(message.document)
    text = buf.read().decode(errors="replace")
    await _restock_add_blocks(message, state, _split_configs(text))


@router.message(Restock.configs, F.text, ~F.text.startswith("/"))
async def rs_configs_text(message: Message, state: FSMContext):
    await _restock_add_blocks(message, state, _split_configs(message.text))


@router.callback_query(F.data.startswith("rcq:"))
async def cb_region_change(call: CallbackQuery, bot: Bot):
    """Одобрение/отклонение запроса на смену региона. Одобрение → самый быстрый (с макс. запасом)."""
    import handlers_user
    _, action, rid = call.data.split(":")
    req = await db.get_region_change(int(rid))
    if not req:
        await call.answer("Запрос не найден.", show_alert=True)
        return
    if req["status"] != "pending":
        await call.answer("Этот запрос уже обработан.", show_alert=True)
        return
    uid = req["user_id"]
    config_id = req["config_id"]
    ulang = await db.get_lang(uid)

    if action == "no":
        await db.set_region_change_status(int(rid), "rejected")
        try:
            await bot.send_message(uid, texts.region_change_rejected(ulang))
        except Exception:
            pass
        await call.answer("Отклонено")
        try:
            await call.message.edit_text(call.message.html_text + "\n\n❌ <b>Отклонено.</b>")
        except Exception:
            pass
        return

    # Одобрение: выбираем самый быстрый = с наибольшим свободным запасом (кроме текущего региона)
    cfg = await db.get_config(config_id)
    if not cfg or cfg["status"] != "sold":
        await call.answer("Конфиг клиента уже не активен.", show_alert=True)
        return
    regions = await db.regions_for_purchase()
    avail = [r for r in regions if r[2] >= 1 and r[0] != cfg["region"]]
    if not avail:
        await call.answer("Нет свободных серверов для замены — загрузи конфиги в любой регион.", show_alert=True)
        return
    best = max(avail, key=lambda r: r[2])[0]
    new = await db.replace_config(config_id, best, "country")
    if not new:
        await call.answer("Не удалось заменить — нет свободного конфига. Попробуй ещё раз.", show_alert=True)
        return
    await db.set_region_change_status(int(rid), "approved")
    try:
        await bot.send_message(uid, texts.region_change_done(texts.region_name(best, ulang), ulang))
        await handlers_user.send_config_to(bot, uid, new, ulang)
    except Exception:
        pass
    await call.answer("✅ Одобрено — клиент получил новый регион")
    try:
        await call.message.edit_text(call.message.html_text + f"\n\n✅ <b>Одобрено → {best}.</b>")
    except Exception:
        pass
