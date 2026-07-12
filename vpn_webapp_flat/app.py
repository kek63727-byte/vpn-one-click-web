"""
VPN Mini App — Flask сервер.

Работает В ТОМ ЖЕ ПРОЕКТЕ, что и бот, и использует ТЕ ЖЕ модули:
db.py, config.py, payments.py, handlers_user.py — поэтому цены, выдача
конфигов, реферальные начисления и способы оплаты полностью совпадают
с тем, что уже работает в самом боте. Ничего не задублировано и не
придумано заново.

Запускать отдельным процессом (см. Procfile: web-дино), бот — отдельным
воркер-процессом. Оба процесса читают/пишут один и тот же DB_PATH (sqlite).
"""

import asyncio
import hashlib
import hmac
import json
import logging
import urllib.parse
from datetime import datetime

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from flask import Flask, jsonify, request, send_from_directory

import db
import texts
from config import (
    BOT_TOKEN, DEVICE_TITLE, PAYMENT_MODE, PERIOD_TITLE, PLANS, PLAN_ORDER,
    PRIME_DEVICES, PRIME_ENABLED, PRIME_PERIOD, PRIME_PLAN, PRIME_PRICES,
    SUPPORT_USERNAME, TOPUP_PRESETS,
)
from payments import (
    check_crypto_invoice, check_lava_invoice, create_crypto_invoice,
    create_lava_invoice, invoice_params, price_rub, topup_bonus_for,
)

# handlers_user содержит уже готовую логику выдачи/наград — переиспользуем её,
# чтобы поведение веб-аппа 1-в-1 совпадало с ботом.
import handlers_user as hu

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("webapp")

app = Flask(__name__, static_folder="static")


# ────────────────────────────────────────────────────────────────
# Проверка Telegram WebApp initData (обязательно! иначе любой человек
# сможет прислать чужой user_id и получить чужой баланс/конфиги).
# https://core.telegram.org/bots/webapps#validating-data-received-via-the-mini-app
# ────────────────────────────────────────────────────────────────
def verify_init_data(init_data: str, max_age_sec: int = 86400) -> dict | None:
    if not init_data:
        return None
    try:
        parsed = dict(urllib.parse.parse_qsl(init_data, strict_parsing=True))
    except ValueError:
        return None
    recv_hash = parsed.pop("hash", None)
    if not recv_hash:
        return None
    data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(parsed.items()))
    secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
    computed = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(computed, recv_hash):
        return None
    try:
        auth_date = int(parsed.get("auth_date", "0"))
        if max_age_sec and (datetime.now().timestamp() - auth_date) > max_age_sec:
            return None
    except ValueError:
        return None
    user = json.loads(parsed.get("user", "{}"))
    if not user.get("id"):
        return None
    return user


def require_user():
    """Достаёт и проверяет пользователя из тела запроса. Возвращает (user_dict, error_response)."""
    data = request.get_json(silent=True) or {}
    user = verify_init_data(data.get("init_data", ""))
    if not user:
        return None, (jsonify({"error": "unauthorized: bad init_data"}), 401)
    return user, None


def run(coro):
    """Flask синхронный — гоняем asyncio-корутины из db.py/payments.py по одной за запрос."""
    return asyncio.run(coro)


async def _bot():
    return Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))


_bot_username_cache: dict = {}


async def _get_bot_username() -> str:
    if "value" in _bot_username_cache:
        return _bot_username_cache["value"]
    async with await _bot() as bot:
        me = await bot.get_me()
        _bot_username_cache["value"] = me.username
        return me.username


# ────────────────────────────────────────────────────────────────
# Статика
# ────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ────────────────────────────────────────────────────────────────
# GET /api/plans — тарифы, цены, регионы (из реального config.py/db.py)
# ────────────────────────────────────────────────────────────────
@app.route("/api/plans", methods=["GET"])
def api_plans():
    async def _go():
        plans_out = {}
        for key in PLAN_ORDER:
            p = PLANS[key]
            prices = {}
            for (devices, period), rub in p["prices"].items():
                prices.setdefault(str(devices), {})[period] = rub
            plans_out[key] = {
                "title": p["title"], "emoji": p["emoji"], "speed": p["speed"],
                "premium_access": p["premium_access"], "features": p["features"],
                "prices": prices,
            }
        regions = await db.regions_for_purchase()
        prime = None
        if PRIME_ENABLED:
            prime = {
                "plan": PRIME_PLAN, "devices": PRIME_DEVICES,
                "default_period": PRIME_PERIOD, "prices": PRIME_PRICES,
            }
        return {
            "plans": plans_out,
            "plan_order": PLAN_ORDER,
            "device_titles": DEVICE_TITLE,
            "period_titles": PERIOD_TITLE,
            "regions": [{"region": r, "is_premium": bool(pr), "free": f} for r, pr, f in regions],
            "prime": prime,
            "topup_presets": TOPUP_PRESETS,
            "payment_mode": PAYMENT_MODE,
            "bot_username": await _get_bot_username(),
            "support_username": SUPPORT_USERNAME,
        }
    return jsonify(run(_go()))


