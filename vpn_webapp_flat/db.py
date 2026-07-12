"""Слой БД (SQLite): конфиги, пользователи, заказы, рефералы, запасы, триал-пул."""

from datetime import datetime, timedelta, timezone

import aiosqlite

from config import DB_PATH, DEFAULT_REGION_CATALOG, LOW_STOCK_THRESHOLD, ORDER_TTL_MIN, PERIOD_DAYS


def now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.isoformat()


SCHEMA = """
CREATE TABLE IF NOT EXISTS configs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region TEXT NOT NULL,
    config_text TEXT NOT NULL,
    is_premium INTEGER NOT NULL DEFAULT 0,
    is_trial INTEGER NOT NULL DEFAULT 0,
    status TEXT NOT NULL DEFAULT 'free',
    user_id INTEGER, plan TEXT, period TEXT,
    created_at TEXT NOT NULL, reserved_at TEXT, sold_at TEXT, expires_at TEXT
);

CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT, full_name TEXT,
    referred_by INTEGER,
    trial_used INTEGER NOT NULL DEFAULT 0,
    bonus_days INTEGER NOT NULL DEFAULT 0,
    ref_earned INTEGER NOT NULL DEFAULT 0,
    ref_balance_rub INTEGER NOT NULL DEFAULT 0,
    ref_earned_rub INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, plan TEXT, devices INTEGER, period TEXT,
    region TEXT, config_ids TEXT,
    full_rub INTEGER, discount INTEGER, rub INTEGER,
    status TEXT, created_at TEXT
);

CREATE TABLE IF NOT EXISTS payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, order_id INTEGER, amount INTEGER,
    currency TEXT, charge_id TEXT, created_at TEXT
);

CREATE TABLE IF NOT EXISTS region_state (
    region TEXT PRIMARY KEY,
    low_notified INTEGER NOT NULL DEFAULT 0,
    empty_notified INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS promo_codes (
    code TEXT PRIMARY KEY,
    kind TEXT NOT NULL DEFAULT 'discount',
    percent INTEGER NOT NULL DEFAULT 0,
    amount_rub INTEGER NOT NULL DEFAULT 0,
    max_uses INTEGER NOT NULL DEFAULT 0,
    used INTEGER NOT NULL DEFAULT 0,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS topups (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, amount_rub INTEGER, method TEXT,
    status TEXT NOT NULL DEFAULT 'pending', invoice_ref TEXT, created_at TEXT
);

CREATE TABLE IF NOT EXISTS preorders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, plan TEXT, devices INTEGER, period TEXT, region TEXT,
    full_rub INTEGER, discount INTEGER, rub INTEGER, promo TEXT,
    status TEXT NOT NULL DEFAULT 'waiting', lang TEXT DEFAULT 'ru', created_at TEXT
);

CREATE TABLE IF NOT EXISTS subscriptions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, plan TEXT, devices INTEGER, period TEXT,
    expires_at TEXT, status TEXT NOT NULL DEFAULT 'active', created_at TEXT
);

CREATE TABLE IF NOT EXISTS region_change_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER, config_id INTEGER, from_region TEXT,
    status TEXT NOT NULL DEFAULT 'pending', created_at TEXT
);

CREATE TABLE IF NOT EXISTS promo_redemptions (
    code TEXT NOT NULL,
    user_id INTEGER NOT NULL,
    created_at TEXT,
    PRIMARY KEY (code, user_id)
);

CREATE TABLE IF NOT EXISTS settings_prices (
    plan TEXT NOT NULL,
    devices INTEGER NOT NULL,
    period TEXT NOT NULL,
    rub INTEGER NOT NULL,
    PRIMARY KEY (plan, devices, period)
);

CREATE TABLE IF NOT EXISTS region_catalog (
    region TEXT PRIMARY KEY,
    is_premium INTEGER NOT NULL DEFAULT 0,
    position INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS restock_orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    region TEXT NOT NULL,
    need INTEGER NOT NULL DEFAULT 0,
    amount_rub INTEGER,
    pay_url TEXT,
    status TEXT NOT NULL DEFAULT 'new',
    added INTEGER NOT NULL DEFAULT 0,
    urgent INTEGER NOT NULL DEFAULT 0,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS replacements (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    old_id INTEGER, new_id INTEGER,
    region TEXT, reason TEXT, old_source TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS payout_requests (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    amount_rub INTEGER NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    created_at TEXT,
    updated_at TEXT
);

CREATE INDEX IF NOT EXISTS idx_configs_rs ON configs(region, status);
"""


async def _ensure_column(db, table, col, ddl):
    cur = await db.execute(f"PRAGMA table_info({table})")
    cols = [r[1] for r in await cur.fetchall()]
    if col not in cols:
        await db.execute(f"ALTER TABLE {table} ADD COLUMN {ddl}")


async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        for col, ddl in [
            ("is_premium", "is_premium INTEGER NOT NULL DEFAULT 0"),
            ("is_trial", "is_trial INTEGER NOT NULL DEFAULT 0"),
            ("plan", "plan TEXT"), ("period", "period TEXT"),
        ]:
            await _ensure_column(db, "configs", col, ddl)
        for col, ddl in [
            ("referred_by", "referred_by INTEGER"),
            ("trial_used", "trial_used INTEGER NOT NULL DEFAULT 0"),
            ("bonus_days", "bonus_days INTEGER NOT NULL DEFAULT 0"),
            ("ref_earned", "ref_earned INTEGER NOT NULL DEFAULT 0"),
            ("ref_balance_rub", "ref_balance_rub INTEGER NOT NULL DEFAULT 0"),
            ("ref_earned_rub", "ref_earned_rub INTEGER NOT NULL DEFAULT 0"),
            ("lang", "lang TEXT NOT NULL DEFAULT 'ru'"),
            ("balance_rub", "balance_rub INTEGER NOT NULL DEFAULT 0"),
            ("banned", "banned INTEGER NOT NULL DEFAULT 0"),
            ("autopay", "autopay INTEGER NOT NULL DEFAULT 0"),
            ("ref_cash_rub", "ref_cash_rub INTEGER NOT NULL DEFAULT 0"),
            ("ref_milestone", "ref_milestone INTEGER NOT NULL DEFAULT 0"),
            ("ab_exp", "ab_exp TEXT"),
            ("ab_variant", "ab_variant TEXT"),
            ("verified", "verified INTEGER NOT NULL DEFAULT 0"),
            ("channel_bonus_claimed", "channel_bonus_claimed INTEGER NOT NULL DEFAULT 0"),
            ("trial_reminded", "trial_reminded INTEGER NOT NULL DEFAULT 0"),
        ]:
            await _ensure_column(db, "users", col, ddl)
        for col, ddl in [
            ("full_rub", "full_rub INTEGER"), ("discount", "discount INTEGER"),
            ("promo", "promo TEXT"),
        ]:
            await _ensure_column(db, "orders", col, ddl)
        await _ensure_column(db, "configs", "renew_notified", "renew_notified INTEGER NOT NULL DEFAULT 0")
        await _ensure_column(db, "configs", "source", "source TEXT")
        await _ensure_column(db, "configs", "winback_notified", "winback_notified INTEGER NOT NULL DEFAULT 0")
        await _ensure_column(db, "configs", "lowbal_notified", "lowbal_notified INTEGER NOT NULL DEFAULT 0")
        await _ensure_column(db, "configs", "frozen_at", "frozen_at TEXT")
        await _ensure_column(db, "configs", "sub_id", "sub_id INTEGER")
        for col, ddl in [
            ("kind", "kind TEXT NOT NULL DEFAULT 'discount'"),
            ("amount_rub", "amount_rub INTEGER NOT NULL DEFAULT 0"),
            ("is_gift", "is_gift INTEGER NOT NULL DEFAULT 0"),
        ]:
            await _ensure_column(db, "promo_codes", col, ddl)
        # сидируем каталог регионов значениями по умолчанию (только если пусто)
        cur = await db.execute("SELECT COUNT(*) FROM region_catalog")
        if (await cur.fetchone())[0] == 0:
            for pos, (region, prem) in enumerate(DEFAULT_REGION_CATALOG):
                await db.execute(
                    "INSERT OR IGNORE INTO region_catalog(region, is_premium, position) VALUES(?,?,?)",
                    (region, 1 if prem else 0, pos),
                )
        await db.commit()


