"""
VPN Mini App — веб-сервер для Telegram Web App.

Только API + статика (index.html). Бота (bot.py, aiogram polling) этот файл
НЕ запускает — его нужно поднимать отдельным процессом/сервисом.

Пути и поля запросов согласованы с тем, что реально шлёт index.html:
  POST /create_payment  {tariff, devices, period, region, user_id, init_data}
  POST /check_payment   {order_id, method, invoice_id, init_data}
  POST /me              {init_data}                       -> { is_admin, ... }
  POST /admin/stats_summary {init_data}                    -> { users, revenue, active, stock, ... }

Оплата и выдача конфигов используют ТЕ ЖЕ функции, что и сам бот
(db.reserve_purchase/create_order, payments.create_lava_invoice/…,
handlers_user._fulfill) — мини-апп не дублирует логику, а вызывает её.
У веб-сервера свой Bot(token=...) — только для отправки сообщений/инвойсов,
polling он не делает, поэтому конфликта (409) с ботом, запущенным отдельно,
не будет.
"""

import hashlib
import hmac
import json
import logging
import os
from datetime import timedelta
from urllib.parse import parse_qsl

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web

import db
import store
import payments as pay
import handlers_user  # переиспользуем _fulfill — та же выдача, что и в боте
from config import ADMIN_IDS, BOT_TOKEN, PAYMENT_MODE, PLANS, RESTOCK_THRESHOLD

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("webapp")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан — заполни .env / переменные Railway")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")


# ───────────────────────── Telegram WebApp initData ─────────────────────────

