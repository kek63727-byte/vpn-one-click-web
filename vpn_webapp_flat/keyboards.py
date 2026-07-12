"""Флаги и инлайн-клавиатуры (RU/EN)."""

from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

from config import (
    NEWS_CHANNEL_URL, PLAN_ORDER, PLANS, PRIME_ENABLED, SUPPORT_USERNAME, CHANNEL_BONUS_DAYS,
    WEBAPP_URL,
)
from payments import price_rub
from texts import dev_title, money, per_title, region_name

FLAGS = {
    "germany": "🇩🇪", "netherlands": "🇳🇱", "usa": "🇺🇸", "us": "🇺🇸",
    "france": "🇫🇷", "finland": "🇫🇮", "japan": "🇯🇵", "uk": "🇬🇧",
    "sweden": "🇸🇪", "poland": "🇵🇱", "turkey": "🇹🇷", "russia": "🇷🇺",
    "singapore": "🇸🇬", "switzerland": "🇨🇭", "austria": "🇦🇹",
    "estonia": "🇪🇪", "latvia": "🇱🇻", "norway": "🇳🇴", "croatia": "🇭🇷",
    "bulgaria": "🇧🇬", "slovenia": "🇸🇮", "australia": "🇦🇺", "korea": "🇰🇷",
    "германия": "🇩🇪", "нидерланды": "🇳🇱", "сша": "🇺🇸", "франция": "🇫🇷",
    "финляндия": "🇫🇮", "япония": "🇯🇵", "британия": "🇬🇧",
    "великобритания": "🇬🇧", "швеция": "🇸🇪", "польша": "🇵🇱",
    "турция": "🇹🇷", "россия": "🇷🇺", "сингапур": "🇸🇬",
    "швейцария": "🇨🇭", "австрия": "🇦🇹", "эстония": "🇪🇪",
    "латвия": "🇱🇻", "норвегия": "🇳🇴", "хорватия": "🇭🇷",
    "болгария": "🇧🇬", "словения": "🇸🇮", "австралия": "🇦🇺",
    "корея": "🇰🇷", "южная корея": "🇰🇷",
}


def flag(region: str) -> str:
    return FLAGS.get(region.lower(), "📍")


def _t(lang, ru, en):
    return en if lang == "en" else ru


# Подписи нижнего (reply) меню. Ключ → (RU, EN). Используются и клавиатурой, и хендлерами.
REPLY_LABELS = {
    "buy":     ("🌐 Купить подписку", "🌐 Buy subscription"),
    "my":      ("📁 Мои подключения", "📁 My connections"),
    "profile": ("👤 Профиль", "👤 Profile"),
    "prime":   ("👑 Prime подписка", "👑 Prime subscription"),
    "support": ("💬 Поддержка", "💬 Support"),
    "menu":    ("🏠 Меню", "🏠 Menu"),
    "hide":    ("✖️ Скрыть меню", "✖️ Hide menu"),
}


def reply_menu_kb(lang="ru"):
    """Нижняя клавиатура (над полем ввода). Сворачивается после нажатия, открывается иконкой."""
    from config import PRIME_ENABLED
    kb = ReplyKeyboardBuilder()
    kb.button(text=_t(lang, *REPLY_LABELS["buy"]))
    kb.button(text=_t(lang, *REPLY_LABELS["my"]))
    kb.button(text=_t(lang, *REPLY_LABELS["profile"]))
    if PRIME_ENABLED:
        kb.button(text=_t(lang, *REPLY_LABELS["prime"]))
    kb.button(text=_t(lang, *REPLY_LABELS["support"]))
    if WEBAPP_URL:
        kb.button(text=_t(lang, "🌐 Открыть приложение", "🌐 Open app"), web_app=WebAppInfo(url=WEBAPP_URL))
    kb.button(text=_t(lang, *REPLY_LABELS["menu"]))
    kb.button(text=_t(lang, *REPLY_LABELS["hide"]))
    if PRIME_ENABLED:
        kb.adjust(1, 2, 2, 2)
    else:
        kb.adjust(1, 2, 2, 1)
    return kb.as_markup(resize_keyboard=True, one_time_keyboard=True)


def language_kb():
    kb = InlineKeyboardBuilder()
    kb.button(text="🇷🇺 Русский", callback_data="setlang:ru")
    kb.button(text="🇬🇧 English", callback_data="setlang:en")
    kb.adjust(1)
    return kb.as_markup()