# ---------- пользователи / рефералы ----------

async def add_user(user_id, username, full_name) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT 1 FROM users WHERE user_id=?", (user_id,))
        exists = await cur.fetchone() is not None
        await db.execute(
            "INSERT INTO users(user_id, username, full_name, created_at) VALUES(?,?,?,?) "
            "ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, "
            "full_name=excluded.full_name",
            (user_id, username, full_name, iso(now())),
        )
        await db.commit()
        return not exists


async def get_user(user_id) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_referrer(user_id, referrer_id):
    if user_id == referrer_id:
        return
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET referred_by=? WHERE user_id=? AND referred_by IS NULL",
            (referrer_id, user_id),
        )
        await db.commit()


async def referral_stats(user_id) -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user_id,))
        invited = (await cur.fetchone())[0]
    u = await get_user(user_id) or {}
    return {
        "invited": invited,
        "earned_days": u.get("ref_earned", 0),
        "earned_rub": u.get("ref_earned_rub", 0),
        "balance_days": u.get("bonus_days", 0),
        "balance_rub": u.get("ref_balance_rub", 0),
        "cash_rub": u.get("ref_cash_rub", 0),
    }


async def mark_trial_used(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET trial_used=1 WHERE user_id=?", (user_id,))
        await db.commit()


async def get_lang(user_id) -> str:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT lang FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return (row[0] if row and row[0] else "ru")


async def set_lang(user_id, lang):
    if lang not in ("ru", "en"):
        lang = "ru"
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET lang=? WHERE user_id=?", (lang, user_id))
        await db.commit()


async def add_bonus_days(user_id, days):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET bonus_days=bonus_days+?, ref_earned=ref_earned+? WHERE user_id=?",
            (days, days, user_id),
        )
        await db.commit()


async def add_ref_balance(user_id, rub):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET ref_balance_rub=ref_balance_rub+?, "
            "ref_earned_rub=ref_earned_rub+? WHERE user_id=?",
            (rub, rub, user_id),
        )
        await db.commit()


async def use_ref_balance(user_id, rub):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET ref_balance_rub=MAX(0, ref_balance_rub-?) WHERE user_id=?",
            (rub, user_id),
        )
        await db.commit()


# ---------- реферальный кошелёк (выводимый реальными деньгами) ----------

async def add_ref_cash(user_id, rub):
    """Начисляет реферальный кэш (выводимый) и инкрементит lifetime-заработок."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET ref_cash_rub=ref_cash_rub+?, ref_earned_rub=ref_earned_rub+? "
            "WHERE user_id=?",
            (rub, rub, user_id),
        )
        await db.commit()


async def get_ref_cash(user_id) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT ref_cash_rub FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row and row[0] else 0


async def get_ref_milestone(user_id) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT ref_milestone FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row and row[0] else 0


async def set_ref_milestone(user_id, value):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET ref_milestone=? WHERE user_id=?", (value, user_id))
        await db.commit()


# ---------- заявки на вывод реферального баланса ----------

async def create_payout(user_id, amount) -> int | None:
    """Создаёт заявку на вывод и «холдит» сумму (списывает с реф-кэша). None — если не хватает."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT ref_cash_rub FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        have = (row[0] if row and row[0] else 0)
        if amount <= 0 or have < amount:
            return None
        await db.execute("UPDATE users SET ref_cash_rub=ref_cash_rub-? WHERE user_id=?",
                         (amount, user_id))
        cur = await db.execute(
            "INSERT INTO payout_requests(user_id, amount_rub, status, created_at, updated_at) "
            "VALUES(?,?, 'pending', ?, ?)",
            (user_id, amount, iso(now()), iso(now())),
        )
        await db.commit()
        return cur.lastrowid


async def get_payout(pid):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM payout_requests WHERE id=?", (pid,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def has_pending_payout(user_id) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM payout_requests WHERE user_id=? AND status='pending' LIMIT 1", (user_id,))
        return (await cur.fetchone()) is not None


async def set_payout_status(pid, status, refund=False):
    """Меняет статус заявки. refund=True — вернуть сумму на реф-кэш (при отклонении)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id, amount_rub, status FROM payout_requests WHERE id=?", (pid,))
        row = await cur.fetchone()
        if not row:
            return
        user_id, amount, cur_status = row
        if refund and cur_status == "pending":
            await db.execute("UPDATE users SET ref_cash_rub=ref_cash_rub+? WHERE user_id=?",
                             (amount, user_id))
        await db.execute("UPDATE payout_requests SET status=?, updated_at=? WHERE id=?",
                         (status, iso(now()), pid))
        await db.commit()


async def pending_payouts() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM payout_requests WHERE status='pending' ORDER BY created_at")
        return [dict(r) for r in await cur.fetchall()]


# ---------- история платежей клиента ----------

async def pay_history(user_id, limit=20) -> list[dict]:
    """Объединённая история: пополнения (оплаченные) + покупки подписок."""
    items = []
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT amount_rub, method, created_at FROM topups "
            "WHERE user_id=? AND status='paid' ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        for r in await cur.fetchall():
            items.append({"kind": "topup", "amount": r["amount_rub"],
                          "info": (r["method"] or "").upper(), "at": r["created_at"]})
        cur = await db.execute(
            "SELECT plan, period, region, rub, status, created_at FROM orders "
            "WHERE user_id=? AND status IN ('paid','refunded') ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )
        for r in await cur.fetchall():
            items.append({"kind": "order", "amount": r["rub"], "plan": r["plan"],
                          "period": r["period"], "region": r["region"],
                          "status": r["status"], "at": r["created_at"]})
    items.sort(key=lambda x: x["at"] or "", reverse=True)
    return items[:limit]


# ---------- воронка возврата (win-back) ----------

async def winback_candidates(after_days) -> list[dict]:
    """Истёкшие N+ дней назад подписки у тех, кто НЕ переоформил, и кому ещё не слали возврат."""
    cutoff = iso(now() - timedelta(days=after_days))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT c.id, c.user_id, c.region FROM configs c "
            "WHERE c.status='expired' AND c.is_trial=0 AND c.winback_notified=0 "
            "AND c.expires_at IS NOT NULL AND c.expires_at < ? "
            "AND NOT EXISTS (SELECT 1 FROM configs s WHERE s.user_id=c.user_id "
            "                AND s.status='sold' AND s.is_trial=0) "
            "AND (SELECT banned FROM users u WHERE u.user_id=c.user_id)=0",
            (cutoff,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def mark_winback(config_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE configs SET winback_notified=1 WHERE id=?", (config_id,))
        await db.commit()


# ---------- A/B эксперименты ----------

async def set_user_ab(user_id, exp, variant):
    """Фиксирует вариант эксперимента за пользователем (только если ещё не задан)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE users SET ab_exp=?, ab_variant=? "
            "WHERE user_id=? AND (ab_exp IS NULL OR ab_exp='')",
            (exp, variant, user_id),
        )
        await db.commit()


