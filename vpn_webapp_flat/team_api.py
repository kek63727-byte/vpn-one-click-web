"""
team_api.py — приём заявок "Присоединиться к команде" из мини-аппа.
Доступно ЛЮБОМУ валидному пользователю Telegram (не только админам) —
это форма кандидата, а не админ-функция.

Подключается в app.py рядом с admin_api:

    import team_api
    app.add_routes(team_api.routes)

При получении заявки:
  1) сохраняет её в таблицу team_applications (создаётся автоматически);
  2) сразу шлёт уведомление всем ADMIN_IDS в бота;
  3) заявку также можно посмотреть в разделе админки "Заявки в команду"
     (см. admin_api_team_patch.py + admin_js_team_patch.js).
"""

import logging
from datetime import datetime, timezone

import aiosqlite
from aiohttp import web

from admin_api import _parse_init_data  # переиспользуем ту же проверку initData
from config import ADMIN_IDS, DB_PATH

log = logging.getLogger("team_api")
routes = web.RouteTableDef()

ROLE_TITLES = {
    "qa": "🛡 Тестировщик (QA)",
    "idea": "💡 Креатор идей",
    "hr": "👥 Поиск персонала (HR)",
    "dev": "💻 Программист / Разработчик",
    "design": "🎨 Дизайнер",
    "marketing": "📣 Маркетолог / SMM",
    "other": "🧩 Другое",
}
EXP_TITLES = {
    "none": "Без опыта",
    "lt1": "До 1 года",
    "1-3": "1–3 года",
    "3-5": "3–5 лет",
    "5plus": "5+ лет",
}
PAY_TITLES = {"fixed": "Фиксированная оплата", "percent": "Процент от прибыли"}

MAX_FILE_BYTES = 10 * 1024 * 1024
_MAX_B64_LEN = int(MAX_FILE_BYTES * 4 / 3) + 100


async def _ensure_table():
    async with aiosqlite.connect(DB_PATH) as dbx:
        await dbx.execute(
            """
            CREATE TABLE IF NOT EXISTS team_applications (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT,
                full_name TEXT,
                role TEXT NOT NULL,
                experience TEXT NOT NULL,
                salary_from INTEGER,
                salary_to INTEGER,
                currency TEXT,
                payment_type TEXT,
                comment TEXT,
                contact_tg TEXT NOT NULL,
                resume_filename TEXT,
                resume_mime TEXT,
                resume_b64 TEXT,
                status TEXT NOT NULL DEFAULT 'new',
                created_at TEXT NOT NULL
            )
            """
        )
        await dbx.commit()


def _fmt_notification(app_id: int, auth: dict, f: dict) -> str:
    salary_line = ""
    if f.get("salary_from") or f.get("salary_to"):
        rng = f"{f.get('salary_from') or '—'}–{f.get('salary_to') or '—'}"
        salary_line = f"\n💰 Зарплата: {rng} {f.get('currency', 'RUB')} · {PAY_TITLES.get(f.get('payment_type'), '')}"
    lines = [
        f"🆕 <b>Новая заявка в команду</b> #{app_id}",
        "",
        f"👤 {f.get('full_name') or '—'}"
        + (f" · @{auth.get('username')}" if auth.get("username") else "")
        + f" (ID {auth['user_id']})",
        f"📇 Роль: <b>{ROLE_TITLES.get(f['role'], f['role'])}</b>",
        f"📈 Опыт: {EXP_TITLES.get(f['experience'], f['experience'])}" + salary_line,
        f"💬 Связь: {f['contact_tg']}",
    ]
    if f.get("comment"):
        lines.append(f"\n📝 {f['comment']}")
    if f.get("resume_filename"):
        lines.append(f"\n📎 Резюме: {f['resume_filename']}")
    return "\n".join(lines)


@routes.post("/join_team")
async def join_team(request: web.Request):
    await _ensure_table()
    try:
        body = await request.json()
    except Exception:
        return web.json_response({"error": "bad_request"}, status=400)

    auth = _parse_init_data(body.get("init_data", ""))
    if not auth:
        return web.json_response({"error": "bad_init_data"}, status=401)

    role = body.get("role")
    experience = body.get("experience")
    contact_tg = (body.get("contact_tg") or "").strip()

    if role not in ROLE_TITLES:
        return web.json_response({"error": "bad_role"}, status=400)
    if experience not in EXP_TITLES:
        return web.json_response({"error": "bad_experience"}, status=400)
    if not contact_tg:
        return web.json_response({"error": "no_contact"}, status=400)
    if not contact_tg.startswith("@"):
        contact_tg = "@" + contact_tg

    def _int_or_none(v):
        try:
            return int(v) if v not in (None, "") else None
        except (TypeError, ValueError):
            return None

    salary_from = _int_or_none(body.get("salary_from"))
    salary_to = _int_or_none(body.get("salary_to"))
    currency = body.get("currency") or "RUB"
    payment_type = body.get("payment_type") or "fixed"
    comment = (body.get("comment") or "").strip()[:500]
    full_name = (body.get("full_name") or "").strip()[:120]

    resume_filename = body.get("resume_filename")
    resume_mime = body.get("resume_mime")
    resume_b64 = body.get("resume_b64")
    if resume_b64 and len(resume_b64) > _MAX_B64_LEN:
        return web.json_response({"error": "file_too_large"}, status=400)

    created_at = datetime.now(timezone.utc).isoformat(timespec="seconds")

    async with aiosqlite.connect(DB_PATH) as dbx:
        cur = await dbx.execute(
            "INSERT INTO team_applications "
            "(user_id, username, full_name, role, experience, salary_from, salary_to, "
            " currency, payment_type, comment, contact_tg, resume_filename, resume_mime, "
            " resume_b64, status, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                auth["user_id"], auth.get("username"), full_name, role, experience,
                salary_from, salary_to, currency, payment_type, comment, contact_tg,
                resume_filename, resume_mime, resume_b64, "new", created_at,
            ),
        )
        await dbx.commit()
        app_id = cur.lastrowid

    bot = request.app.get("bot")
    if bot:
        text = _fmt_notification(
            app_id, auth,
            {
                "role": role, "experience": experience, "salary_from": salary_from,
                "salary_to": salary_to, "currency": currency, "payment_type": payment_type,
                "comment": comment, "contact_tg": contact_tg, "full_name": full_name,
                "resume_filename": resume_filename,
            },
        )
        for admin_id in ADMIN_IDS:
            try:
                await bot.send_message(admin_id, text)
            except Exception as e:
                log.warning("team notify failed for %s: %s", admin_id, e)

    return web.json_response({"ok": True, "id": app_id})