def parse_init_data(init_data: str) -> dict | None:
    """Проверяет подпись initData из Telegram.WebApp.initData.
    None, если подпись неверна — БЕЗ этой проверки любой мог бы прислать
    чужой user_id и покупать/списывать баланс за чужой счёт."""
    if not init_data:
        return None
    try:
        pairs = dict(parse_qsl(init_data, strict_parsing=False))
        recv_hash = pairs.pop("hash", None)
        if not recv_hash:
            return None
        data_check_string = "\n".join(f"{k}={v}" for k, v in sorted(pairs.items()))
        secret_key = hmac.new(b"WebAppData", BOT_TOKEN.encode(), hashlib.sha256).digest()
        calc_hash = hmac.new(secret_key, data_check_string.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(calc_hash, recv_hash):
            return None
        user = json.loads(pairs.get("user", "{}"))
        if not user.get("id"):
            return None
        return {
            "user_id": int(user["id"]),
            "username": user.get("username"),
            "full_name": " ".join(filter(None, [user.get("first_name"), user.get("last_name")])),
        }
    except Exception as e:
        log.warning("bad init_data: %s", e)
        return None


async def _auth(request: web.Request) -> dict | None:
    """Фронт шлёт initData полем `init_data` в JSON-теле (POST)."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    init_data = body.get("init_data", "")
    request["_body"] = body  # чтобы не читать тело дважды
    return parse_init_data(init_data)


class _TargetShim:
    """handlers_user._fulfill() ожидает aiogram Message (.answer/.answer_document/
    .answer_photo — шлют в тот же чат). Из HTTP-запроса чата нет — шлём эти же
    типы сообщений напрямую по user_id через Bot API."""

    def __init__(self, chat_id: int):
        self.chat_id = chat_id

    async def answer(self, text, reply_markup=None, **kw):
        return await bot.send_message(self.chat_id, text, reply_markup=reply_markup, **kw)

    async def answer_document(self, document, caption=None, **kw):
        return await bot.send_document(self.chat_id, document, caption=caption, **kw)

    async def answer_photo(self, photo, caption=None, **kw):
        return await bot.send_photo(self.chat_id, photo, caption=caption, **kw)


# ───────────────────────────────── API ─────────────────────────────────

routes = web.RouteTableDef()


@routes.get("/")
async def index(request):
    path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(path):
        return web.Response(text="static/index.html не найден", status=404)
    return web.FileResponse(path)


@routes.post("/me")
async def api_me(request):
    auth = await _auth(request)
    if not auth:
        return web.json_response({"error": "bad_init_data"}, status=401)
    user_id = auth["user_id"]
    await db.add_user(user_id, auth.get("username"), auth.get("full_name"))

    lang = await db.get_lang(user_id)
    balance = await db.get_balance(user_id)
    spent = await db.total_spent(user_id)

    return web.json_response({
        "is_admin": user_id in ADMIN_IDS,
        "user_id": user_id,
        "lang": lang,
        "balance": balance,
        "total_spent": spent,
        "loyalty_percent": pay.loyalty_percent_for(spent),
    })


def _pick_region(plan: str) -> tuple[str, bool] | None:
    """Fallback, если фронт почему-то не прислал region: берём первый регион
    каталога с достаточным типом доступа (используется только если фронт
    старой версии — актуальный index.html теперь всегда шлёт region сам)."""
    premium_ok = PLANS[plan]["premium_access"]
    for region, is_premium in store.CATALOG:
        if is_premium and not premium_ok:
            continue
        return region, is_premium
    return None


@routes.post("/create_payment")
async def api_create_payment(request):
    auth = await _auth(request)
    if not auth:
        return web.json_response({"error": "bad_init_data"}, status=401)
    user_id = auth["user_id"]
    body = request["_body"]

    plan = body.get("tariff")
    period = body.get("period")
    region = body.get("region")
    try:
        devices = int(body.get("devices", 1))
    except (TypeError, ValueError):
        return web.json_response({"error": "bad_devices"}, status=400)

    if plan not in PLANS or (devices, period) not in PLANS[plan]["prices"]:
        return web.json_response({"error": "bad_plan"}, status=400)

    if not region:
        picked = _pick_region(plan)
        if not picked:
            return web.json_response({"error": "no_region"}, status=400)
        region, _ = picked
    elif store.is_premium_region(region) and not PLANS[plan]["premium_access"]:
        return web.json_response({"error": "region_locked"}, status=400)

    # Цена считается ТОЛЬКО на сервере — цену, присланную фронтом, не используем.
    full = pay.price_rub(plan, devices, period)
    spent = await db.total_spent(user_id)
    discount = full * pay.loyalty_percent_for(spent) // 100
    to_pay = full - discount

    reserved = await db.reserve_purchase(region, devices, user_id)
    if reserved is None:
        return web.json_response({"error": "no_stock"}, status=409)

    config_ids = [c["id"] for c in reserved]
    order_id = await db.create_order(user_id, plan, devices, period, region, config_ids,
                                      full, discount, to_pay)
    lang = await db.get_lang(user_id)

    if to_pay <= 0:
        order = await db.get_order(order_id)
        await handlers_user._fulfill(_TargetShim(user_id), user_id, order, bot,
                                      paid_money=False, lang=lang)
        return web.json_response({"paid": True, "order_id": order_id})

    method = PAYMENT_MODE if PAYMENT_MODE != "choice" else "crypto"
    title = f"{PLANS[plan]['title']} · {devices} устр. · {period}"
    desc = f"VPN-доступ ({region})."
    invoice_id = None

    try:
        if method in ("lava", "sbp", "card"):
            _iid, pay_url = await pay.create_lava_invoice(order_id, to_pay, title)
        elif method == "crypto":
            invoice_id, pay_url = await pay.create_crypto_invoice(order_id, to_pay, title)
            if not pay_url:
                raise RuntimeError("CryptoPay не вернул ссылку на оплату")
        elif method in ("stars", "yookassa"):
            params = pay.invoice_params(title, desc, f"order:{order_id}", to_pay)
            pay_url = await bot.create_invoice_link(**params)
            # Для stars/yookassa оплата подтвердится САМА через pre_checkout/
            # successful_payment хендлеры в handlers_user.py — их обрабатывает
            # polling-бот, запущенный этим же процессом. check_payment не нужен.
        else:
            raise RuntimeError(f"неизвестный PAYMENT_MODE: {method!r}")
    except Exception as e:
        log.exception("invoice error (%s): %s", method, e)
        await db.free_configs(config_ids)
        await db.set_order_status(order_id, "cancelled")
        return web.json_response({"error": "payment_unavailable"}, status=500)

    return web.json_response({
        "payment_url": pay_url,
        "order_id": order_id,
        "method": method,
        "invoice_id": invoice_id,
    })


@routes.post("/check_payment")
async def api_check_payment(request):
    """Мини-апп зовёт это, когда пользователь вернулся после оплаты (lava/crypto) —
    аналог кнопки «Я оплатил — проверить» в самом боте."""
    auth = await _auth(request)
    if not auth:
        return web.json_response({"error": "bad_init_data"}, status=401)
    user_id = auth["user_id"]
    body = request["_body"]

    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return web.json_response({"error": "bad_order_id"}, status=400)
    method = body.get("method")
    invoice_id = body.get("invoice_id")

    order = await db.get_order(order_id)
    if not order or order["user_id"] != user_id:
        return web.json_response({"error": "not_found"}, status=404)
    if order["status"] == "paid":
        return web.json_response({"status": "paid"})

    try:
        if method == "lava":
            paid = await pay.check_lava_invoice(order_id)
            ref = str(order_id)
        elif method == "crypto":
            paid = await pay.check_crypto_invoice(int(invoice_id))
            ref = str(invoice_id)
        else:
            return web.json_response({"status": "pending"})
    except Exception as e:
        log.exception("check_payment error: %s", e)
        return web.json_response({"error": str(e)}, status=500)

    if not paid:
        return web.json_response({"status": "pending"})

    await db.record_payment(user_id, order_id, order["rub"], method.upper(), ref)
    lang = await db.get_lang(user_id)
    await handlers_user._fulfill(_TargetShim(user_id), user_id, order, bot,
                                  paid_money=True, lang=lang)
    return web.json_response({"status": "paid"})


@routes.post("/admin/stats_summary")
async def api_admin_stats(request):
    auth = await _auth(request)
    if not auth or auth["user_id"] not in ADMIN_IDS:
        return web.json_response({"error": "forbidden"}, status=403)

    s = await db.stats_extended()
    low_stock = await db.low_stock_regions(RESTOCK_THRESHOLD)
    day_rub, _day_cnt = s["day"]
    cut = db.iso(db.now() - timedelta(hours=24))
    new_users_24h = await db.new_users_since(cut)

    return web.json_response({
        "users": s["users"],
        "revenue": s["all"][0],
        "active": s["active_subs"],
        "stock": s["free_paid"],
        "users_delta": f"+{new_users_24h} за 24ч" if new_users_24h else None,
        "revenue_delta": f"+{day_rub}₽ за 24ч" if day_rub else None,
        "stock_alert": bool(low_stock),
    })


# ─────────────────────────────── запуск ───────────────────────────────

async def on_startup(app: web.Application):
    await db.init_db()
    await store.load_from_db()
    log.info("Веб-сервер поднят (бот запускается отдельно, см. bot.py).")


async def on_cleanup(app: web.Application):
    await bot.session.close()


def build_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    if os.path.isdir(STATIC_DIR):
        app.router.add_static("/static/", STATIC_DIR, show_index=False)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    web.run_app(build_app(), host="0.0.0.0", port=port)