def main_menu_kb(lang="ru"):
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(lang, "🎁 Триал 3 дня", "🎁 3-day trial"), callback_data="trial")
    kb.button(text=_t(lang, "💰 Баланс", "💰 Balance"), callback_data="balance")
    kb.button(text=_t(lang, "👥 Пригласить друга", "👥 Invite a friend"), callback_data="ref")
    kb.button(text=_t(lang, "🧾 Мои платежи", "🧾 My payments"), callback_data="history")
    kb.button(text=_t(lang, f"🎁 +{CHANNEL_BONUS_DAYS} дня за подписку", f"🎁 +{CHANNEL_BONUS_DAYS} days for sub"), callback_data="chanbonus")
    kb.button(text=_t(lang, "⚡️ Оплата СБП", "⚡️ SBP Payment"), callback_data="webapp_pay")
    kb.button(text=_t(lang, "📖 Как подключиться", "📖 How to connect"), callback_data="howto")
    kb.button(text=_t(lang, "❓ FAQ", "❓ FAQ"), callback_data="faq")
    kb.button(text=_t(lang, "📰 Новости", "📰 News"), url=NEWS_CHANNEL_URL)
    kb.button(text=_t(lang, "ℹ️ О сервисе", "ℹ️ About"), callback_data="about")
    kb.button(text="🌐 Язык · Language", callback_data="lang")
    kb.adjust(2, 2, 2, 2, 2, 1)
    return kb.as_markup()