# ────────────────────────────────────────────────────────────────
# POST /api/profile — баланс, рефералка, активный тариф, мои конфиги
# ────────────────────────────────────────────────────────────────
@app.route("/api/profile", methods=["POST"])
def api_profile():
    user, err = require_user()
    if err:
        return err
    uid = user["id"]

    async def _go():
        await db.add_user(uid, user.get("username"), user.get("first_name"))
        bal = await db.get_balance(uid)
        ref = await db.referral_stats(uid)
        active = await db.active_plan(uid)
        cfgs = await db.user_configs(uid)
        return {
            "user_id": uid,
            "balance": bal,
            "active_plan": active,
            "referral": ref,
            "configs": [
                {"id": c["id"], "region": c["region"], "status": c["status"],
                 "expires_at": c["expires_at"], "plan": c["plan"], "period": c["period"]}
                for c in cfgs
            ],
        }
    return jsonify(run(_go()))


# ────────────────────────────────────────────────────────────────
# POST /api/payments — история платежей (пополнения + оплаченные заказы)
# ────────────────────────────────────────────────────────────────
@app.route("/api/payments", methods=["POST"])
def api_payments():
    user, err = require_user()
    if err:
        return err
    uid = user["id"]

    async def _go():
        return await db.pay_history(uid, limit=30)
    return jsonify({"items": run(_go())})


# ────────────────────────────────────────────────────────────────
# POST /api/create_order — купить тариф (баланс → авто-выдача, иначе счёт)
# body: {init_data, plan, devices, period, region, method}
# method ∈ lava | sbp | crypto | stars  (игнорируется, если PAYMENT_MODE != "choice")
# ────────────────────────────────────────────────────────────────
@app.route("/api/create_order", methods=["POST"])
def api_create_order():
    user, err = require_user()
    if err:
        return err
    uid = user["id"]
    data = request.get_json(silent=True) or {}
    plan = data.get("plan")
    devices = int(data.get("devices", 1))
    period = data.get("period")
    region = data.get("region")
    method = data.get("method") or (PAYMENT_MODE if PAYMENT_MODE != "choice" else "lava")

    if plan not in PLANS:
        return jsonify({"error": "unknown plan"}), 400
    if (devices, period) not in PLANS[plan]["prices"]:
        return jsonify({"error": "unknown devices/period combo for this plan"}), 400

    async def _go():
        await db.add_user(uid, user.get("username"), user.get("first_name"))
        full = price_rub(plan, devices, period)

        reserved = await db.reserve_purchase(region, devices, uid)
        if reserved is None:
            return {"status": "out_of_stock", "region": region}

        bal = await db.get_balance(uid)
        config_ids = [c["id"] for c in reserved]

        # хватает баланса — списываем и выдаём сразу, платёж не нужен
        if bal >= full:
            if not await db.deduct_balance(uid, full):
                await db.free_configs(config_ids)
                return {"status": "insufficient_balance"}
            order_id = await db.create_order(uid, plan, devices, period, region, config_ids, full, 0, full)
            order = await db.get_order(order_id)
            async with await _bot() as bot:
                await _fulfill_webapp(bot, uid, order, paid_money=False)
            return {"status": "paid_from_balance", "order_id": order_id, "charged": full}

        # баланса не хватает — держим сервер за пользователем и создаём счёт на остаток
        order_id = await db.create_order(uid, plan, devices, period, region, config_ids, full, 0, full)
        order = await db.get_order(order_id)
        pay_info = await _create_invoice(order, method)
        return {"status": "awaiting_payment", "order_id": order_id, "to_pay": full, **pay_info}

    return jsonify(run(_go()))