async def ab_report(exp) -> list[dict]:
    """По вариантам активного эксперимента: пользователей, взяли триал, оплатили, конверсия."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT u.ab_variant variant, COUNT(*) users, "
            "SUM(CASE WHEN u.trial_used=1 THEN 1 ELSE 0 END) trials, "
            "SUM(CASE WHEN EXISTS(SELECT 1 FROM orders o "
            "      WHERE o.user_id=u.user_id AND o.status='paid') THEN 1 ELSE 0 END) paid "
            "FROM users u WHERE u.ab_exp=? AND u.ab_variant IS NOT NULL "
            "GROUP BY u.ab_variant ORDER BY u.ab_variant",
            (exp,),
        )
        return [dict(r) for r in await cur.fetchall()]


# ---------- заморозка подписки ----------

async def can_freeze(config_id, cooldown_days) -> tuple[bool, str | None]:
    """Можно ли заморозить (с учётом кулдауна). Возвращает (можно, дата_след_заморозки)."""
    if cooldown_days <= 0:
        return True, None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT frozen_at FROM configs WHERE id=?", (config_id,))
        row = await cur.fetchone()
        if not row or not row["frozen_at"]:
            return True, None
        try:
            last = datetime.fromisoformat(row["frozen_at"])
        except (ValueError, TypeError):
            return True, None
        nxt = last + timedelta(days=cooldown_days)
        if now() >= nxt:
            return True, None
        return False, iso(nxt)


async def mark_frozen(config_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE configs SET frozen_at=? WHERE id=?", (iso(now()), config_id))
        await db.commit()


async def mark_lowbal_notified(config_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE configs SET lowbal_notified=1 WHERE id=?", (config_id,))
        await db.commit()


async def lowbal_autopay_candidates(before_days) -> list[dict]:
    """Подписки на автопродлении, которые скоро спишутся, но ещё не предупреждены о нехватке."""
    n = now()
    upper = iso(n + timedelta(days=before_days))
    lower = iso(n)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT c.* FROM configs c JOIN users u ON u.user_id = c.user_id "
            "WHERE c.status='sold' AND c.is_trial=0 AND u.autopay=1 AND u.banned=0 "
            "AND c.lowbal_notified=0 AND c.renew_notified=0 "
            "AND c.expires_at IS NOT NULL AND c.expires_at > ? AND c.expires_at <= ?",
            (lower, upper),
        )
        return [dict(r) for r in await cur.fetchall()]


async def apply_bonus(user_id) -> tuple[int, str | None]:
    u = await get_user(user_id)
    if not u or u["bonus_days"] <= 0:
        return 0, None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM configs WHERE user_id=? AND status='sold' "
            "ORDER BY expires_at DESC LIMIT 1", (user_id,),
        )
        cfg = await cur.fetchone()
        if not cfg:
            return 0, None
        days = u["bonus_days"]
        base = now()
        try:
            exp = datetime.fromisoformat(cfg["expires_at"])
            if exp > base:
                base = exp
        except (ValueError, TypeError):
            pass
        new_exp = base + timedelta(days=days)
        await db.execute("UPDATE configs SET expires_at=? WHERE id=?", (iso(new_exp), cfg["id"]))
        await db.execute("UPDATE users SET bonus_days=0 WHERE user_id=?", (user_id,))
        await db.commit()
        return days, cfg["region"]


async def all_user_ids():
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT user_id FROM users")
        return [r[0] for r in await cur.fetchall()]


# ---------- капча / верификация ----------
async def is_verified(user_id) -> bool:
    u = await get_user(user_id)
    return bool(u and u.get("verified"))


async def set_verified(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET verified=1 WHERE user_id=?", (user_id,))
        await db.commit()


# ---------- бонус за подписку на канал ----------
async def extend_active_sub(user_id, days) -> tuple[int, str | None, str | None]:
    """Продлевает последнюю активную подписку (sold) на days дней.
    Возвращает (days, region, new_expiry_iso) либо (0, None, None), если активной нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM configs WHERE user_id=? AND status='sold' "
            "ORDER BY expires_at DESC LIMIT 1", (user_id,))
        cfg = await cur.fetchone()
        if not cfg:
            return 0, None, None
        base = now()
        try:
            exp = datetime.fromisoformat(cfg["expires_at"])
            if exp > base:
                base = exp
        except (ValueError, TypeError):
            pass
        new_exp = base + timedelta(days=days)
        await db.execute("UPDATE configs SET expires_at=? WHERE id=?", (iso(new_exp), cfg["id"]))
        await db.commit()
        return days, cfg["region"], iso(new_exp)


async def channel_bonus_claimed(user_id) -> bool:
    u = await get_user(user_id)
    return bool(u and u.get("channel_bonus_claimed"))


async def set_channel_bonus_claimed(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET channel_bonus_claimed=1 WHERE user_id=?", (user_id,))
        await db.commit()


# ---------- напоминание после триала ----------
async def trial_reminder_candidates(after_days: int) -> list[dict]:
    """Кто активировал триал, но так и не купил, и прошло >= after_days дней."""
    cut = iso(now() - timedelta(days=after_days))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT user_id, lang FROM users u "
            "WHERE u.trial_used=1 AND u.banned=0 AND u.trial_reminded=0 "
            "AND u.created_at <= ? "
            "AND NOT EXISTS (SELECT 1 FROM configs c WHERE c.user_id=u.user_id "
            "                AND c.is_trial=0 AND c.sold_at IS NOT NULL)",
            (cut,))
        return [dict(r) for r in await cur.fetchall()]


async def mark_trial_reminded(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET trial_reminded=1 WHERE user_id=?", (user_id,))
        await db.commit()


# ---------- дайджест ----------
async def new_users_since(cut_iso: str) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE created_at >= ?", (cut_iso,))
        return (await cur.fetchone())[0]


# ---------- конфиги ----------

async def add_config(region, config_text, is_premium, is_trial, source=None) -> tuple[int, bool]:
    """Добавляет конфиг. Невалидный WireGuard кладётся со статусом 'broken' (не продаётся).
    Возвращает (id, is_valid)."""
    from utils import is_valid_wg
    valid = is_valid_wg(config_text)
    status = "free" if valid else "broken"
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO configs(region, config_text, is_premium, is_trial, status, source, created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (region, config_text, 1 if is_premium else 0, 1 if is_trial else 0, status, source, iso(now())),
        )
        await db.execute(
            "INSERT INTO region_state(region, low_notified, empty_notified) VALUES(?,0,0) "
            "ON CONFLICT(region) DO UPDATE SET low_notified=0, empty_notified=0",
            (region,),
        )
        await db.commit()
        return cur.lastrowid, valid


async def regions_overview(min_free):
    """Платные регионы (без триал-конфигов). (region, is_premium, free)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT region, MAX(is_premium) prem, "
            "SUM(CASE WHEN status='free' AND is_trial=0 THEN 1 ELSE 0 END) free "
            "FROM configs WHERE is_trial=0 GROUP BY region HAVING free >= ? ORDER BY prem, region",
            (min_free,),
        )
        return [(r[0], r[1], r[2]) for r in await cur.fetchall()]


async def free_counts_by_region() -> dict:
    """{region: число свободных платных конфигов}."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT region, SUM(CASE WHEN status='free' AND is_trial=0 THEN 1 ELSE 0 END) free "
            "FROM configs WHERE is_trial=0 GROUP BY region"
        )
        return {r[0]: (r[1] or 0) for r in await cur.fetchall()}


async def regions_for_purchase():
    """Каталог регионов (всегда показываются) + число свободных конфигов.
    Регионы без конфигов остаются в списке — при выборе предложат предзаказ.
    Возвращает [(region, is_premium, free), ...] в порядке каталога."""
    import store
    free = await free_counts_by_region()
    catalog = list(store.CATALOG)
    seen = {r for r, _ in catalog}
    result = [(region, 1 if prem else 0, free.get(region, 0)) for region, prem in catalog]
    # регионы, которых нет в каталоге, но есть конфиги — добавим в конец
    for region, cnt in free.items():
        if region not in seen:
            result.append((region, 0, cnt))
    return result


