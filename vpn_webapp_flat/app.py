"""
VPN Mini App — веб-сервер для Telegram Web App.

Только API + статика (index.html). Бота (bot.py, aiogram polling) этот файл
НЕ запускает — его нужно поднимать отдельным процессом/сервисом.

Пути и поля запросов согласованы с тем, что реально шлёт index.html:
  POST /create_payment  {tariff, devices, period, region, user_id, init_data}
  POST /check_payment   {order_id, method, invoice_id, init_data}
  POST /me              {init_data}                       -> { is_admin, ... }
  POST /admin/stats_summary {init_data}                    -> { users, revenue, active, stock, ... }

ОПЛАТА ТАРИФОВ: ТОЛЬКО с внутреннего баланса. Если баланса не хватает —
пользователь получает need_topup и должен пополнить баланс через /topup
(единственный путь, который создаёт счёт в LAVA — СБП / карта).

ВАЖНО про orderId для LAVA: заказы (order_id) и пополнения баланса (topup_id)
хранятся в РАЗНЫХ таблицах с независимыми autoincrement-счётчиками, поэтому
их значения могут совпадать (например order_id=5 и topup_id=5). LAVA хранит
все orderId у себя в рамках магазина и отклоняет повтор ошибкой "OrderId
должен быть уникальным", даже если для нас это два разных объекта. Поэтому
все вызовы create_lava_invoice/check_lava_invoice для пополнений передают
kind="topup" — так orderId у LAVA всегда получается вида "topup-5" и не
пересекается с чем-либо ещё.
"""

import hashlib
import hmac
import json
import logging
import os
import asyncio
import texts
from datetime import timedelta
from urllib.parse import parse_qsl

from aiogram import Bot
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiohttp import web
from utils import happ_deeplink, happ_open_url

import db
import store
import payments as pay
import handlers_user
import admin_api
import team_api          # ← добавить эту строку

from config import (
    ADMIN_IDS,
    BOT_TOKEN,
    PAYMENT_MODE,
    PLANS,
    RESTOCK_THRESHOLD,
    PRIME_PLAN,
    PRIME_DEVICES,
    PRIME_PRICES,
    LAVA_WEBHOOK_SECRET,
    FREEZE_PRICE,
    FREEZE_DAYS,
    FREEZE_COOLDOWN_DAYS,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger("webapp")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN не задан — заполни .env / переменные Railway")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")

# Известные методы оплаты для ПОПОЛНЕНИЯ БАЛАНСА (/topup). Всё, что вне
# этого списка (включая "choice"), приводится к дефолтному методу LAVA.
# Для покупки тарифа (/create_payment) методы оплаты больше не используются
# вообще — оплата идёт исключительно с баланса.
_KNOWN_METHODS = {"lava", "sbp", "card", "crypto", "stars", "yookassa"}
_DEFAULT_METHOD = "lava"


def _resolve_payment_method(requested: str | None) -> str:
    """Возвращает валидный метод оплаты для /topup, по умолчанию — LAVA."""
    method = (requested or "").strip().lower()
    if method not in _KNOWN_METHODS:
        return _DEFAULT_METHOD
    return method


# ───────────────────────── Telegram WebApp initData ─────────────────────────

def parse_init_data(init_data: str) -> dict | None:
    """Проверяет подпись initData из Telegram.WebApp.initData."""
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
    request["_body"] = body
    return parse_init_data(init_data)


class _TargetShim:
    """Шим для handlers_user._fulfill() — шлёт сообщения по user_id через Bot API."""

    def __init__(self, chat_id: int):
        self.chat_id = chat_id

    async def answer(self, text, reply_markup=None, **kw):
        return await bot.send_message(self.chat_id, text, reply_markup=reply_markup, **kw)

    async def answer_document(self, document, caption=None, **kw):
        return await bot.send_document(self.chat_id, document, caption=caption, **kw)

    async def answer_photo(self, photo, caption=None, **kw):
        return await bot.send_photo(self.chat_id, photo, caption=caption, **kw)

    async def answer_video(self, video, caption=None, **kw):
        return await bot.send_video(self.chat_id, video, caption=caption, **kw)


