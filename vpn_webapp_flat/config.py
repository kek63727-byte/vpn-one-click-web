import os

from dotenv import load_dotenv

load_dotenv()

# ============ ОСНОВНЫЕ НАСТРОЙКИ ============
BOT_TOKEN = os.getenv("BOT_TOKEN", "")
ADMIN_IDS = [
    int(x) for x in os.getenv("ADMIN_IDS", "").replace(" ", "").split(",") if x
]
DB_PATH = os.getenv("DB_PATH", "vpn_bot.db")
ORDER_TTL_MIN = int(os.getenv("ORDER_TTL_MIN", "15"))

BRAND = os.getenv("BRAND", "One Click VPN")
SUPPORT_USERNAME = os.getenv("SUPPORT_USERNAME", "@oneclickvpnsupport")
# Новостной канал (ссылка-приглашение). Показывается в меню и профиле.
NEWS_CHANNEL_URL = os.getenv("NEWS_CHANNEL_URL", "https://t.me/+OAs4i2OJaXJhOTEy")
# Ссылка на «Правила пользования» (например, страница telegra.ph). Пусто = текст без ссылки.
RULES_URL = os.getenv("RULES_URL", "")
# Ссылка на саппорт-чат (если отличается от SUPPORT_USERNAME). Пусто = из @username.
SUPPORT_URL = os.getenv("SUPPORT_URL", "")

WEBAPP_URL = os.getenv("WEBAPP_URL", "")
# ============ БОНУС ЗА ПОПОЛНЕНИЕ ============
# (порог_₽, бонус_%). Берётся максимальный подходящий тариф. Пусто = выключено.
TOPUP_BONUS_TIERS = [(1000, 10), (3000, 15), (5000, 20)]

# ============ БОНУС ЗА ПОДПИСКУ НА КАНАЛ ============
# Дни, которые добавятся к АКТИВНОЙ подписке за подписку на канал (разово).
CHANNEL_BONUS_DAYS = int(os.getenv("CHANNEL_BONUS_DAYS", "3"))
# ID или @username канала для проверки подписки. Бот ДОЛЖЕН быть админом этого канала.
# Пример: -1001234567890 или @oneclickvpn_news. Пусто = функция выключена.
# (Это НЕ ссылка-приглашение t.me/+... — нужен именно @username или числовой ID.)
BONUS_CHANNEL_ID = os.getenv("BONUS_CHANNEL_ID", "")

# ============ КАПЧА (АНТИБОТ) ============
# Простая проверка при первом /start, чтобы не плодились боты ради триалов.
CAPTCHA_ENABLED = os.getenv("CAPTCHA_ENABLED", "true").lower() in ("1", "true", "yes")

# ============ ЕЖЕДНЕВНЫЙ ДАЙДЖЕСТ АДМИНУ ============
# Авто-сводка раз в N часов в личку админам (0 = выключить).
DIGEST_EVERY_HOURS = int(os.getenv("DIGEST_EVERY_HOURS", "24"))

# ============ НАПОМИНАНИЕ ПОСЛЕ ТРИАЛА ============
# Через сколько дней после старта слать оффер тем, кто пробовал триал, но не купил.
TRIAL_REMINDER_AFTER_DAYS = int(os.getenv("TRIAL_REMINDER_AFTER_DAYS", "2"))
TRIAL_REMINDER_PROMO_PERCENT = int(os.getenv("TRIAL_REMINDER_PROMO_PERCENT", "15"))
SWITCH_DISCOUNT_PERCENT = int(os.getenv("SWITCH_DISCOUNT_PERCENT", "15"))
TRIAL_REMINDER_PROMO_DAYS = int(os.getenv("TRIAL_REMINDER_PROMO_DAYS", "3"))

# ============ СТИКЕРЫ ============
# Короткое имя твоего стикерпака — часть ссылки после t.me/addstickers/<ИМЯ>.
# При нажатии кнопок бот шлёт стикер. Пусто = выключено.
STICKER_SET = os.getenv("STICKER_SET", "")

