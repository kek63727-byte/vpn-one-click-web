"""
Admin API для мини-аппа: те же действия, что в handlers_admin.py (панель в боте),
но как HTTP-эндпоинты для WebApp. Подключается в app.py:

    import admin_api
    app.add_routes(admin_api.routes)
    app["bot"] = bot   # уже создан в app.py — просто сохранить ссылку в app-контейнере

Все эндпоинты — POST, тело JSON, обязательно поле init_data (проверяется подпись
Telegram WebApp + что user_id входит в ADMIN_IDS). Формат ошибок единый:
{"error": "forbidden"} / {"error": "bad_init_data"} и т.д., код 401/403/400/404.
"""

import hashlib
import hmac
import json
import logging
from datetime import timedelta
from urllib.parse import parse_qsl

from aiohttp import web

import ab
import db
import store
from config import ADMIN_IDS, BOT_TOKEN, PLAN_ORDER, PLANS, RESTOCK_BATCH, RESTOCK_THRESHOLD

log = logging.getLogger("admin_api")
routes = web.RouteTableDef()

_PERIOD_RU = {"month": "1 мес", "3month": "3 мес", "6month": "6 мес", "year": "1 год"}


# ───────────────────────── авторизация (та же проверка initData, что в app.py) ─────────────────────────

def _parse_init_data(init_data: str) -> dict | None:
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
        return {"user_id": int(user["id"]), "username": user.get("username")}
    except Exception as e:
        log.warning("bad init_data: %s", e)
        return None


async def _admin_auth(request: web.Request):
    """Возвращает (auth_dict, body) либо кидает web.HTTPUnauthorized/HTTPForbidden."""
    try:
        body = await request.json()
    except Exception:
        body = {}
    auth = _parse_init_data(body.get("init_data", ""))
    if not auth:
        raise web.HTTPUnauthorized(text=json.dumps({"error": "bad_init_data"}),
                                    content_type="application/json")
    if auth["user_id"] not in ADMIN_IDS:
        raise web.HTTPForbidden(text=json.dumps({"error": "forbidden"}),
                                 content_type="application/json")
    return auth, body


def _bot(request: web.Request):
    return request.app.get("bot")


# ══════════════════════════ 1. СТАТИСТИКА ══════════════════════════

@routes.post("/admin/stats_full")
async def admin_stats_full(request):
    await _admin_auth(request)
    s = await db.stats_extended()
    breakdown = await db.active_subs_breakdown()
    mrr = 0.0
    for plan, period, c in breakdown:
        price = store.get_price(plan, 1, period)
        monthly = price if period == "month" else (price / 12 if period == "year" else 0)
        mrr += monthly * c
    conv = await db.trial_conversion()
    churn = await db.churn_30d()
    stars = next((x for x in s["by_currency"] if x["currency"] == "XTR"), None)
    return web.json_response({
        "day_rub": s["day"][0], "day_cnt": s["day"][1],
        "week_rub": s["week"][0], "month_rub": s["month"][0], "all_rub": s["all"][0],
        "stars_total": stars["s"] if stars else 0,
        "users": s["users"], "total_balance": s["total_balance"],
        "pending_preorders": s["pending_preorders"], "active_subs": s["active_subs"],
        "free_paid": s["free_paid"], "free_trial": s["free_trial"],
        "mrr": round(mrr), "trial_conv_rate": round(conv["rate"], 1),
        "trial_conv_n": f"{conv['converted']}/{conv['trials']}",
        "churn_rate": round(churn["rate"], 1), "churn_n": f"{churn['churned']}/{churn['expired']}",
    })


# ══════════════════════════ 2. ПОЛЬЗОВАТЕЛИ / БАН ══════════════════════════

@routes.post("/admin/users")
async def admin_users(request):
    _, body = await _admin_auth(request)
    q = (body.get("search") or "").strip()
    if q:
        u = await db.find_user(q)
        rows = [u] if u else []
    else:
        offset = int(body.get("offset") or 0)
        rows = await db.list_users(10, offset)
    return web.json_response({"users": rows, "total": await db.count_users()})