def balance_kb(lang="ru"):
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(lang, "➕ Пополнить баланс", "➕ Top up balance"), callback_data="topup")
    kb.button(text=_t(lang, "🎟 Промокод", "🎟 Promo code"), callback_data="promobal")
    kb.button(text=_t(lang, "🎁 Подарить баланс", "🎁 Gift balance"), callback_data="gift")
    kb.button(text=_t(lang, "🛒 Купить подписку", "🛒 Buy subscription"), callback_data="buy")
    kb.button(text=_t(lang, "⬅️ В главное меню", "⬅️ Main menu"), callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def gift_amounts_kb(presets, lang="ru", usd_rate=None):
    kb = InlineKeyboardBuilder()
    for amount in presets:
        kb.button(text=money(amount, lang, usd_rate), callback_data=f"giftamt:{amount}")
    kb.button(text=_t(lang, "⬅️ Назад", "⬅️ Back"), callback_data="balance")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def profile_kb(autopay_on, lang="ru"):
    kb = InlineKeyboardBuilder()
    if autopay_on:
        kb.button(text=_t(lang, "🔁 Автопродление: вкл ✅", "🔁 Auto-renew: on ✅"), callback_data="autopay:off")
    else:
        kb.button(text=_t(lang, "🔁 Включить автопродление", "🔁 Enable auto-renew"), callback_data="autopay:on")
    kb.button(text=_t(lang, "📁 Мои подключения", "📁 My connections"), callback_data="my")
    kb.button(text=_t(lang, "💰 Баланс", "💰 Balance"), callback_data="balance")
    kb.button(text=_t(lang, "⬅️ В главное меню", "⬅️ Main menu"), callback_data="menu")
    kb.adjust(1, 2, 1)
    return kb.as_markup()


def support_kb(lang="ru"):
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(lang, "✍️ Написать обращение", "✍️ Write to support"), callback_data="ticket")
    kb.button(text=_t(lang, "💬 Открыть чат поддержки", "💬 Open support chat"),
              url=f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")
    kb.button(text=_t(lang, "📰 Новостной канал", "📰 News channel"), url=NEWS_CHANNEL_URL)
    kb.button(text=_t(lang, "⬅️ В главное меню", "⬅️ Main menu"), callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def prime_locations_kb(regions, lang="ru"):
    """Локации для Prime: компактная сетка 2 столбца, доступные сверху, + авто-подбор."""
    from config import PRIME_DEVICES
    regs = sorted(regions, key=lambda r: (r[2] < PRIME_DEVICES, -r[2], region_name(r[0], lang)))
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(lang, "⚡️ Подобрать автоматически", "⚡️ Auto-pick best"),
              callback_data="primeauto")
    for region, prem, free in regs:
        star = "⭐️" if prem else ""
        mark = "✅" if free >= PRIME_DEVICES else "⏳"
        kb.button(text=f"{star}{flag(region)} {region_name(region, lang)} {mark}",
                  callback_data=f"primeloc:{region}")
    kb.button(text=_t(lang, "⬅️ В главное меню", "⬅️ Main menu"), callback_data="menu")
    n = len(regs)
    sizes = [1] + [2] * (n // 2) + ([1] if n % 2 else []) + [1]
    kb.adjust(*sizes)
    return kb.as_markup()


def topup_amounts_kb(presets, lang="ru", usd_rate=None):
    kb = InlineKeyboardBuilder()
    for amount in presets:
        kb.button(text=money(amount, lang, usd_rate), callback_data=f"topupamt:{amount}")
    kb.button(text=_t(lang, "✏️ Своя сумма", "✏️ Custom amount"), callback_data="topupcustom")
    kb.button(text=_t(lang, "⬅️ Назад", "⬅️ Back"), callback_data="balance")
    kb.adjust(2, 2, 1, 1)
    return kb.as_markup()


def topup_methods_kb(amount, lang="ru"):
    kb = InlineKeyboardBuilder()
    if lang == "en":
        kb.button(text="🪙 Cryptocurrency", callback_data=f"tmethod:crypto:{amount}")
    else:
        kb.button(text="💳 Банковская карта", callback_data=f"tmethod:lava:{amount}")
        kb.button(text="⚡️ СБП", callback_data=f"tmethod:sbp:{amount}")
        kb.button(text="🪙 Криптовалюта", callback_data=f"tmethod:crypto:{amount}")
    kb.button(text=_t(lang, "⬅️ Назад", "⬅️ Back"), callback_data="topup")
    kb.adjust(1)
    return kb.as_markup()


def back_to_menu_kb(lang="ru"):
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(lang, "⬅️ В главное меню", "⬅️ Main menu"), callback_data="menu")
    return kb.as_markup()


def plans_kb(lang="ru", usd_rate=None):
    import store
    kb = InlineKeyboardBuilder()
    frm_word = _t(lang, "от", "from")
    for key in PLAN_ORDER:
        p = PLANS[key]
        frm = min(store.plan_prices(key).values())
        kb.button(text=f"{p['emoji']} {p['title']} — {frm_word} {money(frm, lang, usd_rate)}", callback_data=f"plan:{key}")
    kb.button(text=_t(lang, "⬅️ В главное меню", "⬅️ Main menu"), callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def buy_webapp_kb(lang="ru"):
    """Кнопка открытия Mini App для оплаты через СБП — открывается прямо внутри Telegram."""
    from aiogram.types import WebAppInfo
    kb = InlineKeyboardBuilder()
    kb.button(
        text=_t(lang, "⚡️ Открыть форму оплаты СБП", "⚡️ Open SBP payment form"),
        web_app=WebAppInfo(url=WEBAPP_URL),
    )
    kb.button(
        text=_t(lang, "⬅️ В главное меню", "⬅️ Main menu"),
        callback_data="menu",
    )
    kb.adjust(1)
    return kb.as_markup()


def devices_kb(plan, lang="ru"):
    kb = InlineKeyboardBuilder()
    for n in (1, 2, 4):
        kb.button(text=f"📱 {dev_title(n, lang)}", callback_data=f"dev:{plan}:{n}")
    kb.button(text=_t(lang, "⬅️ К тарифам", "⬅️ Back to plans"), callback_data="buy")
    kb.adjust(1)
    return kb.as_markup()


def periods_kb(plan, devices, lang="ru", usd_rate=None):
    kb = InlineKeyboardBuilder()
    monthly = price_rub(plan, devices, "month")
    for period in ("month", "3month", "6month", "year"):
        rub = price_rub(plan, devices, period)
        label = f"📅 {per_title(period, lang)} — {money(rub, lang, usd_rate)}"
        if period == "year" and monthly > 0 and rub > 0:
            save = round((1 - rub / (monthly * 12)) * 100)
            if save > 0:
                label += f" · 🔥 −{save}%"
        kb.button(text=label, callback_data=f"per:{plan}:{devices}:{period}")
    kb.button(text=_t(lang, "⬅️ Назад", "⬅️ Back"), callback_data=f"plan:{plan}")
    kb.adjust(1)
    return kb.as_markup()


def locations_kb(plan, devices, period, regions, lang="ru"):
    premium_access = PLANS[plan]["premium_access"]
    kb = InlineKeyboardBuilder()

    def is_locked(r):
        return r[1] and not premium_access

    regs = sorted(regions, key=lambda r: (is_locked(r), r[2] < devices, -r[2], region_name(r[0], lang)))
    for region, prem, free in regs:
        rname = region_name(region, lang)
        if prem and not premium_access:
            kb.button(text=f"🔒 {flag(region)} {rname}", callback_data="locked")
        else:
            star = "⭐️" if prem else ""
            mark = "✅" if free >= devices else "⏳"
            kb.button(text=f"{star}{flag(region)} {rname} {mark}",
                      callback_data=f"buyloc:{plan}:{devices}:{period}:{region}")
    kb.button(text=_t(lang, "🎟 Промокод", "🎟 Promo code"), callback_data=f"promoask:{plan}:{devices}:{period}")
    kb.button(text=_t(lang, "⬅️ Назад", "⬅️ Back"), callback_data=f"dev:{plan}:{devices}")
    n = len(regs)
    sizes = [2] * (n // 2) + ([1] if n % 2 else []) + [1, 1]
    kb.adjust(*sizes)
    return kb.as_markup()


def trial_locations_kb(regions, lang="ru"):
    kb = InlineKeyboardBuilder()
    regs = [r for r in regions if not r[1]]
    for region, prem, free in regs:
        kb.button(text=f"{flag(region)} {region_name(region, lang)}", callback_data=f"trialloc:{region}")
    kb.button(text=_t(lang, "⬅️ В главное меню", "⬅️ Main menu"), callback_data="menu")
    n = len(regs)
    sizes = [2] * (n // 2) + ([1] if n % 2 else []) + [1]
    kb.adjust(*sizes)
    return kb.as_markup()


def referral_kb(lang="ru"):
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(lang, "💸 Вывести заработок", "💸 Withdraw earnings"), callback_data="refwd")
    kb.button(text=_t(lang, "⬅️ В главное меню", "⬅️ Main menu"), callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def howto_kb(lang="ru"):
    kb = InlineKeyboardBuilder()
    kb.button(text="💻 Windows", callback_data="guide:windows")
    kb.button(text="💻 macOS", callback_data="guide:macos")
    kb.button(text="📱 Android", callback_data="guide:android")
    kb.button(text="🍏 iPhone", callback_data="guide:iphone")
    kb.button(text=_t(lang, "⬅️ В главное меню", "⬅️ Main menu"), callback_data="menu")
    kb.adjust(2, 2, 1)
    return kb.as_markup()


def guide_back_kb(lang="ru"):
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(lang, "⬅️ К платформам", "⬅️ Platforms"), callback_data="howto")
    kb.button(text=_t(lang, "🏠 Меню", "🏠 Menu"), callback_data="menu")
    kb.adjust(2)
    return kb.as_markup()


def renew_kb(config_id, lang="ru"):
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(lang, "🔄 Продлить", "🔄 Renew"), callback_data=f"renew:{config_id}")
    return kb.as_markup()


def connection_kb(config_id, lang="ru"):
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(lang, "🔄 Продлить", "🔄 Renew"), callback_data=f"renew:{config_id}")
    kb.button(text=_t(lang, "🔁 Заменить конфиг", "🔁 Replace config"), callback_data=f"rep:{config_id}")
    kb.button(text=_t(lang, "⏸ Заморозить", "⏸ Pause"), callback_data=f"frz:{config_id}")
    kb.adjust(2, 1)
    return kb.as_markup()


def replace_reasons_kb(config_id, lang="ru"):
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(lang, "🚫 Не работает / не подключается", "🚫 Not working"),
              callback_data=f"repr:{config_id}:dead")
    kb.button(text=_t(lang, "🐢 Медленно / нестабильно", "🐢 Slow / unstable"),
              callback_data=f"repr:{config_id}:slow")
    kb.button(text=_t(lang, "📱 Заблокировал провайдер", "📱 Blocked by ISP"),
              callback_data=f"repr:{config_id}:blocked")
    kb.button(text=_t(lang, "🌍 Сменить страну", "🌍 Change country"),
              callback_data=f"repr:{config_id}:country")
    kb.button(text=_t(lang, "✍️ Другая причина", "✍️ Other reason"),
              callback_data=f"repr:{config_id}:other")
    kb.button(text=_t(lang, "⬅️ Назад", "⬅️ Back"), callback_data="my")
    kb.adjust(1)
    return kb.as_markup()