# ───────────────────────────────── API ─────────────────────────────────

routes = web.RouteTableDef()


@routes.get("/")
async def index(request):
    path = os.path.join(STATIC_DIR, "index.html")
    if not os.path.exists(path):
        return web.Response(text="static/index.html не найден", status=404)
    return web.FileResponse(path)

@routes.get("/prices")
async def api_prices(request):
    """Актуальные цены (с учётом оверрайдов из админки) для мини-аппа —
    чтобы не дублировать цены в JS и не показывать устаревшие цифры."""
    plans_out = {}
    for plan in PLANS:
        by_devices: dict[str, dict[str, int]] = {}
        for (devices, period), rub in store.plan_prices(plan).items():
            by_devices.setdefault(str(devices), {})[period] = rub
        plans_out[plan] = by_devices

    prime_prices = {
        period: store.get_price(PRIME_PLAN, PRIME_DEVICES, period)
        for period in PRIME_PRICES
    }
    resp = web.json_response({"plans": plans_out, "prime_prices": prime_prices})
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


@routes.get("/sub/{config_id}/{token}")
async def sub_link(request):
    """Публичная ссылка на конфиг для happ://add/... — БЕЗ Telegram init_data,
    Happ открывает её как обычный браузер. Защита — HMAC-токен в самой ссылке."""
    from utils import sub_token
    try:
        config_id = int(request.match_info["config_id"])
    except ValueError:
        return web.Response(status=404, text="not found")
    token = request.match_info["token"]
    if not hmac.compare_digest(sub_token(config_id), token):
        return web.Response(status=404, text="not found")
    cfg = await db.get_config(config_id)
    if not cfg or cfg.get("status") != "sold":
        return web.Response(status=404, text="not found")
    return web.Response(text=cfg["config_text"], content_type="text/plain", charset="utf-8")

@routes.get("/happ-open/{config_id}")
async def happ_open_page(request):
    """Промежуточная HTML-страница: открывается во внешнем браузере и оттуда
    сама перенаправляет в happ:// — то, что нельзя сделать напрямую из
    Telegram Mini App WebView (там custom-схемы блокируются)."""
    from utils import happ_deeplink, sub_token
    try:
        config_id = int(request.match_info["config_id"])
    except ValueError:
        return web.Response(status=404, text="not found")

    token = request.query.get("t", "")
    if not hmac.compare_digest(sub_token(config_id), token):
        return web.Response(status=404, text="not found")

    cfg = await db.get_config(config_id)
    if not cfg or cfg.get("status") != "sold":
        return web.Response(status=404, text="Конфиг не найден или недействителен")

    deeplink = happ_deeplink(config_id)

    html = f"""<!DOCTYPE html>
<html lang="ru"><head><meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Открываем Happ…</title>
<style>
  body {{ background:#050307; color:#f6f4ff; font-family:-apple-system,Inter,sans-serif;
          display:flex; flex-direction:column; align-items:center; justify-content:center;
          height:100vh; margin:0; padding:24px; text-align:center; }}
  .spinner {{ width:40px; height:40px; border:3px solid rgba(124,58,237,0.25);
              border-top-color:#7c3aed; border-radius:50%; animation:spin .8s linear infinite; margin-bottom:20px; }}
  @keyframes spin {{ to {{ transform:rotate(360deg); }} }}
  a.btn {{ display:inline-block; margin-top:18px; padding:14px 26px; border-radius:14px;
           background:linear-gradient(135deg,#7c3aed,#b794ff); color:#fff; text-decoration:none; font-weight:700; }}
  p {{ color:#a89fc4; font-size:14px; line-height:1.6; max-width:320px; }}
</style></head>
<body>
  <div class="spinner"></div>
  <p>Открываем приложение Happ…<br>Если ничего не произошло — нажми кнопку ниже.</p>
  <a class="btn" id="manualBtn" href="{deeplink}">Открыть вручную</a>
  <script>
    window.location.href = "{deeplink}";
  </script>
</body></html>"""
    return web.Response(text=html, content_type="text/html")

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

    # Загружаем активные конфиги пользователя для экрана "Подключения"
    configs = await db.user_configs(user_id)

    active_configs = [
        {
            "id": c["id"],
            "region": c["region"],
            "plan": c.get("plan", "standard"),
            "expires_at": (c.get("expires_at") or "")[:10],
            "status": c.get("status", ""),
            "config_type": c.get("config_type", "wireguard"),
            "happ_link": happ_deeplink(c["id"]) if c.get("config_type") == "vless" else None,
            "happ_open_url": happ_open_url(c["id"]) if c.get("config_type") == "vless" else None,
        }
        for c in configs if c.get("status") == "sold"
    ]

    # Реферальный код и статистика
    ref_stats = await db.referral_stats(user_id)
    ref_cash = await db.get_ref_cash(user_id)

    offer_eligible = await db.webapp_offer_eligible(user_id)

    return web.json_response({
        "is_admin": user_id in ADMIN_IDS,
        "user_id": user_id,
        "lang": lang,
        "balance": balance,
        "total_spent": spent,
        "loyalty_percent": pay.loyalty_percent_for(spent),
        "active_configs": active_configs,
        "ref_invited": ref_stats.get("invited", 0),
        "ref_cash": ref_cash,
        "referral_code": str(user_id),
        "special_offer": {"eligible": offer_eligible, "percent": 50},
        "freeze_price": FREEZE_PRICE,
        "freeze_days": FREEZE_DAYS,
    })