@routes.post("/admin/user_card")
async def admin_user_card(request):
    _, body = await _admin_auth(request)
    uid = int(body.get("user_id"))
    u = await db.user_card(uid)
    if not u:
        return web.json_response({"error": "not_found"}, status=404)
    return web.json_response({"user": u})


@routes.post("/admin/user_action")
async def admin_user_action(request):
    auth, body = await _admin_auth(request)
    bot = _bot(request)
    uid = int(body.get("user_id"))
    action = body.get("action")
    val = body.get("value")

    if action == "days":
        days = int(val)
        applied, region = await db.extend_active(uid, days)
        if days > 0 and not applied:
            await db.add_bonus_days(uid, days)
        if bot:
            try:
                if days >= 0:
                    await bot.send_message(uid, f"🎁 Администратор начислил тебе <b>{days}</b> дней!")
            except Exception:
                pass
    elif action == "balance":
        amount = int(val)
        if amount >= 0:
            await db.add_balance(uid, amount)
        else:
            await db.deduct_balance(uid, -amount)
        if bot:
            try:
                sign = "начислил" if amount >= 0 else "списал"
                await bot.send_message(uid, f"💰 Администратор {sign} <b>{abs(amount)} ₽</b> на балансе.")
            except Exception:
                pass
    elif action == "ban":
        await db.set_banned(uid, True)
    elif action == "unban":
        await db.set_banned(uid, False)
    elif action == "noprem":
        premium_plans = [k for k, v in PLANS.items() if v.get("premium_access")]
        await db.disable_premium(uid, premium_plans)
    elif action == "refund":
        order = await db.last_paid_order(uid)
        if not order:
            return web.json_response({"error": "no_order"}, status=404)
        await db.add_balance(uid, order["rub"])
        await db.set_order_status(order["id"], "refunded")
    elif action == "message":
        if bot and val:
            try:
                await bot.send_message(uid, str(val))
            except Exception as e:
                return web.json_response({"error": str(e)}, status=502)
    else:
        return web.json_response({"error": "unknown_action"}, status=400)

    u = await db.user_card(uid)
    return web.json_response({"ok": True, "user": u})


# ══════════════════════════ 3. СЕРВЕРЫ / РЕГИОНЫ ══════════════════════════

@routes.post("/admin/servers")
async def admin_servers(request):
    await _admin_auth(request)
    return web.json_response({"regions": await db.catalog_with_stock()})


@routes.post("/admin/servers/add")
async def admin_servers_add(request):
    _, body = await _admin_auth(request)
    region = (body.get("region") or "").strip()
    if not region:
        return web.json_response({"error": "empty_region"}, status=400)
    await db.catalog_add(region, bool(body.get("premium")))
    await store.load_from_db()
    return web.json_response({"ok": True})


@routes.post("/admin/servers/toggle_premium")
async def admin_servers_toggle_premium(request):
    _, body = await _admin_auth(request)
    region = body.get("region")
    await db.catalog_set_premium(region, bool(body.get("premium")))
    await store.load_from_db()
    return web.json_response({"ok": True})


@routes.post("/admin/servers/rename")
async def admin_servers_rename(request):
    _, body = await _admin_auth(request)
    old, new = body.get("old"), (body.get("new") or "").strip()
    if not new:
        return web.json_response({"error": "empty_name"}, status=400)
    await db.catalog_rename(old, new)
    await store.load_from_db()
    return web.json_response({"ok": True})


@routes.post("/admin/servers/delete")
async def admin_servers_delete(request):
    _, body = await _admin_auth(request)
    region = body.get("region")
    await db.catalog_remove(region)
    await store.load_from_db()
    return web.json_response({"ok": True})


# ══════════════════════════ 4. ЦЕНЫ ══════════════════════════