async def load_catalog() -> list[tuple[str, bool]]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT region, is_premium FROM region_catalog ORDER BY position, region")
        return [(r[0], bool(r[1])) for r in await cur.fetchall()]


async def catalog_with_stock() -> list[dict]:
    """Для админки: регион, premium, свободно, всего конфигов."""
    free = await free_counts_by_region()
    import store
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT region, COUNT(*) total FROM configs WHERE is_trial=0 GROUP BY region")
        totals = {r[0]: r[1] for r in await cur.fetchall()}
    out = []
    for region, prem in store.CATALOG:
        out.append({"region": region, "is_premium": prem,
                    "free": free.get(region, 0), "total": totals.get(region, 0)})
    return out


async def catalog_add(region: str, is_premium: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COALESCE(MAX(position),-1)+1 FROM region_catalog")
        pos = (await cur.fetchone())[0]
        await db.execute(
            "INSERT INTO region_catalog(region, is_premium, position) VALUES(?,?,?) "
            "ON CONFLICT(region) DO UPDATE SET is_premium=excluded.is_premium",
            (region, 1 if is_premium else 0, pos))
        await db.commit()


async def catalog_set_premium(region: str, is_premium: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE region_catalog SET is_premium=? WHERE region=?",
                         (1 if is_premium else 0, region))
        # синхронизируем флаг и у существующих конфигов региона
        await db.execute("UPDATE configs SET is_premium=? WHERE region=? AND is_trial=0",
                         (1 if is_premium else 0, region))
        await db.commit()


async def catalog_remove(region: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM region_catalog WHERE region=?", (region,))
        await db.commit()


async def catalog_rename(old: str, new: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE region_catalog SET region=? WHERE region=?", (new, old))
        await db.execute("UPDATE configs SET region=? WHERE region=?", (new, old))
        await db.execute("UPDATE region_state SET region=? WHERE region=?", (new, old))
        await db.commit()


# ---------- редактируемые цены ----------

async def load_prices() -> list[tuple]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT plan, devices, period, rub FROM settings_prices")
        return [(r[0], r[1], r[2], r[3]) for r in await cur.fetchall()]


async def save_price(plan: str, devices: int, period: str, rub: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings_prices(plan, devices, period, rub) VALUES(?,?,?,?) "
            "ON CONFLICT(plan, devices, period) DO UPDATE SET rub=excluded.rub",
            (plan, devices, period, rub))
        await db.commit()


async def regions_for_purchase_legacy():
    """Старое поведение (только регионы с конфигами) — оставлено на всякий случай."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT region, MAX(is_premium) prem, "
            "SUM(CASE WHEN status='free' AND is_trial=0 THEN 1 ELSE 0 END) free "
            "FROM configs WHERE is_trial=0 GROUP BY region ORDER BY prem, region"
        )
        return [(r[0], r[1], r[2]) for r in await cur.fetchall()]


async def trial_regions():
    """Регионы пробного периода — ТОЛЬКО триал-пул. Платные серверы не трогаются."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT region, 0, SUM(CASE WHEN status='free' THEN 1 ELSE 0 END) free "
            "FROM configs WHERE is_trial=1 GROUP BY region HAVING free >= 1 ORDER BY region"
        )
        return [(r[0], r[1], r[2]) for r in await cur.fetchall()]


async def extend_active(user_id, days) -> tuple[bool, str | None]:
    """Добавляет дни к самой свежей активной подписке пользователя."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM configs WHERE user_id=? AND status='sold' "
            "ORDER BY expires_at DESC LIMIT 1", (user_id,),
        )
        cfg = await cur.fetchone()
        if not cfg:
            return False, None
        base = now()
        try:
            exp = datetime.fromisoformat(cfg["expires_at"])
            if exp > base:
                base = exp
        except (ValueError, TypeError):
            pass
        new_exp = base + timedelta(days=days)
        await db.execute("UPDATE configs SET expires_at=? WHERE id=?", (iso(new_exp), cfg["id"]))
        await db.commit()
        return True, cfg["region"]


async def reserve_purchase(region, n, user_id) -> list[dict] | None:
    """Бронь платных (не триал) конфигов."""
    return await _reserve(region, n, user_id, "AND is_trial=0", "id")


async def reserve_trial(region, user_id) -> list[dict] | None:
    """Бронь 1 конфига для триала — строго из триал-пула."""
    return await _reserve(region, 1, user_id, "AND is_trial=1", "id")


async def _reserve(region, n, user_id, extra_where, order_by):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute(
            f"SELECT * FROM configs WHERE region=? AND status='free' {extra_where} "
            f"ORDER BY {order_by} LIMIT ?",
            (region, n),
        )
        rows = [dict(r) for r in await cur.fetchall()]
        if len(rows) < n:
            await db.commit()
            return None
        for row in rows:
            await db.execute(
                "UPDATE configs SET status='reserved', user_id=?, reserved_at=? WHERE id=?",
                (user_id, iso(now()), row["id"]),
            )
        await db.commit()
        return rows


async def get_config(config_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM configs WHERE id=?", (config_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def mark_sold(config_id, user_id, plan, period) -> datetime:
    sold = now()
    expires = sold + timedelta(days=PERIOD_DAYS[period])
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE configs SET status='sold', user_id=?, plan=?, period=?, "
            "sold_at=?, expires_at=?, reserved_at=NULL WHERE id=?",
            (user_id, plan, period, iso(sold), iso(expires), config_id),
        )
        await db.commit()
    return expires


async def expire_configs():
    cutoff = iso(now())
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, user_id, region FROM configs "
            "WHERE status='sold' AND expires_at IS NOT NULL AND expires_at < ?", (cutoff,),
        )
        rows = [dict(r) for r in await cur.fetchall()]
        for cfg in rows:
            await db.execute("UPDATE configs SET status='expired' WHERE id=?", (cfg["id"],))
        await db.commit()
        return rows


async def user_configs(user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM configs WHERE user_id=? AND status IN ('sold','expired') ORDER BY id",
            (user_id,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def delete_free_configs(region):
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "DELETE FROM configs WHERE region=? AND status IN ('free','broken')", (region,))
        await db.commit()
        return cur.rowcount


# ---------- запасы ----------

async def scan_stock_alerts() -> list[tuple]:
    alerts = []
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT region, SUM(CASE WHEN status='free' AND is_trial=0 THEN 1 ELSE 0 END) free "
            "FROM configs WHERE is_trial=0 GROUP BY region"
        )
        regions = [(r["region"], r["free"]) for r in await cur.fetchall()]
        for region, free in regions:
            cur = await db.execute(
                "SELECT low_notified, empty_notified FROM region_state WHERE region=?", (region,)
            )
            st = await cur.fetchone()
            low_n = st["low_notified"] if st else 0
            emp_n = st["empty_notified"] if st else 0
            if free == 0:
                if not emp_n:
                    alerts.append((region, "empty", free))
                    await db.execute(
                        "INSERT INTO region_state(region, low_notified, empty_notified) VALUES(?,1,1) "
                        "ON CONFLICT(region) DO UPDATE SET low_notified=1, empty_notified=1", (region,))
            elif free <= LOW_STOCK_THRESHOLD:
                if not low_n:
                    alerts.append((region, "low", free))
                    await db.execute(
                        "INSERT INTO region_state(region, low_notified, empty_notified) VALUES(?,1,0) "
                        "ON CONFLICT(region) DO UPDATE SET low_notified=1, empty_notified=0", (region,))
            else:
                if low_n or emp_n:
                    await db.execute(
                        "INSERT INTO region_state(region, low_notified, empty_notified) VALUES(?,0,0) "
                        "ON CONFLICT(region) DO UPDATE SET low_notified=0, empty_notified=0", (region,))
        await db.commit()
    return alerts


# ---------- заказы ----------

async def create_order(user_id, plan, devices, period, region, config_ids, full_rub, discount, rub) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO orders(user_id, plan, devices, period, region, config_ids, "
            "full_rub, discount, rub, status, created_at) VALUES(?,?,?,?,?,?,?,?,?, 'pending', ?)",
            (user_id, plan, devices, period, region, ",".join(map(str, config_ids)),
             full_rub, discount, rub, iso(now())),
        )
        await db.commit()
        return cur.lastrowid


async def get_order(order_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM orders WHERE id=?", (order_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_order_status(order_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE orders SET status=? WHERE id=?", (status, order_id))
        await db.commit()


async def release_stale_orders():
    cutoff = iso(now() - timedelta(minutes=ORDER_TTL_MIN))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM orders WHERE status='pending' AND created_at < ?", (cutoff,))
        for o in [dict(r) for r in await cur.fetchall()]:
            ids = [int(x) for x in o["config_ids"].split(",") if x]
            if ids:
                qs = ",".join("?" * len(ids))
                await db.execute(
                    f"UPDATE configs SET status='free', user_id=NULL, reserved_at=NULL "
                    f"WHERE id IN ({qs}) AND status='reserved'", ids)
            await db.execute("UPDATE orders SET status='cancelled' WHERE id=?", (o["id"],))
        await db.commit()


# ---------- платежи / статистика ----------

async def record_payment(user_id, order_id, amount, currency, charge_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO payments(user_id, order_id, amount, currency, charge_id, created_at) "
            "VALUES(?,?,?,?,?,?)",
            (user_id, order_id, amount, currency, charge_id, iso(now())),
        )
        await db.commit()


# ============ ПОДПИСКИ СО СЛОТАМИ (многоустройственные тарифы) ============

async def create_subscription(user_id, plan, devices, period) -> int:
    n = now()
    exp = iso(n + timedelta(days=PERIOD_DAYS[period]))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO subscriptions(user_id, plan, devices, period, expires_at, status, created_at) "
            "VALUES(?,?,?,?,?, 'active', ?)",
            (user_id, plan, devices, period, exp, iso(n)))
        await db.commit()
        return cur.lastrowid


async def get_subscription(sub_id) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM subscriptions WHERE id=?", (sub_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def subscription_configs(sub_id) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM configs WHERE sub_id=? AND status IN ('sold','expired') ORDER BY id", (sub_id,))
        return [dict(r) for r in await cur.fetchall()]


async def user_subscriptions(user_id) -> list[dict]:
    """Активные подписки пользователя с числом активированных/свободных слотов."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM subscriptions WHERE user_id=? AND status='active' ORDER BY id DESC", (user_id,))
        subs = [dict(r) for r in await cur.fetchall()]
        for s in subs:
            c = await (await db.execute(
                "SELECT COUNT(*) c FROM configs WHERE sub_id=? AND status IN ('sold','expired')",
                (s["id"],))).fetchone()
            s["activated"] = c["c"]
            s["free_slots"] = max(s["devices"] - s["activated"], 0)
        return subs


async def activate_slot(sub_id, region, user_id) -> dict | None:
    """Бронирует один свободный конфиг в регионе под слот подписки. None — нет места/стока."""
    sub = await get_subscription(sub_id)
    if not sub or sub["status"] != "active" or sub["user_id"] != user_id:
        return None
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        used = await (await db.execute(
            "SELECT COUNT(*) c FROM configs WHERE sub_id=? AND status IN ('sold','expired')",
            (sub_id,))).fetchone()
        if used["c"] >= sub["devices"]:
            return None  # свободных слотов нет
        row = await (await db.execute(
            "SELECT id FROM configs WHERE region=? AND status='free' AND is_trial=0 "
            "ORDER BY id LIMIT 1", (region,))).fetchone()
        if not row:
            return None  # нет свободного конфига в регионе
        cid = row["id"]
        await db.execute(
            "UPDATE configs SET status='sold', user_id=?, plan=?, period=?, sub_id=?, "
            "sold_at=?, expires_at=? WHERE id=? AND status='free'",
            (user_id, sub["plan"], sub["period"], sub_id, iso(now()), sub["expires_at"], cid))
        await db.commit()
        cur = await db.execute("SELECT * FROM configs WHERE id=?", (cid,))
        return dict(await cur.fetchone())


async def active_plan(user_id) -> str | None:
    """Текущий тариф пользователя: по активной подписке, иначе по активному конфигу."""
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (await db.execute(
            "SELECT plan FROM subscriptions WHERE user_id=? AND status='active' "
            "ORDER BY id DESC LIMIT 1", (user_id,))).fetchone()
        if row and row[0]:
            return row[0]
        row = await (await db.execute(
            "SELECT plan FROM configs WHERE user_id=? AND status='sold' AND plan IS NOT NULL "
            "ORDER BY id DESC LIMIT 1", (user_id,))).fetchone()
        return row[0] if row and row[0] else None


# ============ ЗАПРОСЫ СМЕНЫ РЕГИОНА (через одобрение админа) ============

async def create_region_change(user_id, config_id, from_region) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO region_change_requests(user_id, config_id, from_region, status, created_at) "
            "VALUES(?,?,?, 'pending', ?)", (user_id, config_id, from_region, iso(now())))
        await db.commit()
        return cur.lastrowid