# Какой стикер на какую кнопку. Значение — НОМЕР стикера в паке (1, 2, 3 ...).
# Узнать номера: напиши боту /stickers — он пришлёт все стикеры пака с номерами.
# 0 (или убрать строку) = на эту кнопку стикер не отправляется.
# Анти-спам: не чаще одного стикера в STICKER_COOLDOWN_SEC секунд на чат.
# По умолчанию 0 — стикеры не копятся, т.к. старый автоматически заменяется новым.
STICKER_COOLDOWN_SEC = int(os.getenv("STICKER_COOLDOWN_SEC", "0"))
# Ключи = действия кнопок (и нижнего меню, и инлайн-кнопок):
STICKER_MAP = {
    "buy":     1,   # 🌐 Купить подписку
    "my":      2,   # 📁 Мои подключения
    "profile": 3,   # 👤 Профиль
    "prime":   4,   # 👑 Prime подписка
    "support": 5,   # 💬 Поддержка
    "balance": 6,   # 💰 Баланс
    "ref":     7,   # 👥 Пригласить друга
    "history": 8,   # 🧾 Мои платежи
    "howto":   9,   # 📖 Как подключиться
    "faq":     10,  # ❓ FAQ
    "trial":   11,  # 🎁 Триал
    "about":   12,  # ℹ️ О сервисе
    "rules":   13,  # 📄 Правила
    "menu":    14,  # 🏠 Меню
}

# ============ PRIME-ПОДПИСКА (бандл) ============
# Готовый премиум-набор: 5 устройств на максимальном тарифе одной кнопкой.
PRIME_ENABLED = os.getenv("PRIME_ENABLED", "true").lower() in ("1", "true", "yes")
PRIME_PLAN = os.getenv("PRIME_PLAN", "ultimate")
PRIME_DEVICES = int(os.getenv("PRIME_DEVICES", "5"))
# Цены по периодам. Можно покупать на месяц или на год — каждый со своей ценой.
PRIME_PRICES = {
    "month": int(os.getenv("PRIME_PRICE_MONTH", "890")),
    "year": int(os.getenv("PRIME_PRICE_YEAR", "2490")),
}
# Какой период предлагать по умолчанию / в кнопках, если нужен один период.
PRIME_PERIOD = os.getenv("PRIME_PERIOD", "year")
# Обратная совместимость: если где-то в коде используется старое имя PRIME_PRICE —
# это цена дефолтного периода.
PRIME_PRICE = PRIME_PRICES[PRIME_PERIOD]

# ============ ПРОБНЫЙ ПЕРИОД И РЕФЕРАЛКА ============
TRIAL_DAYS = int(os.getenv("TRIAL_DAYS", "3"))
REF_REWARD_DAYS = int(os.getenv("REF_REWARD_DAYS", "3"))
REF_PERCENT = int(os.getenv("REF_PERCENT", "15"))
# Минимальная сумма реферального баланса для вывода реальными деньгами (через саппорт).
REF_MIN_PAYOUT = int(os.getenv("REF_MIN_PAYOUT", "1000"))
# Разовые бонусы за число приглашённых: (порог_приглашённых, бонус_₽_на_реф-баланс).
REF_MILESTONES = [
    (5, 100),
    (10, 250),
    (25, 750),
    (50, 2000),
]

# ============ УВЕДОМЛЕНИЯ О ЗАПАСАХ ============
LOW_STOCK_THRESHOLD = int(os.getenv("LOW_STOCK_THRESHOLD", "3"))

# ============ НАПОМИНАНИЯ И ЛОГ ПРОДАЖ ============
REMIND_BEFORE_DAYS = int(os.getenv("REMIND_BEFORE_DAYS", "2"))
# ID приватного канала/чата для лога продаж (бот должен быть админом). Пусто = выключено.
SALES_LOG_CHAT_ID = os.getenv("SALES_LOG_CHAT_ID", "").strip()

# Пресеты сумм пополнения баланса (₽)
TOPUP_PRESETS = [int(x) for x in os.getenv("TOPUP_PRESETS", "100,300,500,1000").split(",")]

# Предзаказ (когда сервера нет в наличии)
PREORDER_REFUND_HOURS = int(os.getenv("PREORDER_REFUND_HOURS", "6"))
PREORDER_PROMISE_MIN = os.getenv("PREORDER_PROMISE_MIN", "10")

# ============ СКЛАД / ЗАКУПКИ ============
# Минимальный запас свободных конфигов на регион. Ниже — создаётся заявка на закупку.
RESTOCK_THRESHOLD = int(os.getenv("RESTOCK_THRESHOLD", "8"))
# Сколько конфигов даёт партнёр за одну покупку (для подсказки "нужно N").
RESTOCK_BATCH = int(os.getenv("RESTOCK_BATCH", "8"))