async def _pick_region(plan: str) -> tuple[str, bool] | None:
    """Автовыбор региона («Авто» в мини-аппе): берём первый по каталогу
    регион нужного уровня доступа, в котором реально есть свободные конфиги."""
    premium_ok = PLANS[plan]["premium_access"]
    free_by_region = await db.free_counts_by_region()
    for region, is_premium in store.CATALOG:
        if is_premium and not premium_ok:
            continue
        if free_by_region.get(region, 0) > 0:
            return region, is_premium
    return None


@routes.post("/create_payment")
async def api_create_payment(request):
    """Покупка тарифа — ТОЛЬКО с внутреннего баланса.

    Если баланса не хватает — возвращаем need_topup и НИКАКОГО перехода на
    внешние платёжки (Lava/крипта/Stars) для оплаты тарифа больше нет.
    Пополнить баланс пользователь может только через отдельный /topup.
    """
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
        picked = await _pick_region(plan)
        if not picked:
            return web.json_response({"error": "no_region"}, status=400)
        region, _ = picked
    elif store.is_premium_region(region) and not PLANS[plan]["premium_access"]:
        return web.json_response({"error": "region_locked"}, status=400)

    # Цена считается ТОЛЬКО на сервере
    full = pay.price_rub(plan, devices, period)
    spent = await db.total_spent(user_id)
    loyalty_discount = full * pay.loyalty_percent_for(spent) // 100

    # Приветственная/возвратная скидка мини-аппа — право на неё перепроверяем
    # на сервере, клиентскому флагу не доверяем (иначе любой мог бы прислать
    # use_special_offer=true и получить скидку без права на неё).
    use_offer = bool(body.get("use_special_offer"))
    offer_applied = False
    if use_offer and await db.webapp_offer_eligible(user_id):
        offer_discount = full * 50 // 100
        if offer_discount > loyalty_discount:
            discount = offer_discount
            offer_applied = True
        else:
            discount = loyalty_discount
    else:
        discount = loyalty_discount

    to_pay = full - discount
    balance = await db.get_balance(user_id)

    # ── Баланса не хватает — сразу просим пополнить, ДО брони сервера.
    # Никакой Lava-ссылки на оплату тарифа больше не создаём.
    if balance < to_pay:
        await db.log_event(user_id, "order_failed", amount=to_pay,
                            meta={"reason": "need_topup", "plan": plan, "devices": devices,
                                  "period": period, "region": region, "balance": balance},
                            source="webapp")
        return web.json_response({
            "error": "need_topup",
            "to_pay": to_pay,
            "balance": balance,
        }, status=409)

    reserved = await db.reserve_purchase(region, devices, user_id)
    if reserved is None:
        # Баланса хватает, но серверов нет — это реальный дефицит стока.
        await db.log_event(user_id, "order_failed",
                            meta={"reason": "no_stock", "plan": plan, "devices": devices,
                                  "period": period, "region": region}, source="webapp")
        return web.json_response({"error": "no_stock"}, status=409)

    config_ids = [c["id"] for c in reserved]

    # Списываем баланс СРАЗУ. Если списание не удалось (гонка запросов,
    # баланс успел измениться) — освобождаем забронированные конфиги.
    if not await db.deduct_balance(user_id, to_pay):
        await db.free_configs(config_ids)
        fresh_balance = await db.get_balance(user_id)
        return web.json_response({
            "error": "need_topup",
            "to_pay": to_pay,
            "balance": fresh_balance,
        }, status=409)

    order_id = await db.create_order(user_id, plan, devices, period, region, config_ids,
                                      full, discount, to_pay)
    lang = await db.get_lang(user_id)

    # Оплата с баланса — сразу выдаём тариф.
    order = await db.get_order(order_id)
    await handlers_user._fulfill(_TargetShim(user_id), user_id, order, bot,
                                  paid_money=False, lang=lang, source="webapp")

    if offer_applied:
        await db.mark_webapp_offer_used(user_id)

    await db.set_order_status(order_id, "paid")
    await db.log_event(user_id, "order_paid", amount=to_pay,
                        meta={"plan": plan, "devices": devices, "period": period,
                              "region": region, "order_id": order_id,
                              "full_rub": full, "discount": discount,
                              "offer_applied": offer_applied},
                        source="webapp")

    new_balance = await db.get_balance(user_id)
    return web.json_response({"paid": True, "order_id": order_id, "balance": new_balance})