async def get_region_change(req_id) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM region_change_requests WHERE id=?", (req_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_region_change_status(req_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE region_change_requests SET status=? WHERE id=?", (status, req_id))
        await db.commit()


async def digest_stats() -> dict:
    """Сводка за последние 24 часа для ежедневного дайджеста админам."""
    cut = iso(now() - timedelta(hours=24))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        new_users = (await (await db.execute(
            "SELECT COUNT(*) c FROM users WHERE created_at>=?", (cut,))).fetchone())["c"]
        row = await (await db.execute(
            "SELECT COUNT(*) cnt, COALESCE(SUM(amount),0) rub FROM payments WHERE created_at>=?",
            (cut,))).fetchone()
        sales_cnt, revenue = row["cnt"], row["rub"]
        trials = (await (await db.execute(
            "SELECT COUNT(*) c FROM configs WHERE is_trial=1 AND sold_at>=?", (cut,))).fetchone())["c"]
        pending_po = (await (await db.execute(
            "SELECT COUNT(*) c FROM orders WHERE status='preorder'")).fetchone())["c"]
        free_left = (await (await db.execute(
            "SELECT COUNT(*) c FROM configs WHERE status='free' AND is_trial=0")).fetchone())["c"]
        low = await (await db.execute(
            "SELECT COUNT(*) c FROM (SELECT region FROM configs WHERE is_trial=0 "
            "GROUP BY region HAVING SUM(status='free')<=3)")).fetchone()
        return {"new_users": new_users, "sales_cnt": sales_cnt, "revenue": revenue,
                "trials": trials, "pending_po": pending_po, "free_left": free_left,
                "low_stock": low["c"]}


async def stats():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT region, MAX(is_premium) prem, MAX(is_trial) tr, SUM(status='free') free, "
            "SUM(status='reserved') reserved, SUM(status='sold') sold, "
            "SUM(status='expired') expired, COUNT(*) total "
            "FROM configs GROUP BY region ORDER BY prem, region"
        )
        per_region = [dict(r) for r in await cur.fetchall()]
        cur = await db.execute("SELECT COUNT(*) c FROM users")
        users_count = (await cur.fetchone())["c"]
        cur = await db.execute(
            "SELECT currency, COALESCE(SUM(amount),0) total, COUNT(*) cnt FROM payments GROUP BY currency")
        revenue = [dict(r) for r in await cur.fetchall()]
        cur = await db.execute("SELECT COUNT(*) c FROM orders WHERE status='paid'")
        orders_paid = (await cur.fetchone())["c"]
        return per_region, users_count, revenue, orders_paid