# ============ ПРОГРАММА ЛОЯЛЬНОСТИ ============
# Накопительная скидка по сумме всех покупок (в ₽).
# Список (порог_потрачено_₽, скидка_%) — берётся максимальный подходящий уровень.
# Не суммируется с промокодом: применяется бОльшая из двух скидок.
LOYALTY_TIERS = [
    (1000, 5),    # потратил 1000 ₽  → 5%
    (3000, 10),   # потратил 3000 ₽  → 10%
    (7000, 15),   # потратил 7000 ₽  → 15%
    (15000, 20),  # потратил 15000 ₽ → 20%
]

# ============ АВТОПРОДЛЕНИЕ ============
# За сколько дней до конца пытаться списать с баланса и продлить автоматически.
AUTORENEW_BEFORE_DAYS = int(os.getenv("AUTORENEW_BEFORE_DAYS", "1"))


# ============ ОПЛАТА ============
# stars | yookassa | crypto | lava | choice
# choice = показать пользователю выбор: Карта / СБП / Крипта
PAYMENT_MODE = os.getenv("PAYMENT_MODE", "stars")

# Telegram Stars
RUB_PER_STAR = float(os.getenv("RUB_PER_STAR", "1.6"))

# ЮKassa
PROVIDER_TOKEN = os.getenv("PROVIDER_TOKEN", "")
CURRENCY = os.getenv("CURRENCY", "RUB")

# Crypto Pay (@CryptoBot)
CRYPTO_PAY_TOKEN = os.getenv("CRYPTO_PAY_TOKEN", "")
CRYPTO_ASSET = os.getenv("CRYPTO_ASSET", "USDT")
CRYPTO_TESTNET = os.getenv("CRYPTO_TESTNET", "false").lower() in ("1", "true", "yes")
USDT_RUB_RATE = float(os.getenv("USDT_RUB_RATE", "90"))

# Запасной курс USD->RUB для отображения цен в долларах (EN-версия).
# Основной курс берётся автоматически; это значение — fallback.
USD_RUB_RATE = float(os.getenv("USD_RUB_RATE", "74"))

# LAVA Business (business.lava.ru)
LAVA_SHOP_ID = os.getenv("LAVA_SHOP_ID", "")
LAVA_SECRET_KEY = os.getenv("LAVA_SECRET_KEY", "")

# ============ WEB APP (оплата через Mini App / СБП) ============
# URL задеплоенного Web App (например, Railway: https://<проект>.up.railway.app).
# Используется в кнопке WebAppInfo для оплаты через СБП прямо в Telegram.
WEBAPP_URL = os.getenv("WEBAPP_URL", "https://your-app.up.railway.app")

# ============ ТАРИФЫ И ЦЕНЫ (в рублях) ============
PLANS = {
    "standard": {
        "title": "Standard",
        "emoji": "🐱",
        "speed": "100 Мбит/с",
        "premium_access": False,
        "features": [
            "Стандартное шифрование",
            "Без доступа к ⭐️ Premium-серверам",
            "Базовая поддержка"
        ],
        "prices": {
            (1, "month"): 129,
            (1, "3month"): 299,
            (1, "6month"): 449,
            (1, "year"): 599,

            (2, "month"): 199,
            (2, "3month"): 499,
            (2, "6month"): 699,
            (2, "year"): 899,

            (4, "month"): 299,
            (4, "3month"): 799,
            (4, "6month"): 1099,
            (4, "year"): 1299,
        },
    },

    "premium": {
        "title": "Premium",
        "emoji": "💫",
        "speed": "200 Мбит/с",
        "premium_access": True,
        "features": [
            "Доступ к ⭐️ Premium-серверам",
            "Блокировка рекламы",
            "Приоритетная поддержка"
        ],
        "prices": {
            (1, "month"): 199,
            (1, "3month"): 499,
            (1, "6month"): 799,
            (1, "year"): 999,

            (2, "month"): 279,
            (2, "3month"): 699,
            (2, "6month"): 1099,
            (2, "year"): 1399,

            (4, "month"): 399,
            (4, "3month"): 699,
            (4, "6month"): 999,
            (4, "year"): 1590,
        },
    },

    "ultimate": {
        "title": "Ultimate",
        "emoji": "🌟",
        "speed": "250 Мбит/с",
        "premium_access": True,
        "features": [
            "Доступ к ⭐️ Premium-серверам",
            "Блокировка рекламы",
            "Двойное шифрование",
            "Максимальный приоритет"
        ],
        "prices": {
            (1, "month"): 249,
            (1, "3month"): 649,
            (1, "6month"): 999,
            (1, "year"): 1199,

            (2, "month"): 379,
            (2, "3month"): 999,
            (2, "6month"): 1499,
            (2, "year"): 1799,

            (4, "month"): 649,
            (4, "3month"): 990,
            (4, "6month"): 1290,
            (4, "year"): 1690,
        },
    },
}