@routes.post("/webhook/lava")
async def webhook_lava(request: web.Request):
    """Вебхук от LAVA Business. Названия полей в разных версиях API могут
    отличаться, поэтому пробуем несколько распространённых вариантов и
    логируем сырой payload — если что-то не распозналось, будет видно в
    логах Railway (Deployments -> Logs) и легко поправить руками."""
    raw = await request.text()
    try:
        body = json.loads(raw)
    except Exception as e:
        log.warning("lava webhook: bad json body: %s raw=%s", e, raw[:500])
        return web.json_response({"error": "bad_body"}, status=400)

    log.info("lava webhook received: headers=%s body=%s",
              {k: v for k, v in request.headers.items() if k.lower() != "cookie"}, raw[:2000])

    signature = (
        request.headers.get("Signature")
        or request.headers.get("signature")
        or request.headers.get("Authorization", "").replace("Bearer ", "")
        or body.get("signature")
        or ""
    )
    if LAVA_WEBHOOK_SECRET:
        expected = hmac.new(LAVA_WEBHOOK_SECRET.encode(), raw.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected, signature):
            log.warning("lava webhook: signature mismatch (got=%s expected=%s) — "
                        "ПРОВЕРЬТЕ LAVA_WEBHOOK_SECRET в .env, это ОТДЕЛЬНЫЙ "
                        "'дополнительный ключ' из ЛК LAVA, не тот же что LAVA_SECRET_KEY",
                        signature[:16], expected[:16])
            return web.json_response({"error": "bad_signature"}, status=403)
    else:
        log.warning("lava webhook: LAVA_WEBHOOK_SECRET не задан в .env — "
                    "подпись НЕ проверяется, это небезопасно для продакшена")

    order_id_raw = (
        body.get("orderId") or body.get("order_id")
        or body.get("customFields") or body.get("custom_fields")
    ) or ""
    if not order_id_raw and isinstance(body.get("data"), dict):
        order_id_raw = body["data"].get("orderId") or body["data"].get("order_id") or ""

    status_raw = (
        body.get("status") or (body.get("data") or {}).get("status") or ""
    )
    status = str(status_raw).lower()

    log.info("lava webhook parsed: order_id_raw=%r status=%r", order_id_raw, status)

    if status not in ("success", "paid", "completed", "confirmed"):
        return web.json_response({"ok": True})

    kind, _, raw_id = str(order_id_raw).partition("-")
    try:
        entity_id = int(raw_id)
    except ValueError:
        log.warning("lava webhook: не смог распарсить orderId=%r — проверьте формат в логах выше",
                    order_id_raw)
        return web.json_response({"error": "bad_order_id"}, status=400)

    if kind == "topup":
        topup = await db.get_topup(entity_id)
        if not topup or topup["status"] == "paid":
            return web.json_response({"ok": True})
        await db.set_topup_paid(entity_id)
        await db.add_balance(topup["user_id"], topup["amount_rub"])
        await db.record_payment(topup["user_id"], 0, topup["amount_rub"], "LAVA", str(entity_id))
        await db.log_event(topup["user_id"], "topup_paid", amount=topup["amount_rub"],
                            meta={"method": "LAVA", "topup_id": entity_id}, source="webhook")
        log.info("lava webhook: topup %s credited for user %s", entity_id, topup["user_id"])
        try:
            await bot.send_message(topup["user_id"],
                                   f"✅ Баланс пополнен на {topup['amount_rub']} ₽")
        except Exception:
            pass

    elif kind == "order":
        order = await db.get_order(entity_id)
        if not order or order["status"] == "paid":
            return web.json_response({"ok": True})
        await db.record_payment(order["user_id"], order["id"], order["rub"], "LAVA", str(entity_id))
        lang = await db.get_lang(order["user_id"])
        await handlers_user._fulfill(_TargetShim(order["user_id"]), order["user_id"], order, bot,
                                      paid_money=True, lang=lang, source="webhook")
        await db.set_order_status(order["id"], "paid")
        await db.log_event(order["user_id"], "order_paid", amount=order["rub"],
                            meta={"plan": order.get("plan"), "devices": order.get("devices"),
                                  "period": order.get("period"), "region": order.get("region"),
                                  "order_id": order["id"]},
                            source="webhook")
        log.info("lava webhook: order %s fulfilled for user %s", entity_id, order["user_id"])

    return web.json_response({"ok": True})

