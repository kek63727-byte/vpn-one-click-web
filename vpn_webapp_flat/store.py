"""Изменяемые в рантайме настройки: цены тарифов и каталог регионов.

PLANS в config.py — это метаданные тарифа (название, эмодзи, фичи) + цены ПО УМОЛЧАНИЮ.
Здесь хранятся ОВЕРРАЙДЫ цен и актуальный каталог регионов, которые редактируются
из админки и сохраняются в БД. Все функции чтения — синхронные (работают из клавиатур
и текстов), запись идёт через db и обновляет кэш.
"""

from config import DEFAULT_REGION_CATALOG, PLANS

# {(plan, devices, period): rub} — переопределённые цены
PRICES: dict[tuple, int] = {}

# [(region, is_premium), ...] — актуальный каталог регионов
CATALOG: list[tuple[str, bool]] = list(DEFAULT_REGION_CATALOG)


def get_price(plan: str, devices: int, period: str) -> int:
    if (plan, devices, period) in PRICES:
        return PRICES[(plan, devices, period)]
    return PLANS[plan]["prices"].get((devices, period), 0)


def plan_prices(plan: str) -> dict:
    """Полный набор цен тарифа {(devices, period): rub} с учётом оверрайдов."""
    base = dict(PLANS[plan]["prices"])
    for (pl, dev, per), rub in PRICES.items():
        if pl == plan:
            base[(dev, per)] = rub
    return base


def set_price_cache(plan: str, devices: int, period: str, rub: int):
    PRICES[(plan, devices, period)] = rub


def is_premium_region(region: str) -> bool:
    for r, prem in CATALOG:
        if r == region:
            return prem
    return False


async def load_from_db():
    """Загружает оверрайды цен и каталог регионов из БД (вызывать после init_db)."""
    import db
    rows = await db.load_prices()
    PRICES.clear()
    for plan, dev, per, rub in rows:
        PRICES[(plan, dev, per)] = rub
    catalog = await db.load_catalog()
    if catalog:
        CATALOG.clear()
        CATALOG.extend(catalog)

# ══════════════════════ ОТДЕЛЬНАЯ АКЦИЯ (год со скидкой) ══════════════════════
# Полностью независима от обычных PRICES/PLANS выше. Хранится в своём JSON-файле,
# чтобы не трогать схему БД. Когда акция выключена (enabled=False) —
# get_promo_price всегда возвращает None, и всё работает как раньше.

import json as _json
import os as _os

_PROMO_FILE = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), "promo_config.json")

# ══════ РУЧНАЯ НАСТРОЙКА АКЦИИ — меняй только эти 4 строки ══════
PROMO = {
    "enabled": True,               # True — акция включена, False — выключена
    "plan": "ultimate",            # standard / premium / ultimate
    "period": "year",              # month / 3month / 6month / year
    "prices": {"4": 799},
}
# ══════════════════════════════════════════════════════════════


def get_promo_price(plan: str, devices: int, period: str) -> int | None:
    """Возвращает цену акции для этой комбинации или None, если акция
    неактивна / не относится к этому тарифу-периоду-устройству."""
    if not PROMO.get("enabled"):
        return None
    if plan != PROMO.get("plan") or period != PROMO.get("period"):
        return None
    return PROMO.get("prices", {}).get(str(devices))


def get_promo_public() -> dict:
    """То, что можно безопасно отдать фронту (без авторизации) —
    для рендера баннера актуальными цифрами."""
    return {
        "enabled": bool(PROMO.get("enabled")),
        "plan": PROMO.get("plan"),
        "period": PROMO.get("period"),
        "prices": PROMO.get("prices", {}),
    }


def set_promo(enabled: bool | None = None, plan: str | None = None,
              period: str | None = None, prices: dict | None = None):
    if enabled is not None:
        PROMO["enabled"] = enabled
    if plan is not None:
        PROMO["plan"] = plan
    if period is not None:
        PROMO["period"] = period
    if prices is not None:
        PROMO["prices"] = {str(k): int(v) for k, v in prices.items()}
    _save_promo()


def _save_promo():
    try:
        with open(_PROMO_FILE, "w", encoding="utf-8") as f:
            _json.dump(PROMO, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


def _load_promo():
    try:
        if _os.path.exists(_PROMO_FILE):
            with open(_PROMO_FILE, "r", encoding="utf-8") as f:
                data = _json.load(f)
                PROMO.update(data)
    except Exception:
        pass


# ══ ВРЕМЕННО ОТКЛЮЧЕНО ══
# Раньше эта строка подхватывала сохранённые настройки акции из
# promo_config.json (созданного через админку) и МОГЛА ПЕРЕЗАПИСАТЬ
# значения PROMO выше. Пока акция настраивается вручную прямо в этом
# файле, вызов закомментирован, чтобы файл promo_config.json (если он
# есть на сервере) ничего не перетирал.
# _load_promo()
