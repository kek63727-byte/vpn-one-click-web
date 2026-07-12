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