@routes.post("/get_config")
async def api_get_config(request):
    """Отдаёт содержимое конфига для скачивания/показа QR в мини-аппе
    (кнопка «Конфиг» в разделе «Подключения»)."""
    auth = await _auth(request)
    if not auth:
        return web.json_response({"error": "bad_init_data"}, status=401)
    user_id = auth["user_id"]
    body = request["_body"]

    try:
        config_id = int(body.get("config_id"))
    except (TypeError, ValueError):
        return web.json_response({"error": "bad_config_id"}, status=400)

    cfg = await db.get_config(config_id)
    if not cfg or cfg.get("user_id") != user_id or cfg.get("status") != "sold":
        return web.json_response({"error": "not_found"}, status=404)

    ext = "json" if cfg.get("config_type") == "vless" else "conf"
    filename = f"{texts.region_slug(cfg['region'])}_{cfg['id']}.{ext}"

    return web.json_response({
        "config_text": cfg["config_text"],
        "title": f"Конфиг · {cfg['region']}",
        "filename": filename,
    })

@routes.post("/check_payment")
async def api_check_payment(request):
    """Оставлено для обратной совместимости со старыми клиентами мини-аппа.

    Оплата тарифов больше не создаёт внешних счетов (см. /create_payment),
    поэтому проверять тут, по сути, нечего — заказ либо уже оплачен с
    баланса и выдан сразу в /create_payment, либо не существует."""
    auth = await _auth(request)
    if not auth:
        return web.json_response({"error": "bad_init_data"}, status=401)
    user_id = auth["user_id"]
    body = request["_body"]

    try:
        order_id = int(body.get("order_id"))
    except (TypeError, ValueError):
        return web.json_response({"error": "bad_order_id"}, status=400)

    order = await db.get_order(order_id)
    if not order or order["user_id"] != user_id:
        return web.json_response({"error": "not_found"}, status=404)
    if order["status"] == "paid":
        return web.json_response({"status": "paid"})
    return web.json_response({"status": "pending"})