# ---------- промокоды ----------

async def create_promo(code, kind, percent=0, amount_rub=0, max_uses=0):
    """kind: 'discount' (percent) или 'balance' (amount_rub)."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO promo_codes(code, kind, percent, amount_rub, max_uses, used, active, created_at) "
            "VALUES(?,?,?,?,?,0,1,?) "
            "ON CONFLICT(code) DO UPDATE SET kind=?, percent=?, amount_rub=?, max_uses=?, active=1",
            (code.upper(), kind, percent, amount_rub, max_uses, iso(now()),
             kind, percent, amount_rub, max_uses),
        )
        await db.commit()


async def get_promo(code) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM promo_codes WHERE code=?", (code.upper(),))
        row = await cur.fetchone()
        if not row:
            return None
        p = dict(row)
        if not p["active"]:
            return None
        if p["max_uses"] and p["used"] >= p["max_uses"]:
            return None
        return p


async def use_promo(code):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE promo_codes SET used=used+1 WHERE code=?", (code.upper(),))
        await db.commit()


async def list_promos() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM promo_codes ORDER BY created_at DESC")
        return [dict(r) for r in await cur.fetchall()]


async def toggle_promo(code):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE promo_codes SET active=1-active WHERE code=?", (code.upper(),))
        await db.commit()


async def delete_promo(code):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM promo_codes WHERE code=?", (code.upper(),))
        await db.commit()


# ---------- напоминания о продлении ----------

async def expiring_soon(days) -> list[dict]:
    """Активные платные подписки, истекающие в ближайшие N дней, без отправленного напоминания."""
    n = now()
    upper = iso(n + timedelta(days=days))
    lower = iso(n)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT c.* FROM configs c JOIN users u ON u.user_id = c.user_id "
            "WHERE c.status='sold' AND c.is_trial=0 AND c.renew_notified=0 AND u.autopay=0 "
            "AND c.expires_at IS NOT NULL AND c.expires_at > ? AND c.expires_at <= ?",
            (lower, upper),
        )
        return [dict(r) for r in await cur.fetchall()]


async def mark_renew_notified(config_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE configs SET renew_notified=1 WHERE id=?", (config_id,))
        await db.commit()


# ---------- расширенная аналитика ----------

async def stats_extended() -> dict:
    n = now()
    day = iso(n - timedelta(days=1))
    week = iso(n - timedelta(days=7))
    month = iso(n - timedelta(days=30))

    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row

        async def rev(cut=None):
            base = "SELECT COALESCE(SUM(amount),0) s, COUNT(*) c FROM payments WHERE currency != 'XTR'"
            if cut:
                cur = await db.execute(base + " AND created_at >= ?", (cut,))
            else:
                cur = await db.execute(base)
            r = await cur.fetchone()
            return r["s"], r["c"]

        # выручка по валютам (т.к. суммы в разных валютах: RUB / XTR)
        cur = await db.execute(
            "SELECT currency, COALESCE(SUM(amount),0) s, COUNT(*) c FROM payments GROUP BY currency")
        by_cur = [dict(r) for r in await cur.fetchall()]

        d_s, d_c = await rev(day)
        w_s, w_c = await rev(week)
        m_s, m_c = await rev(month)
        a_s, a_c = await rev()

        cur = await db.execute("SELECT COUNT(*) c FROM users")
        users_count = (await cur.fetchone())["c"]
        cur = await db.execute("SELECT COUNT(*) c FROM configs WHERE status='sold' AND is_trial=0")
        active_subs = (await cur.fetchone())["c"]
        cur = await db.execute("SELECT COUNT(*) c FROM configs WHERE status='free' AND is_trial=0")
        free_paid = (await cur.fetchone())["c"]
        cur = await db.execute("SELECT COUNT(*) c FROM configs WHERE status='free' AND is_trial=1")
        free_trial = (await cur.fetchone())["c"]

        cur = await db.execute("SELECT COALESCE(SUM(balance_rub),0) s FROM users")
        total_balance = (await cur.fetchone())["s"]
        cur = await db.execute("SELECT COUNT(*) c FROM preorders WHERE status='waiting'")
        pending_preorders = (await cur.fetchone())["c"]

        return {
            "day": (d_s, d_c), "week": (w_s, w_c), "month": (m_s, m_c), "all": (a_s, a_c),
            "by_currency": by_cur, "users": users_count, "active_subs": active_subs,
            "free_paid": free_paid, "free_trial": free_trial,
            "total_balance": total_balance, "pending_preorders": pending_preorders,
        }


async def all_regions() -> list[str]:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT DISTINCT region FROM configs ORDER BY region")
        return [r[0] for r in await cur.fetchall()]


async def set_order_promo(order_id, code):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE orders SET promo=? WHERE id=?", (code.upper(), order_id))
        await db.commit()


# ---------- баланс ----------

async def get_balance(user_id) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT balance_rub FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return row[0] if row and row[0] else 0


async def add_balance(user_id, rub):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET balance_rub = balance_rub + ? WHERE user_id=?", (rub, user_id))
        await db.commit()


async def deduct_balance(user_id, rub) -> bool:
    """Списывает rub, если хватает. True — успех."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT balance_rub FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        bal = row[0] if row and row[0] else 0
        if bal < rub:
            return False
        await db.execute("UPDATE users SET balance_rub = balance_rub - ? WHERE user_id=?", (rub, user_id))
        await db.commit()
        return True


# ---------- пополнения ----------

async def create_topup(user_id, amount_rub, method) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO topups(user_id, amount_rub, method, status, created_at) "
            "VALUES(?,?,?, 'pending', ?)",
            (user_id, amount_rub, method, iso(now())),
        )
        await db.commit()
        return cur.lastrowid


async def get_topup(topup_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM topups WHERE id=?", (topup_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def set_topup_paid(topup_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE topups SET status='paid' WHERE id=?", (topup_id,))
        await db.commit()


async def set_topup_ref(topup_id, ref):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE topups SET invoice_ref=? WHERE id=?", (str(ref), topup_id))
        await db.commit()


# ---------- предзаказы (когда сервера нет в наличии) ----------

async def create_preorder(user_id, plan, devices, period, region, full_rub, discount, rub, promo, lang) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO preorders(user_id, plan, devices, period, region, full_rub, discount, rub, "
            "promo, status, lang, created_at) VALUES(?,?,?,?,?,?,?,?,?, 'waiting', ?, ?)",
            (user_id, plan, devices, period, region, full_rub, discount, rub, promo, lang, iso(now())),
        )
        await db.commit()
        return cur.lastrowid


async def get_preorder(preorder_id):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM preorders WHERE id=?", (preorder_id,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def waiting_preorders() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM preorders WHERE status='waiting' ORDER BY created_at")
        return [dict(r) for r in await cur.fetchall()]


async def set_preorder_status(preorder_id, status):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE preorders SET status=? WHERE id=?", (status, preorder_id))
        await db.commit()


async def preorders_to_refund(hours) -> list[dict]:
    cutoff = iso(now() - timedelta(hours=hours))
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM preorders WHERE status='waiting' AND created_at < ?", (cutoff,))
        return [dict(r) for r in await cur.fetchall()]


async def free_configs(config_ids):
    """Возвращает зарезервированные конфиги обратно в свободные."""
    ids = [int(x) for x in config_ids if x]
    if not ids:
        return
    qs = ",".join("?" * len(ids))
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE configs SET status='free', user_id=NULL, reserved_at=NULL "
            f"WHERE id IN ({qs}) AND status='reserved'", ids)
        await db.commit()


# ---------- бан / автоплатёж ----------