@routes.post("/admin/prices")
async def admin_prices(request):
    await _admin_auth(request)
    out = []
    for plan in PLAN_ORDER:
        prices = store.plan_prices(plan)
        items = []
        for dev in (1, 2, 4):
            for per in ("month", "3month", "6month", "year"):
                rub = prices.get((dev, per))
                if rub is not None:
                    items.append({"devices": dev, "period": per,
                                 "period_ru": _PERIOD_RU.get(per, per), "rub": rub})
        out.append({"plan": plan, "title": PLANS[plan]["title"], "items": items})
    return web.json_response({"plans": out})


@routes.post("/admin/prices/set")
async def admin_prices_set(request):
    _, body = await _admin_auth(request)
    plan = body.get("plan")
    devices = int(body.get("devices"))
    period = body.get("period")
    rub = int(body.get("rub"))
    if plan not in PLANS or rub < 0:
        return web.json_response({"error": "bad_value"}, status=400)
    await db.save_price(plan, devices, period, rub)
    store.set_price_cache(plan, devices, period, rub)
    return web.json_response({"ok": True})


# ══════════════════════════ 5. ПРОМОКОДЫ ══════════════════════════

@routes.post("/admin/promo")
async def admin_promo(request):
    await _admin_auth(request)
    return web.json_response({"promos": await db.list_promos()})


@routes.post("/admin/promo/create")
async def admin_promo_create(request):
    _, body = await _admin_auth(request)
    code = (body.get("code") or "").strip().upper()
    kind = body.get("kind")  # "discount" | "balance"
    value = int(body.get("value") or 0)
    max_uses = int(body.get("max_uses") or 0)
    if not code or kind not in ("discount", "balance") or value <= 0:
        return web.json_response({"error": "bad_value"}, status=400)
    if kind == "discount":
        await db.create_promo(code, "discount", percent=value, max_uses=max_uses)
    else:
        await db.create_promo(code, "balance", amount_rub=value, max_uses=max_uses)
    return web.json_response({"ok": True, "promos": await db.list_promos()})


@routes.post("/admin/promo/toggle")
async def admin_promo_toggle(request):
    _, body = await _admin_auth(request)
    await db.toggle_promo(body.get("code"))
    return web.json_response({"ok": True, "promos": await db.list_promos()})


@routes.post("/admin/promo/delete")
async def admin_promo_delete(request):
    _, body = await _admin_auth(request)
    await db.delete_promo(body.get("code"))
    return web.json_response({"ok": True, "promos": await db.list_promos()})


# ══════════════════════════ 6. РАССЫЛКА ══════════════════════════

@routes.post("/admin/broadcast")
async def admin_broadcast(request):
    _, body = await _admin_auth(request)
    bot = _bot(request)
    text = (body.get("text") or "").strip()
    if not text:
        return web.json_response({"error": "empty_text"}, status=400)
    if not bot:
        return web.json_response({"error": "bot_unavailable"}, status=503)
    user_ids = await db.all_user_ids()
    ok = fail = 0
    for uid in user_ids:
        try:
            await bot.send_message(uid, text)
            ok += 1
        except Exception:
            fail += 1
    return web.json_response({"ok": True, "sent": ok, "failed": fail, "total": len(user_ids)})


# ══════════════════════════ 7. A/B ТЕСТЫ ══════════════════════════

@routes.post("/admin/ab")
async def admin_ab(request):
    await _admin_auth(request)
    exp = ab.active_experiment()
    if not exp:
        return web.json_response({"enabled": False})
    rows = await db.ab_report(exp)
    variants = []
    for r in rows:
        users, trials, paid = r["users"] or 0, r["trials"] or 0, r["paid"] or 0
        params = ab.AB_EXPERIMENTS[exp]["variants"].get(r["variant"], {})
        variants.append({
            "variant": r["variant"], "params": params, "users": users, "trials": trials,
            "paid": paid,
            "conv_all": round(paid / users * 100, 1) if users else 0,
            "conv_trial": round(paid / trials * 100, 1) if trials else 0,
        })
    return web.json_response({
        "enabled": True, "title": ab.experiment_title(exp),
        "metric": ab.AB_EXPERIMENTS[exp].get("metric", ""),
        "variants": variants,
    })