@routes.post("/apply_promo")
async def api_apply_promo(request):
    """Применить промокод из мини-аппа."""
    auth = await _auth(request)
    if not auth:
        return web.json_response({"error": "bad_init_data"}, status=401)
    user_id = auth["user_id"]
    body = request["_body"]
    code = (body.get("code") or "").strip().upper()
    if not code:
        return web.json_response({"error": "empty_code"}, status=400)

    promo = await db.get_promo(code)
    if not promo:
        return web.json_response({"error": "not_found"}, status=404)

    if await db.promo_redeemed_by(code, user_id):
        return web.json_response({"error": "already_used"}, status=409)

    if promo["kind"] == "balance":
        await db.add_balance(user_id, promo["amount_rub"])
        await db.use_promo(code)
        await db.record_promo_redemption(code, user_id)
        balance = await db.get_balance(user_id)
        return web.json_response({
            "ok": True,
            "kind": "balance",
            "amount": promo["amount_rub"],
            "new_balance": balance,
        })
    elif promo["kind"] == "discount":
        # Скидочный промокод — возвращаем процент, применяется при следующей покупке
        return web.json_response({
            "ok": True,
            "kind": "discount",
            "percent": promo["percent"],
            "code": code,
        })
    else:
        return web.json_response({"error": "unknown_kind"}, status=400)


@routes.post("/topup")
async def api_topup(request):
    """Пополнение баланса через мини-апп — ЕДИНСТВЕННЫЙ путь, где создаётся
    внешний счёт (LAVA: СБП / карта, либо крипта / Stars)."""
    auth = await _auth(request)
    if not auth:
        return web.json_response({"error": "bad_init_data"}, status=401)
    user_id = auth["user_id"]
    body = request["_body"]

    try:
        amount = int(body.get("amount", 0))
    except (TypeError, ValueError):
        return web.json_response({"error": "bad_amount"}, status=400)

    if amount < 50:
        return web.json_response({"error": "min_50"}, status=400)

    # Метод оплаты: если фронт явно передал method — используем его (после валидации),
    # иначе — берём из конфига. В любом случае неизвестное значение → LAVA.
    method = _resolve_payment_method(body.get("method") or PAYMENT_MODE)

    topup_id = await db.create_topup(user_id, amount, method)
    title = f"Пополнение баланса {amount} ₽"
    invoice_id = None

    try:
        if method in ("lava", "sbp", "card"):
            # kind="topup" — orderId у LAVA получится вида "topup-<id>", чтобы
            # не пересекаться с чем-либо ещё.
            _iid, pay_url = await pay.create_lava_invoice(topup_id, amount, title, kind="topup")
            method = "lava"
        elif method == "crypto":
            invoice_id, pay_url = await pay.create_crypto_invoice(topup_id, amount, title)
        elif method in ("stars", "yookassa"):
            params = pay.invoice_params(title, title, f"topup:{topup_id}", amount)
            pay_url = await bot.create_invoice_link(**params)
        else:
            # На всякий случай — LAVA.
            _iid, pay_url = await pay.create_lava_invoice(topup_id, amount, title, kind="topup")
            method = "lava"
    except Exception as e:
        log.exception("topup invoice error: %s", e)
        return web.json_response({"error": "payment_unavailable"}, status=500)

    await db.log_event(user_id, "topup_invoice", amount=amount,
                        meta={"method": method, "topup_id": topup_id}, source="webapp")
    return web.json_response({
        "payment_url": pay_url,
        "topup_id": topup_id,
        "method": method,
        "invoice_id": invoice_id,
    })