async def set_banned(user_id, banned: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET banned=? WHERE user_id=?", (1 if banned else 0, user_id))
        await db.commit()


async def is_banned(user_id) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT banned FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return bool(row and row[0])


async def set_autopay(user_id, on: bool):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("UPDATE users SET autopay=? WHERE user_id=?", (1 if on else 0, user_id))
        await db.commit()


async def get_autopay(user_id) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT autopay FROM users WHERE user_id=?", (user_id,))
        row = await cur.fetchone()
        return bool(row and row[0])


# ---------- лояльность ----------

async def total_spent(user_id) -> int:
    """Сумма всех реальных платежей пользователя в ₽ (без Telegram Stars)."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COALESCE(SUM(amount),0) FROM payments WHERE user_id=? AND currency != 'XTR'",
            (user_id,),
        )
        return (await cur.fetchone())[0] or 0


# ---------- промокоды: учёт по пользователю ----------

async def promo_redeemed_by(code, user_id) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT 1 FROM promo_redemptions WHERE code=? AND user_id=?", (code.upper(), user_id))
        return await cur.fetchone() is not None


async def record_promo_redemption(code, user_id):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO promo_redemptions(code, user_id, created_at) VALUES(?,?,?)",
            (code.upper(), user_id, iso(now())),
        )
        await db.commit()


# ---------- подарочные коды ----------

async def create_gift_code(code, amount_rub, created_by=None) -> None:
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO promo_codes(code, kind, percent, amount_rub, max_uses, used, active, "
            "is_gift, created_at) VALUES(?, 'balance', 0, ?, 1, 0, 1, 1, ?)",
            (code.upper(), amount_rub, iso(now())),
        )
        await db.commit()


# ---------- автопродление ----------

async def autorenew_candidates(before_days) -> list[dict]:
    """Активные платные подписки, истекающие в ближайшие N дней, у пользователей с autopay=1."""
    n = now()
    upper = iso(n + timedelta(days=before_days))
    lower = iso(n)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT c.* FROM configs c JOIN users u ON u.user_id = c.user_id "
            "WHERE c.status='sold' AND c.is_trial=0 AND u.autopay=1 AND u.banned=0 AND c.renew_notified=0 "
            "AND c.expires_at IS NOT NULL AND c.expires_at > ? AND c.expires_at <= ?",
            (lower, upper),
        )
        return [dict(r) for r in await cur.fetchall()]


async def extend_config(config_id, days) -> datetime:
    """Продлевает конкретный конфиг на N дней (от текущей даты окончания, если она в будущем)."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT expires_at FROM configs WHERE id=?", (config_id,))
        row = await cur.fetchone()
        base = now()
        if row and row["expires_at"]:
            try:
                exp = datetime.fromisoformat(row["expires_at"])
                if exp > base:
                    base = exp
            except (ValueError, TypeError):
                pass
        new_exp = base + timedelta(days=days)
        await db.execute(
            "UPDATE configs SET expires_at=?, status='sold', renew_notified=0 WHERE id=?",
            (iso(new_exp), config_id),
        )
        await db.commit()
        return new_exp


# ---------- админ: карточка пользователя ----------

async def find_user(query: str) -> dict | None:
    """Поиск пользователя по числовому ID или по @username."""
    query = query.strip().lstrip("@")
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if query.isdigit():
            cur = await db.execute("SELECT * FROM users WHERE user_id=?", (int(query),))
        else:
            cur = await db.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE", (query,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def user_card(user_id) -> dict | None:
    u = await get_user(user_id)
    if not u:
        return None
    spent = await total_spent(user_id)
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT COUNT(*) c FROM users WHERE referred_by=?", (user_id,))
        invited = (await cur.fetchone())["c"]
        cur = await db.execute(
            "SELECT region, status, expires_at FROM configs "
            "WHERE user_id=? AND status IN ('sold','expired') ORDER BY expires_at DESC", (user_id,))
        subs = [dict(r) for r in await cur.fetchall()]
    u["spent"] = spent
    u["invited"] = invited
    u["subs"] = subs
    return u


async def last_paid_order(user_id) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT * FROM orders WHERE user_id=? AND status='paid' ORDER BY id DESC LIMIT 1",
            (user_id,),
        )
        row = await cur.fetchone()
        return dict(row) if row else None


async def top_referrers(limit=10) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT u.user_id, u.username, u.full_name, u.ref_earned_rub, "
            "(SELECT COUNT(*) FROM users r WHERE r.referred_by = u.user_id) invited "
            "FROM users u WHERE invited > 0 ORDER BY invited DESC, u.ref_earned_rub DESC LIMIT ?",
            (limit,),
        )
        return [dict(r) for r in await cur.fetchall()]


async def count_users() -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        row = await (await db.execute("SELECT COUNT(*) FROM users")).fetchone()
        return row[0]