async def _create_invoice(order: dict, method: str) -> dict:
    title, desc = hu._order_title(order, "ru")
    to_pay = order["rub"]
    order_id = order["id"]

    if method in ("lava", "sbp", "card"):
        _iid, pay_url = await create_lava_invoice(order_id, to_pay, title)
        return {"method": method, "pay_url": pay_url}

    if method == "crypto":
        invoice_id, pay_url = await create_crypto_invoice(order_id, to_pay, title)
        if not pay_url:
            return {"method": method, "error": "crypto invoice failed"}
        return {"method": method, "pay_url": pay_url, "invoice_id": invoice_id}

    if method == "stars":
        async with await _bot() as bot:
            await bot.send_invoice(chat_id=order["user_id"],
                                   **invoice_params(title, desc, f"order:{order_id}", to_pay))
        return {"method": "stars", "sent_to_chat": True}

    return {"method": method, "error": "unknown method"}


# ────────────────────────────────────────────────────────────────
# POST /api/check_payment — «Я оплатил, проверить» из мини-аппа
# body: {init_data, order_id, method, invoice_id?}
# ────────────────────────────────────────────────────────────────
@app.route("/api/check_payment", methods=["POST"])
def api_check_payment():
    user, err = require_user()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    order_id = int(data.get("order_id"))
    method = data.get("method")
    invoice_id = data.get("invoice_id")

    async def _go():
        order = await db.get_order(order_id)
        if not order or order["user_id"] != user["id"]:
            return {"error": "order not found"}, 404
        if order["status"] == "paid":
            return {"status": "already_paid"}, 200

        if method in ("lava", "sbp", "card"):
            paid = await check_lava_invoice(order_id)
            ref = str(order_id)
            method_name = "LAVA"
        elif method == "crypto":
            paid = await check_crypto_invoice(int(invoice_id))
            ref = str(invoice_id)
            method_name = "CRYPTO"
        else:
            return {"error": "unsupported method for manual check"}, 400

        if not paid:
            return {"status": "not_paid_yet"}, 200

        await db.record_payment(user["id"], order_id, order["rub"], method_name, ref)
        async with await _bot() as bot:
            await _fulfill_webapp(bot, user["id"], order, paid_money=True)
        return {"status": "paid"}, 200

    result, code = run(_go())
    return jsonify(result), code


# ────────────────────────────────────────────────────────────────
# POST /api/create_topup — пополнение баланса
# body: {init_data, amount, method}
# ────────────────────────────────────────────────────────────────
@app.route("/api/create_topup", methods=["POST"])
def api_create_topup():
    user, err = require_user()
    if err:
        return err
    uid = user["id"]
    data = request.get_json(silent=True) or {}
    amount = int(data.get("amount", 0))
    method = data.get("method") or (PAYMENT_MODE if PAYMENT_MODE != "choice" else "lava")
    if amount <= 0:
        return jsonify({"error": "bad amount"}), 400

    async def _go():
        await db.add_user(uid, user.get("username"), user.get("first_name"))
        topup_id = await db.create_topup(uid, amount, method)
        title = f"Пополнение баланса {amount} ₽"

        if method in ("lava", "sbp", "card"):
            _iid, pay_url = await create_lava_invoice(topup_id, amount, title)
            return {"topup_id": topup_id, "method": method, "pay_url": pay_url}

        if method == "crypto":
            invoice_id, pay_url = await create_crypto_invoice(topup_id, amount, title)
            if not pay_url:
                return {"error": "crypto invoice failed"}
            return {"topup_id": topup_id, "method": method, "pay_url": pay_url, "invoice_id": invoice_id}

        if method == "stars":
            async with await _bot() as bot:
                await bot.send_invoice(chat_id=uid,
                                       **invoice_params(title, title, f"topup:{topup_id}", amount))
            return {"topup_id": topup_id, "method": "stars", "sent_to_chat": True}

        return {"error": "unknown method"}
    return jsonify(run(_go()))


# ────────────────────────────────────────────────────────────────
# POST /api/check_topup
# body: {init_data, topup_id, method, invoice_id?}
# ────────────────────────────────────────────────────────────────
@app.route("/api/check_topup", methods=["POST"])
def api_check_topup():
    user, err = require_user()
    if err:
        return err
    data = request.get_json(silent=True) or {}
    topup_id = int(data.get("topup_id"))
    method = data.get("method")
    invoice_id = data.get("invoice_id")

    async def _go():
        topup = await db.get_topup(topup_id)
        if not topup or topup["user_id"] != user["id"]:
            return {"error": "topup not found"}, 404
        if topup["status"] == "paid":
            return {"status": "already_paid"}, 200

        if method in ("lava", "sbp", "card"):
            paid = await check_lava_invoice(topup_id)
            ref = str(topup_id)
            method_name = "LAVA"
        elif method == "crypto":
            paid = await check_crypto_invoice(int(invoice_id))
            ref = str(invoice_id)
            method_name = "CRYPTO"
        else:
            return {"error": "unsupported method for manual check"}, 400

        if not paid:
            return {"status": "not_paid_yet"}, 200

        async with await _bot() as bot:
            await _fulfill_topup_webapp(bot, user["id"], topup, method_name, ref)
        return {"status": "paid"}, 200

    result, code = run(_go())
    return jsonify(result), code