# ══════════════════════════ 8. БЭКАП БАЗЫ ══════════════════════════

@routes.post("/admin/backup")
async def admin_backup(request):
    await _admin_auth(request)
    from config import DB_PATH
    try:
        with open(DB_PATH, "rb") as f:
            data = f.read()
    except OSError as e:
        return web.json_response({"error": str(e)}, status=500)
    return web.Response(
        body=data, content_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="backup.db"'},
    )


# ══════════════════════════ 9. ЗАЯВКИ НА ЗАКУПКУ (СКЛАД) ══════════════════════════

@routes.post("/admin/restock")
async def admin_restock(request):
    await _admin_auth(request)
    orders = await db.list_restock(active_only=True)
    low = await db.low_stock_regions(RESTOCK_THRESHOLD)
    return web.json_response({"orders": orders, "low_stock": low, "batch": RESTOCK_BATCH})


@routes.post("/admin/restock/create")
async def admin_restock_create(request):
    _, body = await _admin_auth(request)
    region = body.get("region")
    if not region:
        return web.json_response({"error": "empty_region"}, status=400)
    rid = await db.create_restock(region, RESTOCK_BATCH, urgent=bool(body.get("urgent")))
    return web.json_response({"ok": True, "id": rid})


@routes.post("/admin/restock/update")
async def admin_restock_update(request):
    """Универсальное обновление заявки: amount_rub / pay_url / status."""
    _, body = await _admin_auth(request)
    rid = int(body.get("id"))
    fields = {}
    if "amount_rub" in body:
        fields["amount_rub"] = int(body["amount_rub"])
    if "pay_url" in body:
        url = (body["pay_url"] or "").strip()
        if not url.lower().startswith("https://"):
            return web.json_response({"error": "bad_url"}, status=400)
        fields["pay_url"] = url
        fields["status"] = "awaiting_payment"
    if "status" in body and body["status"] in ("paid", "done", "canceled"):
        fields["status"] = body["status"]
    if not fields:
        return web.json_response({"error": "nothing_to_update"}, status=400)
    await db.set_restock(rid, **fields)
    return web.json_response({"ok": True, "order": await db.get_restock(rid)})


@routes.post("/admin/restock/add_configs")
async def admin_restock_add_configs(request):
    """Вставка .conf текстом (несколько конфигов, разделённых пустой строкой
    или блоками [Interface]) — так же, как в панели бота."""
    _, body = await _admin_auth(request)
    rid = int(body.get("id"))
    order = await db.get_restock(rid)
    if not order:
        return web.json_response({"error": "not_found"}, status=404)
    raw = (body.get("text") or "").replace("\r", "")
    low = raw.lower()
    if low.count("[interface]") <= 1:
        blocks = [raw.strip()] if raw.strip() else []
    else:
        blocks, cur = [], []
        for line in raw.split("\n"):
            if line.strip().lower() == "[interface]" and cur:
                blocks.append("\n".join(cur).strip())
                cur = [line]
            else:
                cur.append(line)
        if cur:
            blocks.append("\n".join(cur).strip())
        blocks = [b for b in blocks if b]
    premium = store.is_premium_region(order["region"])
    added, skipped = await db.add_configs_bulk(order["region"], premium, False, blocks,
                                                body.get("source"))
    if added:
        await db.restock_inc_added(rid, added)
    return web.json_response({"ok": True, "added": added, "skipped": skipped,
                              "order": await db.get_restock(rid)})

# ══════════════════════════ 10. ТРАНЗАКЦИИ ══════════════════════════