def replace_country_kb(config_id, regions, premium_access, lang="ru"):
    kb = InlineKeyboardBuilder()
    for region, prem, free in regions:
        if prem and not premium_access:
            continue
        if free < 1:
            continue
        star = "⭐️ " if prem else ""
        kb.button(text=f"{star}{flag(region)} {region_name(region, lang)} — {free}",
                  callback_data=f"repc:{config_id}:{region}")
    kb.button(text=_t(lang, "⬅️ Назад", "⬅️ Back"), callback_data=f"rep:{config_id}")
    kb.adjust(1)
    return kb.as_markup()


def captcha_kb(target, options):
    """Кнопки капчи: верный эмодзи → capok, остальные → capno."""
    kb = InlineKeyboardBuilder()
    for emo in options:
        kb.button(text=emo, callback_data="capok" if emo == target else "capno")
    kb.adjust(len(options))
    return kb.as_markup()


def chanbonus_kb(lang="ru"):
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(lang, "📢 Подписаться", "📢 Subscribe"), url=NEWS_CHANNEL_URL)
    kb.button(text=_t(lang, "✅ Я подписался", "✅ I subscribed"), callback_data="chanbonus")
    kb.button(text=_t(lang, "⬅️ В главное меню", "⬅️ Main menu"), callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def sub_buy_kb(plan, devices, period, lang="ru"):
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(lang, "💳 Купить подписку", "💳 Buy subscription"),
              callback_data=f"subbuy:{plan}:{devices}:{period}")
    kb.button(text=_t(lang, "🎟 Промокод", "🎟 Promo code"),
              callback_data=f"promoask:{plan}:{devices}:{period}")
    kb.button(text=_t(lang, "⬅️ Назад", "⬅️ Back"), callback_data=f"dev:{plan}:{devices}")
    kb.adjust(1)
    return kb.as_markup()