@routes.post("/check_topup")
async def api_check_topup(request):
    """Проверка пополнения баланса."""
    auth = await _auth(request)
    if not auth:
        return web.json_response({"error": "bad_init_data"}, status=401)
    user_id = auth["user_id"]
    body = request["_body"]

    try:
        topup_id = int(body.get("topup_id"))
    except (TypeError, ValueError):
        return web.json_response({"error": "bad_topup_id"}, status=400)

    method = _resolve_payment_method(body.get("method"))
    invoice_id = body.get("invoice_id")

    topup = await db.get_topup(topup_id)
    if not topup or topup.get("user_id") != user_id:
        return web.json_response({"error": "not_found"}, status=404)
    if topup.get("status") == "paid":
        balance = await db.get_balance(user_id)
        return web.json_response({"status": "paid", "balance": balance})

    try:
        if method == "lava":
            # kind="topup" — должен совпадать с тем, что передавалось в
            # create_lava_invoice при создании этого пополнения в /topup.
            paid = await pay.check_lava_invoice(topup_id, kind="topup")
        elif method == "crypto":
            paid = await pay.check_crypto_invoice(int(invoice_id))
        else:
            return web.json_response({"status": "pending"})
    except Exception as e:
        log.exception("check_topup error: %s", e)
        return web.json_response({"error": str(e)}, status=500)

    if not paid:
        return web.json_response({"status": "pending"})

    await db.set_topup_paid(topup_id)
    await db.add_balance(user_id, topup["amount_rub"])
    await db.record_payment(user_id, 0, topup["amount_rub"], method.upper(), str(topup_id))
    await db.log_event(user_id, "topup_paid", amount=topup["amount_rub"],
                        meta={"method": method, "topup_id": topup_id}, source="webapp")

    balance = await db.get_balance(user_id)
    return web.json_response({"status": "paid", "balance": balance})

REPORT_REASON_LABELS = {
    'no_connect':        '🚫 Не подключается вообще',
    'slow_speed':        '⚡ Слабая скорость / тормоза',
    'drops':             '🔗 Часто обрывается',
    'want_region':       '🌍 Хочет другой регион',
    'not_working_apps':  '📱 Не работает на устройстве',
    'sites_blocked':     '🛡 Нужные сайты всё ещё блокируются',
    'other':             '💬 Другая проблема',
}


@routes.post("/report_config")
async def api_report_config(request):
    auth = await _auth(request)
    if not auth:
        return web.json_response({"error": "bad_init_data"}, status=401)
    user_id = auth["user_id"]
    body = request["_body"]

    try:
        config_id = int(body.get("config_id"))
    except (TypeError, ValueError):
        return web.json_response({"error": "bad_config_id"}, status=400)
    reason = str(body.get("reason", "")).strip()
    comment = str(body.get("comment", "")).strip()[:500]

    if not reason:
        return web.json_response({"error": "missing_fields"}, status=400)

    cfg = await db.get_config(config_id)
    if not cfg or cfg["user_id"] != user_id or cfg["status"] != "sold":
        return web.json_response({"error": "not_your_config"}, status=403)

    if await db.recent_reports_count(user_id, config_id) >= 3:
        return web.json_response({"error": "too_many_reports"}, status=429)

    report_id = await db.create_report(user_id, config_id, cfg["region"], reason, comment)
    await _notify_admin_report(report_id, auth, cfg, reason, comment)
    return web.json_response({"ok": True, "report_id": report_id})

@routes.post("/my_payments")
async def api_my_payments(request):
    auth = await _auth(request)
    if not auth:
        return web.json_response({"error": "bad_init_data"}, status=401)
    user_id = auth["user_id"]
    rows = await db.get_user_payments(user_id, limit=50)
    return web.json_response({"payments": rows})

async def _notify_admin_report(report_id, auth, cfg, reason, comment):
    from aiogram.utils.keyboard import InlineKeyboardBuilder

    reason_text = REPORT_REASON_LABELS.get(reason, reason)
    uname = f"@{auth['username']}" if auth.get("username") else f"id{auth['user_id']}"
    text = (
        f"🔔 <b>Новая заявка #{report_id}</b>\n\n"
        f"👤 Пользователь: {uname} (<code>{auth['user_id']}</code>)\n"
        f"🌍 Регион: <b>{cfg['region']}</b>\n"
        f"⚠️ Причина: {reason_text}\n"
        + (f"💬 Комментарий: <i>{comment}</i>\n" if comment else "")
    )
    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Заменить авто", callback_data=f"rep:auto:{report_id}")
    kb.button(text="📤 Заменить вручную", callback_data=f"rep:manual:{report_id}")
    kb.button(text="❌ Отклонить", callback_data=f"rep:reject:{report_id}")
    kb.button(text="🔍 Профиль юзера", callback_data=f"acard:{auth['user_id']}")
    kb.adjust(2, 2)

    for admin_id in ADMIN_IDS:
        try:
            await bot.send_message(admin_id, text, reply_markup=kb.as_markup())
        except Exception as e:
            log.warning("notify_admin_report to %s failed: %s", admin_id, e)
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
        "active_delta": None,
        "stock_delta": None,
        "stock_alert": bool(low_stock),
    })