@routes.post("/admin/transactions")
async def admin_transactions(request):
    """Лента пополнений + покупок с деталями по каждому юзеру."""
    _, body = await _admin_auth(request)
    limit = min(int(body.get("limit") or 60), 200)
    kind = body.get("kind") or "all"  # all | topup | order

    import aiosqlite
    from config import DB_PATH

    items = []
    async with aiosqlite.connect(DB_PATH) as dbx:
        dbx.row_factory = aiosqlite.Row

        if kind in ("all", "topup"):
            cur = await dbx.execute(
                "SELECT t.id, t.user_id, t.amount_rub, t.method, t.status, t.created_at, "
                "u.username, u.full_name, COALESCE(u.balance_rub,0) balance_rub "
                "FROM topups t LEFT JOIN users u ON u.user_id=t.user_id "
                "WHERE t.status='paid' ORDER BY t.created_at DESC LIMIT ?", (limit,))
            for r in await cur.fetchall():
                items.append({
                    "kind": "topup", "id": r["id"],
                    "user_id": r["user_id"], "username": r["username"],
                    "full_name": r["full_name"], "balance_rub": r["balance_rub"],
                    "amount": r["amount_rub"], "method": (r["method"] or "—").upper(),
                    "at": r["created_at"],
                })

        if kind in ("all", "order"):
            cur = await dbx.execute(
                "SELECT o.id, o.user_id, o.plan, o.devices, o.period, o.region, "
                "o.config_ids, o.rub, o.discount, o.full_rub, o.promo, o.created_at, "
                "u.username, u.full_name, COALESCE(u.balance_rub,0) balance_rub, "
                "(SELECT COUNT(*) FROM configs c "
                " WHERE c.user_id=o.user_id AND c.status='sold' AND c.is_trial=0) active_configs "
                "FROM orders o LEFT JOIN users u ON u.user_id=o.user_id "
                "WHERE o.status='paid' ORDER BY o.created_at DESC LIMIT ?", (limit,))
            for r in await cur.fetchall():
                cfg_ids = [x for x in (r["config_ids"] or "").split(",") if x]
                items.append({
                    "kind": "order", "id": r["id"],
                    "user_id": r["user_id"], "username": r["username"],
                    "full_name": r["full_name"], "balance_rub": r["balance_rub"],
                    "amount": r["rub"], "full_rub": r["full_rub"] or r["rub"],
                    "discount": r["discount"] or 0, "promo": r["promo"],
                    "plan": r["plan"] or "standard", "devices": r["devices"],
                    "period": r["period"], "region": r["region"],
                    "config_count": len(cfg_ids),
                    "active_configs": r["active_configs"],
                    "at": r["created_at"],
                })

        # сводка
        row = await (await dbx.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount_rub),0) FROM topups WHERE status='paid'")).fetchone()
        topup_cnt, topup_sum = row[0], row[1]

        row = await (await dbx.execute(
            "SELECT COUNT(*), COALESCE(SUM(rub),0) FROM orders WHERE status='paid'")).fetchone()
        order_cnt, order_sum = row[0], row[1]

        active_cfg = (await (await dbx.execute(
            "SELECT COUNT(*) FROM configs WHERE status='sold' AND is_trial=0")).fetchone())[0]
        active_trial = (await (await dbx.execute(
            "SELECT COUNT(*) FROM configs WHERE status='sold' AND is_trial=1")).fetchone())[0]
        total_bal = (await (await dbx.execute(
            "SELECT COALESCE(SUM(balance_rub),0) FROM users")).fetchone())[0]

    items.sort(key=lambda x: x.get("at") or "", reverse=True)

    return web.json_response({
        "items": items[:limit],
        "summary": {
            "topup_cnt": topup_cnt, "topup_sum": topup_sum,
            "order_cnt": order_cnt, "order_sum": order_sum,
            "active_configs": active_cfg, "active_trials": active_trial,
            "total_balance": total_bal,
        },
    })

# ═══════════════════════════════════════════════════════════════
# ПАТЧ ДЛЯ admin_api.py — добавь этот блок в САМЫЙ НИЗ файла (после
# раздела "10. ТРАНЗАКЦИИ", после последней функции admin_transactions).
# ВАЖНО: в оригинальном admin_api.py aiosqlite и DB_PATH импортируются
# только ЛОКАЛЬНО внутри функции admin_transactions — на уровне модуля
# их нет. Поэтому этот патч сам импортирует их наверху блока.
# web / routes / _admin_auth уже есть в файле — их трогать не нужно.
# ═══════════════════════════════════════════════════════════════