PLAN_ORDER = ["standard", "premium", "ultimate"]

# === ФИКС «0 ₽» У PRIME ===
# Карточка и покупка Prime берут цену через price_rub(PRIME_PLAN, PRIME_DEVICES, period),
# то есть ИЩУТ пару (кол-во_устройств, период) в прайс-листе тарифа. В обычной сетке
# есть только 1/2/4 устройства, поэтому для PRIME_DEVICES (5) пары нет → возвращается 0,
# и Prime показывается/продаётся за 0 ₽ (PRIME_PRICES сам по себе тут не используется).
# Регистрируем цены Prime как реальные позиции прайса под текущее PRIME_DEVICES —
# на ВСЕ периоды из PRIME_PRICES. Работает для любого PRIME_DEVICES (хоть 5, хоть 8).
# В обычную покупку «5 устройств» не попадёт: devices_kb жёстко предлагает только 1/2/4.
for _prime_period, _prime_price in PRIME_PRICES.items():
    PLANS[PRIME_PLAN]["prices"][(PRIME_DEVICES, _prime_period)] = _prime_price

# ============ КАТАЛОГ РЕГИОНОВ (всегда показываются в покупке) ============
DEFAULT_REGION_CATALOG = [
    ("Нидерланды", False),
    ("Великобритания", False),
    ("Германия", False),
    ("Швейцария", False),
    ("Польша", False),
    ("Латвия", False),
    ("Норвегия", False),
    ("США", False),
    ("Финляндия", False),
    ("Эстония", False),
    ("Франция", True),
    ("Австрия", True),
    ("Хорватия", True),
    ("Турция", True),
    ("Россия", True),
    ("Южная Корея", True),
    ("Болгария", True),
    ("Словения", True),
    ("Австралия", True),
    ("Швеция", True),
]

PERIOD_DAYS = {
    "month": 30,
    "3month": 90,
    "6month": 180,
    "year": 365,
    "trial": TRIAL_DAYS,
}

PERIOD_TITLE = {
    "month": "1 месяц",
    "3month": "3 месяца",
    "6month": "6 месяцев",
    "year": "1 год",
    "trial": f"{TRIAL_DAYS} дня (пробный)",
}
DEVICE_TITLE = {1: "1 устройство", 2: "2 устройства", 4: "4 устройства"}

# ============ ЗАМОРОЗКА ПОДПИСКИ (пауза) ============
FREEZE_PRICE = int(os.getenv("FREEZE_PRICE", "10"))
FREEZE_DAYS = int(os.getenv("FREEZE_DAYS", "7"))
FREEZE_COOLDOWN_DAYS = int(os.getenv("FREEZE_COOLDOWN_DAYS", "30"))

# ============ A/B ТЕСТЫ ============
AB_EXPERIMENT = os.getenv("AB_EXPERIMENT", "").strip()
AB_EXPERIMENTS = {
    "trial_len": {
        "title": "Длина триала (3 vs 7 дней)",
        "metric": "конверсия триал→оплата",
        "variants": {
            "A": {"extra_days": 0},
            "B": {"extra_days": 4},
        },
    },
}

# ============ ВОРОНКА ВОЗВРАТА (win-back) ============
WINBACK_AFTER_DAYS = int(os.getenv("WINBACK_AFTER_DAYS", "3"))
WINBACK_PROMO_PERCENT = int(os.getenv("WINBACK_PROMO_PERCENT", "20"))
WINBACK_PROMO_DAYS = int(os.getenv("WINBACK_PROMO_DAYS", "3"))

# ============ БЭКАПЫ БАЗЫ ============
BACKUP_EVERY_HOURS = int(os.getenv("BACKUP_EVERY_HOURS", "24"))

# ============ FSM STORAGE ============
REDIS_URL = os.getenv("REDIS_URL", "").strip()