def sub_activate_kb(sub_id, free_slots, lang="ru"):
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(lang, f"➕ Активировать устройство ({free_slots} осталось)",
                      f"➕ Activate a device ({free_slots} left)"),
              callback_data=f"subact:{sub_id}")
    kb.adjust(1)
    return kb.as_markup()


def sub_activate_locations_kb(sub_id, regions, lang="ru"):
    """Регионы для активации одного устройства (2 столбца, только доступные сразу)."""
    kb = InlineKeyboardBuilder()
    regs = sorted(regions, key=lambda r: (r[1], region_name(r[0], lang)))
    for region, prem, free in regs:
        star = "⭐️" if prem else ""
        kb.button(text=f"{star}{flag(region)} {region_name(region, lang)}",
                  callback_data=f"subactloc:{sub_id}:{region}")
    kb.button(text=_t(lang, "⬅️ В главное меню", "⬅️ Main menu"), callback_data="menu")
    n = len(regs)
    sizes = [2] * (n // 2) + ([1] if n % 2 else []) + [1]
    kb.adjust(*sizes)
    return kb.as_markup()


def prime_periods_kb(lang="ru", usd_rate=None):
    """Выбор периода для Prime: месяц или год, у каждого своя цена."""
    from config import PRIME_PRICES
    kb = InlineKeyboardBuilder()
    month_price = PRIME_PRICES["month"]
    year_price = PRIME_PRICES["year"]
    save = round((1 - year_price / (month_price * 12)) * 100) if month_price else 0
    kb.button(
        text=f"📅 {per_title('month', lang)} — {money(month_price, lang, usd_rate)}",
        callback_data="primeper:month",
    )
    year_label = f"📅 {per_title('year', lang)} — {money(year_price, lang, usd_rate)}"
    if save > 0:
        year_label += f" · 🔥 −{save}%"
    kb.button(text=year_label, callback_data="primeper:year")
    kb.button(text=_t(lang, "⬅️ В главное меню", "⬅️ Main menu"), callback_data="menu")
    kb.adjust(1)
    return kb.as_markup()


def prime_buy_kb(price_label, plan, devices, period, lang="ru"):
    """PRIME покупается как слот-подписка: без выбора региона, активация устройств позже."""
    kb = InlineKeyboardBuilder()
    kb.button(text=_t(lang, f"💳 Купить PRIME — {price_label}", f"💳 Buy PRIME — {price_label}"),
              callback_data=f"subbuy:{plan}:{devices}:{period}")
    kb.button(text=_t(lang, "🎟 Промокод", "🎟 Promo code"),
              callback_data=f"promoask:{plan}:{devices}:{period}")
    kb.button(text=_t(lang, "⬅️ Назад", "⬅️ Back"), callback_data="prime")
    kb.adjust(1)
    return kb.as_markup()