import aiosqlite
from config import DB_PATH


_TEAM_ROLE_TITLES = {
    "qa": "🛡 Тестировщик (QA)", "idea": "💡 Креатор идей", "hr": "👥 HR",
    "dev": "💻 Разработчик", "design": "🎨 Дизайнер", "marketing": "📣 Маркетолог/SMM",
    "other": "🧩 Другое",
}
_TEAM_EXP_TITLES = {
    "none": "Без опыта", "lt1": "До 1 года", "1-3": "1–3 года", "3-5": "3–5 лет", "5plus": "5+ лет",
}


async def _team_ensure_table():
    async with aiosqlite.connect(DB_PATH) as dbx:
        await dbx.execute(
            """
            CREATE TABLE IF NOT EXISTS team_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL, username TEXT, full_name TEXT,
                role TEXT NOT NULL, experience TEXT NOT NULL,
                salary_from INTEGER, salary_to INTEGER, currency TEXT, payment_type TEXT,
                comment TEXT, contact_tg TEXT NOT NULL,
                resume_filename TEXT, resume_mime TEXT, resume_b64 TEXT,
                status TEXT NOT NULL DEFAULT 'new', created_at TEXT NOT NULL
            )
            """
        )
        await dbx.commit()


@routes.post("/admin/team_applications")
async def admin_team_applications(request):
    """Список анкет. body: {status: 'all'|'new'|'contacted'|'hired'|'rejected'}"""
    _, body = await _admin_auth(request)
    await _team_ensure_table()
    status = body.get("status") or "all"

    q = "SELECT * FROM team_applications"
    params = ()
    if status != "all":
        q += " WHERE status=?"
        params = (status,)
    q += " ORDER BY created_at DESC LIMIT 200"

    async with aiosqlite.connect(DB_PATH) as dbx:
        dbx.row_factory = aiosqlite.Row
        rows = [dict(r) for r in await (await dbx.execute(q, params)).fetchall()]
        counts_row = await (await dbx.execute(
            "SELECT status, COUNT(*) c FROM team_applications GROUP BY status"
        )).fetchall()
    counts = {r[0]: r[1] for r in counts_row}

    for r in rows:
        r["role_title"] = _TEAM_ROLE_TITLES.get(r["role"], r["role"])
        r["experience_title"] = _TEAM_EXP_TITLES.get(r["experience"], r["experience"])
        r.pop("resume_b64", None)  # не гоняем base64 в списке — только по запросу карточки

    return web.json_response({"applications": rows, "counts": counts})


@routes.post("/admin/team_applications/card")
async def admin_team_application_card(request):
    """Полная карточка заявки, включая base64 резюме (для скачивания)."""
    _, body = await _admin_auth(request)
    app_id = int(body.get("id"))
    async with aiosqlite.connect(DB_PATH) as dbx:
        dbx.row_factory = aiosqlite.Row
        row = await (await dbx.execute(
            "SELECT * FROM team_applications WHERE id=?", (app_id,)
        )).fetchone()
    if not row:
        return web.json_response({"error": "not_found"}, status=404)
    r = dict(row)
    r["role_title"] = _TEAM_ROLE_TITLES.get(r["role"], r["role"])
    r["experience_title"] = _TEAM_EXP_TITLES.get(r["experience"], r["experience"])
    return web.json_response({"application": r})


@routes.post("/admin/team_applications/status")
async def admin_team_application_status(request):
    """body: {id, status: 'new'|'contacted'|'hired'|'rejected'}"""
    _, body = await _admin_auth(request)
    app_id = int(body.get("id"))
    status = body.get("status")
    if status not in ("new", "contacted", "hired", "rejected"):
        return web.json_response({"error": "bad_status"}, status=400)
    async with aiosqlite.connect(DB_PATH) as dbx:
        await dbx.execute("UPDATE team_applications SET status=? WHERE id=?", (status, app_id))
        await dbx.commit()
    return web.json_response({"ok": True})