async def list_users(limit=8, offset=0) -> list[dict]:
    """Страница пользователей (свежие сверху) для просмотра в админке."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT user_id, username, full_name, COALESCE(balance_rub,0) balance_rub "
            "FROM users ORDER BY rowid DESC LIMIT ? OFFSET ?", (limit, offset))
        return [dict(r) for r in await cur.fetchall()]


async def disable_premium(user_id, premium_plans) -> int:
    """Отключает премиум: гасит активные премиум-подписки и премиум-конфиги пользователя."""
    premium_plans = list(premium_plans or [])
    if not premium_plans:
        return 0
    qmarks = ",".join("?" * len(premium_plans))
    async with aiosqlite.connect(DB_PATH) as db:
        cur1 = await db.execute(
            f"UPDATE subscriptions SET status='expired' WHERE user_id=? AND status='active' "
            f"AND plan IN ({qmarks})", (user_id, *premium_plans))
        cur2 = await db.execute(
            f"UPDATE configs SET status='expired' WHERE user_id=? AND status='sold' "
            f"AND plan IN ({qmarks})", (user_id, *premium_plans))
        await db.commit()
        return (cur1.rowcount or 0) + (cur2.rowcount or 0)


async def export_users() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT user_id, username, full_name, lang, balance_rub, bonus_days, "
            "ref_balance_rub, ref_earned_rub, referred_by, trial_used, banned, autopay, created_at "
            "FROM users ORDER BY created_at")
        return [dict(r) for r in await cur.fetchall()]


async def export_payments() -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            "SELECT id, user_id, order_id, amount, currency, charge_id, created_at "
            "FROM payments ORDER BY created_at")
        return [dict(r) for r in await cur.fetchall()]


# ---------- метрики / аналитика ----------

async def active_subs_breakdown() -> list[tuple]:
    """Активные платные подписки по (plan, period). Для расчёта MRR."""
    cutoff = iso(now())
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT COALESCE(plan,'standard') plan, COALESCE(period,'month') period, COUNT(*) c "
            "FROM configs WHERE status='sold' AND is_trial=0 "
            "AND expires_at IS NOT NULL AND expires_at > ? GROUP BY plan, period",
            (cutoff,),
        )
        return [(r[0], r[1], r[2]) for r in await cur.fetchall()]


async def trial_conversion() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute("SELECT COUNT(*) FROM users WHERE trial_used=1")
        trials = (await cur.fetchone())[0]
        cur = await db.execute(
            "SELECT COUNT(*) FROM users u WHERE u.trial_used=1 AND EXISTS("
            "SELECT 1 FROM configs c WHERE c.user_id=u.user_id AND c.is_trial=0 "
            "AND c.status IN ('sold','expired'))")
        converted = (await cur.fetchone())[0]
    rate = (converted / trials * 100) if trials else 0.0
    return {"trials": trials, "converted": converted, "rate": rate}


async def churn_30d() -> dict:
    n = now()
    lower = iso(n - timedelta(days=30))
    cutoff = iso(n)
    async with aiosqlite.connect(DB_PATH) as db:
        # подписки, истёкшие за 30 дней (по пользователям)
        cur = await db.execute(
            "SELECT DISTINCT user_id FROM configs WHERE is_trial=0 AND status='expired' "
            "AND expires_at IS NOT NULL AND expires_at >= ?", (lower,))
        expired_users = {r[0] for r in await cur.fetchall()}
        # из них — у кого СЕЙЧАС есть активная подписка (значит, продлили / не ушли)
        cur = await db.execute(
            "SELECT DISTINCT user_id FROM configs WHERE is_trial=0 AND status='sold' "
            "AND expires_at IS NOT NULL AND expires_at > ?", (cutoff,))
        active_users = {r[0] for r in await cur.fetchall()}
    churned = len(expired_users - active_users)
    base = len(expired_users)
    rate = (churned / base * 100) if base else 0.0
    return {"expired": base, "churned": churned, "rate": rate}


async def revenue_by_day(days=14) -> list[tuple]:
    """[(YYYY-MM-DD, сумма_₽), ...] за последние `days` дней (без Stars)."""
    lower = iso(now() - timedelta(days=days))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT substr(created_at,1,10) d, COALESCE(SUM(amount),0) s "
            "FROM payments WHERE currency != 'XTR' AND created_at >= ? GROUP BY d ORDER BY d",
            (lower,))
        return [(r[0], r[1]) for r in await cur.fetchall()]


async def new_users_by_day(days=14) -> list[tuple]:
    lower = iso(now() - timedelta(days=days))
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT substr(created_at,1,10) d, COUNT(*) c FROM users WHERE created_at >= ? "
            "GROUP BY d ORDER BY d", (lower,))
        return [(r[0], r[1]) for r in await cur.fetchall()]


# ---------- склад / заявки на закупку ----------

# статусы restock: new → awaiting_payment → paid → done | canceled
RESTOCK_ACTIVE = ("new", "awaiting_payment", "paid")


async def add_configs_bulk(region, is_premium, is_trial, texts: list[str], source=None) -> tuple[int, int]:
    """Массовое добавление. Возвращает (добавлено_валидных, пропущено_битых).
    Невалидные не кладутся в продажу вовсе."""
    from utils import is_valid_wg
    added = skipped = 0
    async with aiosqlite.connect(DB_PATH) as db:
        for t in texts:
            t = (t or "").strip()
            if not t:
                continue
            if not is_valid_wg(t):
                skipped += 1
                continue
            await db.execute(
                "INSERT INTO configs(region, config_text, is_premium, is_trial, status, source, created_at) "
                "VALUES(?,?,?,?,'free',?,?)",
                (region, t, 1 if is_premium else 0, 1 if is_trial else 0, source, iso(now())),
            )
            added += 1
        await db.commit()
    return added, skipped


async def validate_free_stock() -> int:
    """Сканирует все свободные конфиги, помечает невалидные как 'broken'. Возвращает число помеченных."""
    from utils import is_valid_wg
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT id, config_text FROM configs WHERE status='free'")
        rows = await cur.fetchall()
        bad = [r["id"] for r in rows if not is_valid_wg(r["config_text"])]
        for cid in bad:
            await db.execute("UPDATE configs SET status='broken' WHERE id=?", (cid,))
        await db.commit()
    return len(bad)


async def broken_counts() -> dict:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT region, COUNT(*) FROM configs WHERE status='broken' GROUP BY region")
        return {r[0]: r[1] for r in await cur.fetchall()}


async def replace_config(old_id, target_region, reason) -> dict | None:
    """Заменяет конфиг клиента на новый из склада target_region, перенося срок действия.
    Возвращает dict нового конфига (+old_source) или None, если свободных нет."""
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        await db.execute("BEGIN IMMEDIATE")
        cur = await db.execute("SELECT * FROM configs WHERE id=?", (old_id,))
        old = await cur.fetchone()
        if not old:
            await db.commit()
            return None
        old = dict(old)
        # берём свободный валидный конфиг нужного региона
        cur = await db.execute(
            "SELECT * FROM configs WHERE region=? AND status='free' AND is_trial=0 ORDER BY id LIMIT 1",
            (target_region,))
        new = await cur.fetchone()
        if not new:
            await db.commit()
            return None
        new = dict(new)
        await db.execute(
            "UPDATE configs SET status='sold', user_id=?, plan=?, period=?, sold_at=?, "
            "expires_at=?, reserved_at=NULL WHERE id=?",
            (old["user_id"], old["plan"], old["period"], iso(now()), old["expires_at"], new["id"]),
        )
        # старый — вывести из оборота
        await db.execute("UPDATE configs SET status='replaced' WHERE id=?", (old_id,))
        await db.execute(
            "INSERT INTO replacements(user_id, old_id, new_id, region, reason, old_source, created_at) "
            "VALUES(?,?,?,?,?,?,?)",
            (old["user_id"], old_id, new["id"], target_region, reason, old.get("source"), iso(now())),
        )
        await db.commit()
        new["expires_at"] = old["expires_at"]
        new["old_source"] = old.get("source")
        new["old_region"] = old["region"]
        new["plan"] = old["plan"]
        return new


async def low_stock_regions(threshold) -> list[dict]:
    """Регионы, которые мы реально держим (есть записи в configs) со свободным остатком < threshold,
    плюс регионы с ожидающими предзаказами. [{region, free, has_preorder}]."""
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "SELECT region, SUM(CASE WHEN status='free' AND is_trial=0 THEN 1 ELSE 0 END) free "
            "FROM configs WHERE is_trial=0 GROUP BY region")
        stock = {r[0]: (r[1] or 0) for r in await cur.fetchall()}
        cur = await db.execute(
            "SELECT region, COUNT(*) FROM preorders WHERE status='waiting' GROUP BY region")
        preo = {r[0]: r[1] for r in await cur.fetchall()}
    out = []
    regions = set(stock) | set(preo)
    for region in regions:
        free = stock.get(region, 0)
        has_pre = region in preo
        if free < threshold or has_pre:
            out.append({"region": region, "free": free, "has_preorder": has_pre})
    return out


async def restock_open_for_region(region) -> bool:
    async with aiosqlite.connect(DB_PATH) as db:
        marks = ",".join("?" * len(RESTOCK_ACTIVE))
        cur = await db.execute(
            f"SELECT 1 FROM restock_orders WHERE region=? AND status IN ({marks}) LIMIT 1",
            (region, *RESTOCK_ACTIVE))
        return await cur.fetchone() is not None


async def create_restock(region, need, urgent=False) -> int:
    async with aiosqlite.connect(DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO restock_orders(region, need, status, urgent, created_at, updated_at) "
            "VALUES(?,?,'new',?,?,?)",
            (region, need, 1 if urgent else 0, iso(now()), iso(now())))
        await db.commit()
        return cur.lastrowid


async def get_restock(rid) -> dict | None:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute("SELECT * FROM restock_orders WHERE id=?", (rid,))
        row = await cur.fetchone()
        return dict(row) if row else None


async def list_restock(active_only=True) -> list[dict]:
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if active_only:
            marks = ",".join("?" * len(RESTOCK_ACTIVE))
            cur = await db.execute(
                f"SELECT * FROM restock_orders WHERE status IN ({marks}) "
                f"ORDER BY urgent DESC, id DESC", RESTOCK_ACTIVE)
        else:
            cur = await db.execute("SELECT * FROM restock_orders ORDER BY id DESC LIMIT 30")
        return [dict(r) for r in await cur.fetchall()]


async def set_restock(rid, **fields):
    if not fields:
        return
    fields["updated_at"] = iso(now())
    cols = ", ".join(f"{k}=?" for k in fields)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(f"UPDATE restock_orders SET {cols} WHERE id=?", (*fields.values(), rid))
        await db.commit()


async def restock_inc_added(rid, n):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE restock_orders SET added=added+?, updated_at=? WHERE id=?",
            (n, iso(now()), rid))
        await db.commit()