@routes.post("/freeze_config")
async def api_freeze_config(request):
    auth = await _auth(request)
    if not auth:
        return web.json_response({"error": "bad_init_data"}, status=401)
    user_id = auth["user_id"]
    body = request["_body"]

    try:
        config_id = int(body.get("config_id"))
    except (TypeError, ValueError):
        return web.json_response({"error": "bad_config_id"}, status=400)

    cfg = await db.get_config(config_id)
    if not cfg or cfg.get("user_id") != user_id or cfg.get("status") != "sold":
        return web.json_response({"error": "not_found"}, status=404)

    ok, nxt = await db.can_freeze(config_id, FREEZE_COOLDOWN_DAYS)
    if not ok:
        await db.log_event(user_id, "freeze_failed",
                            meta={"reason": "cooldown", "region": cfg["region"], "config_id": config_id},
                            source="webapp")
        return web.json_response({
            "error": "cooldown",
            "next_available": (nxt or "")[:10],
        }, status=409)

    balance = await db.get_balance(user_id)
    if balance < FREEZE_PRICE:
        await db.log_event(user_id, "freeze_failed", amount=FREEZE_PRICE,
                            meta={"reason": "need_topup", "region": cfg["region"], "balance": balance},
                            source="webapp")
        return web.json_response({
            "error": "need_topup",
            "to_pay": FREEZE_PRICE,
            "balance": balance,
        }, status=409)

    if not await db.deduct_balance(user_id, FREEZE_PRICE):
        fresh_balance = await db.get_balance(user_id)
        await db.log_event(user_id, "freeze_failed", amount=FREEZE_PRICE,
                            meta={"reason": "need_topup_race", "region": cfg["region"]},
                            source="webapp")
        return web.json_response({
            "error": "need_topup",
            "to_pay": FREEZE_PRICE,
            "balance": fresh_balance,
        }, status=409)

    new_exp = await db.extend_config(config_id, FREEZE_DAYS)
    await db.mark_frozen(config_id)
    new_balance = await db.get_balance(user_id)
    await db.log_event(user_id, "freeze", amount=FREEZE_PRICE,
                        meta={"region": cfg["region"], "config_id": config_id, "days": FREEZE_DAYS},
                        source="webapp")

    return web.json_response({
        "ok": True,
        "config_id": config_id,
        "new_expires_at": new_exp.strftime("%Y-%m-%d"),
        "balance": new_balance,
    })
# ─────────────────────────────── запуск ───────────────────────────────

async def on_startup(app: web.Application):
    app["bot"] = bot   
    await db.init_db()
    await store.load_from_db()
    import bot as bot_module
    app["bot_task"] = asyncio.create_task(bot_module.main())
    log.info("Бот запущен как фоновая задача, веб-сервер поднят.")


async def on_cleanup(app: web.Application):
    task = app.get("bot_task")
    if task:
        task.cancel()
    await bot.session.close()


def build_app() -> web.Application:
    app = web.Application()
    app.add_routes(routes)
    app.add_routes(admin_api.routes)
    app.add_routes(team_api.routes)     # ← добавить эту строку
    if os.path.isdir(STATIC_DIR):
        app.router.add_static("/static/", STATIC_DIR, show_index=False)
    app.on_startup.append(on_startup)
    app.on_cleanup.append(on_cleanup)
    return app


if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    web.run_app(build_app(), host="0.0.0.0", port=port)