# ────────────────────────────────────────────────────────────────
# Вебхуки платёжек — пассивное автозачисление, без нажатия «проверить».
# Ничего не доверяем телу вебхука напрямую: по orderId дёргаем тот же
# check_*_invoice, который реально ходит в API провайдера за статусом.
# ────────────────────────────────────────────────────────────────
@app.route("/lava_webhook", methods=["POST"])
def lava_webhook():
    data = request.get_json(silent=True) or {}
    order_id = data.get("orderId") or data.get("order_id")
    if not order_id:
        return jsonify({"ok": True})
    order_id = int(order_id)

    async def _go():
        # сначала пробуем как заказ на тариф, затем как пополнение баланса
        order = await db.get_order(order_id)
        if order and order["status"] != "paid":
            if await check_lava_invoice(order_id):
                await db.record_payment(order["user_id"], order_id, order["rub"], "LAVA", str(order_id))
                async with await _bot() as bot:
                    await _fulfill_webapp(bot, order["user_id"], order, paid_money=True)
            return
        topup = await db.get_topup(order_id)
        if topup and topup["status"] != "paid":
            if await check_lava_invoice(order_id):
                async with await _bot() as bot:
                    await _fulfill_topup_webapp(bot, topup["user_id"], topup, "LAVA", str(order_id))
    run(_go())
    return jsonify({"ok": True})


# ────────────────────────────────────────────────────────────────
# Выдача — используем ту же логику, что и бот (handlers_user), но шлём
# сообщения по user_id напрямую через bot.send_message/send_document,
# т.к. у нас нет aiogram Message, к которому можно ответить (это HTTP-запрос).
# ────────────────────────────────────────────────────────────────
async def _fulfill_webapp(bot: Bot, user_id: int, order: dict, paid_money: bool, lang: str = "ru"):
    await db.set_order_status(order["id"], "paid")
    if order.get("discount", 0) > 0:
        await db.use_ref_balance(user_id, order["discount"])

    config_ids = [int(x) for x in order["config_ids"].split(",") if x]
    total = len(config_ids)

    if total == 0:
        await db.create_subscription(user_id, order["plan"], order["devices"], order["period"])
        await bot.send_message(user_id, texts.sub_created(order["devices"], lang))
    else:
        await bot.send_message(
            user_id,
            f"🎉 <b>Готово!</b> Высылаю {'конфиг' if total == 1 else f'{total} конфига'} 👇",
        )
        for cid in config_ids:
            await db.mark_sold(cid, user_id, order["plan"], order["period"])
            cfg = await db.get_config(cid)
            await hu.send_config_to(bot, user_id, cfg, lang)
        applied, _region = await db.apply_bonus(user_id)
        if applied:
            await bot.send_message(user_id, f"🎁 К твоей подписке добавлено <b>{applied}</b> бонусных дней!")

    if paid_money:
        if order.get("promo"):
            await hu._consume_promo(order["promo"], user_id)
        await hu._reward_referrer(user_id, order["full_rub"], bot)
        await hu._sales_log(bot, user_id, order)


async def _fulfill_topup_webapp(bot: Bot, user_id: int, topup: dict, method_name: str, ref: str):
    if topup["status"] == "paid":
        return
    await db.set_topup_paid(topup["id"])
    await db.add_balance(user_id, topup["amount_rub"])
    bonus, pct = topup_bonus_for(topup["amount_rub"])
    if bonus > 0:
        await db.add_balance(user_id, bonus)
    await db.record_payment(user_id, 0, topup["amount_rub"], method_name, str(ref))
    bal = await db.get_balance(user_id)
    await bot.send_message(
        user_id,
        f"✅ Баланс пополнен на <b>{topup['amount_rub']} ₽</b>. Текущий баланс: <b>{bal} ₽</b>",
    )
    if bonus > 0:
        await bot.send_message(user_id, f"🎁 Бонус за пополнение: +{bonus} ₽ ({pct}%)")
    await hu._reward_referrer(user_id, topup["amount_rub"], bot)
    await hu._sales_log_topup(bot, user_id, topup)


# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
