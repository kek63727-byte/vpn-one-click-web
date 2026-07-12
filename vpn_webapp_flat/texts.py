"""Тексты бота (RU/EN). Каждая функция принимает lang='ru'|'en'."""

from config import (
    BRAND,
    FREEZE_DAYS,
    FREEZE_PRICE,
    NEWS_CHANNEL_URL,
    PLANS,
    PREORDER_PROMISE_MIN,
    REF_MIN_PAYOUT,
    REF_PERCENT,
    REF_REWARD_DAYS,
    RULES_URL,
    SUPPORT_URL,
    SUPPORT_USERNAME,
    TRIAL_DAYS,
    WINBACK_PROMO_DAYS,
    WINBACK_PROMO_PERCENT,
)

LINE = "➖➖➖➖➖➖➖➖➖➖"


# ============ ЛОКАЛИЗАЦИЯ НАЗВАНИЙ РЕГИОНОВ ============
# Ключ — любое написание (ru/en, в нижнем регистре), значение — (RU, EN).
# В БД и callback_data регион хранится как есть; переводим ТОЛЬКО для показа.
_REGION_I18N = {
    "germany": ("Германия", "Germany"), "германия": ("Германия", "Germany"),
    "netherlands": ("Нидерланды", "Netherlands"), "нидерланды": ("Нидерланды", "Netherlands"),
    "usa": ("США", "USA"), "us": ("США", "USA"), "сша": ("США", "USA"),
    "france": ("Франция", "France"), "франция": ("Франция", "France"),
    "finland": ("Финляндия", "Finland"), "финляндия": ("Финляндия", "Finland"),
    "japan": ("Япония", "Japan"), "япония": ("Япония", "Japan"),
    "uk": ("Великобритания", "United Kingdom"), "британия": ("Великобритания", "United Kingdom"),
    "великобритания": ("Великобритания", "United Kingdom"),
    "sweden": ("Швеция", "Sweden"), "швеция": ("Швеция", "Sweden"),
    "poland": ("Польша", "Poland"), "польша": ("Польша", "Poland"),
    "turkey": ("Турция", "Turkey"), "турция": ("Турция", "Turkey"),
    "russia": ("Россия", "Russia"), "россия": ("Россия", "Russia"),
    "singapore": ("Сингапур", "Singapore"), "сингапур": ("Сингапур", "Singapore"),
    "switzerland": ("Швейцария", "Switzerland"), "швейцария": ("Швейцария", "Switzerland"),
    "austria": ("Австрия", "Austria"), "австрия": ("Австрия", "Austria"),
    "estonia": ("Эстония", "Estonia"), "эстония": ("Эстония", "Estonia"),
    "latvia": ("Латвия", "Latvia"), "латвия": ("Латвия", "Latvia"),
    "norway": ("Норвегия", "Norway"), "норвегия": ("Норвегия", "Norway"),
    "croatia": ("Хорватия", "Croatia"), "хорватия": ("Хорватия", "Croatia"),
    "bulgaria": ("Болгария", "Bulgaria"), "болгария": ("Болгария", "Bulgaria"),
    "slovenia": ("Словения", "Slovenia"), "словения": ("Словения", "Slovenia"),
    "australia": ("Австралия", "Australia"), "австралия": ("Австралия", "Australia"),
    "korea": ("Южная Корея", "South Korea"), "корея": ("Южная Корея", "South Korea"),
    "южная корея": ("Южная Корея", "South Korea"),
}


def region_name(region, lang="ru"):
    """Локализованное название региона для показа. Неизвестное — как есть."""
    if not region:
        return region
    ru, en = _REGION_I18N.get(str(region).strip().lower(), (region, region))
    return en if lang == "en" else ru


def region_slug(region):
    """ASCII-слаг региона для имени .conf-файла (без кириллицы)."""
    import re
    _ru, en = _REGION_I18N.get(str(region).strip().lower(), (region, region))
    slug = re.sub(r"[^a-zA-Z0-9]+", "_", str(en)).strip("_").lower()
    return slug or "vpn"


def money(rub, lang="ru", usd_rate=None):
    """Цена для показа: рубли (RU) или доллары (EN, если передан курс)."""
    if lang == "en" and usd_rate:
        return f"${rub / usd_rate:.2f}"
    return f"{rub} ₽"


def _is_en(lang):
    return lang == "en"


def dev_title(n, lang="ru"):
    if _is_en(lang):
        return {1: "1 device", 2: "2 devices", 4: "4 devices"}.get(n, f"{n} devices")
    return {1: "1 устройство", 2: "2 устройства", 4: "4 устройства"}.get(n, f"{n} устройств")


def per_title(period, lang="ru"):
    if _is_en(lang):
        return {
            "month": "1 month",
            "3month": "3 months",
            "6month": "6 months",
            "year": "1 year",
            "trial": f"{TRIAL_DAYS} days (trial)",
        }[period]
    return {
        "month": "1 месяц",
        "3month": "3 месяца",
        "6month": "6 месяцев",
        "year": "1 год",
        "trial": f"{TRIAL_DAYS} дня (пробный)",
    }[period]


def choose_language():
    return ("🌐 <b>Выберите язык / Choose your language</b>\n" + LINE)


def welcome(lang="ru"):
    if _is_en(lang):
        return (
            f"⚡️ <b>{BRAND}</b> · <i>premium VPN</i>\n{LINE}\n"
            "The internet the way it should feel — borderless, instant, private. 🌍\n\n"
            "🛡 Enterprise-grade encryption (WireGuard)\n"
            "⚡️ Up to 250 Mbps · zero throttling\n"
            "🌐 Hand-picked server network across dozens of countries\n"
            "🤫 Strict no-logs policy · no ads · no compromises\n"
            "📱 Windows · macOS · Android · iPhone\n\n"
            f"🎁 <b>{TRIAL_DAYS} days on us</b> — feel the difference yourself.\n{LINE}\n"
            f"📦 <b>We currently work on a pre-order basis.</b>\n"
            f"After payment your working config is delivered within ~{PREORDER_PROMISE_MIN} minutes — "
            f"no need to reconnect or reconfigure anything.\n{LINE}\n"
            "Choose an action 👇"
        )
    return (
        f"⚡️ <b>{BRAND}</b> · <i>premium VPN</i>\n{LINE}\n"
        "Интернет таким, каким он должен быть — без границ, мгновенный, приватный. 🌍\n\n"
        "🛡 Шифрование корпоративного уровня (WireGuard)\n"
        "⚡️ До 250 Мбит/с · без ограничений скорости\n"
        "🌐 Отобранная сеть серверов в десятках стран\n"
        "🤫 Строгая политика no-logs · без рекламы · без компромиссов\n"
        "📱 Windows · macOS · Android · iPhone\n\n"
        f"🎁 <b>{TRIAL_DAYS} дня в подарок</b> — оцени разницу сам.\n{LINE}\n"
        f"📦 <b>Сейчас мы работаем по предзаказу.</b>\n"
        f"После оплаты рабочий конфиг выдаётся в течение ~{PREORDER_PROMISE_MIN} минут — "
        f"переподключаться и что-то перенастраивать не нужно, всё заработает сразу.\n{LINE}\n"
        "Выбери действие 👇"
    )


def about(lang="ru"):
    if _is_en(lang):
        return (
            f"ℹ️ <b>About {BRAND}</b>\n{LINE}\n"
            "We built a VPN we'd want to use ourselves — fast, quiet, and uncompromising.\n\n"
            "🛡 <b>WireGuard</b> — the modern protocol behind the fastest, most secure tunnels.\n"
            "🌐 A curated network, not a crowd — servers chosen for speed and stability.\n"
            "🤫 <b>Zero logs.</b> We don't collect, store or sell anything about you.\n"
            "🔒 Bypass blocks, mask your real IP, encrypt every byte.\n"
            "💳 Secure payments — card data is never stored.\n"
            f"{LINE}\n💬 Priority support whenever you need it: {SUPPORT_USERNAME}\n"
            "Ready? Tap «🛒 Buy subscription»."
        )
    return (
        f"ℹ️ <b>О сервисе {BRAND}</b>\n{LINE}\n"
        "Мы сделали VPN, которым хотим пользоваться сами — быстрый, тихий, без компромиссов.\n\n"
        "🛡 <b>WireGuard</b> — современный протокол самых быстрых и защищённых туннелей.\n"
        "🌐 Отобранная сеть, а не толпа — серверы под скорость и стабильность.\n"
        "🤫 <b>Ноль логов.</b> Мы не собираем, не храним и не продаём данные о тебе.\n"
        "🔒 Обходим блокировки, скрываем реальный IP, шифруем каждый байт.\n"
        "💳 Оплата безопасна — данные карты не сохраняются.\n"
        f"{LINE}\n💬 Приоритетная поддержка, когда нужно: {SUPPORT_USERNAME}\n"
        "Готов? Жми «🛒 Купить подписку»."
    )


def plan_card(plan_key, lang="ru", usd_rate=None):
    import store
    p = PLANS[plan_key]
    prices = store.plan_prices(plan_key)
    feats = _features(plan_key, lang)
    m1 = money(prices[(1, "month")], lang, usd_rate)
    m2 = money(prices[(2, "month")], lang, usd_rate)
    if _is_en(lang):
        speed_en = p["speed"].replace("Мбит/с", "Mbps")
        lines = [f"{p['emoji']} <b>{p['title']} plan</b>", LINE, f"⚡️ Speed: up to <b>{speed_en}</b>"]
        lines += [f"✅ {f}" for f in feats]
        lines += [LINE, "💰 <b>Prices:</b>",
                  f"• 1 device — from <b>{m1}</b>/mo",
                  f"• 2 devices — from <b>{m2}</b>/mo",
                  LINE, "👇 How many devices?"]
        return "\n".join(lines)
    lines = [f"{p['emoji']} <b>Тариф {p['title']}</b>", LINE, f"⚡️ Скорость: до <b>{p['speed']}</b>"]
    lines += [f"✅ {f}" for f in feats]
    lines += [LINE, "💰 <b>Цены:</b>",
              f"• 1 устройство — от <b>{m1}</b>/мес",
              f"• 2 устройства — от <b>{m2}</b>/мес",
              LINE, "👇 Сколько устройств подключаем?"]
    return "\n".join(lines)


_FEATURES_EN = {
    "standard": ["Standard encryption", "No access to ⭐️ Premium servers", "Basic support"],
    "premium": ["Access to ⭐️ Premium servers", "Ad blocking", "Priority support"],
    "ultimate": ["Access to ⭐️ Premium servers", "Ad blocking", "Double encryption", "Top priority"],
}


def _features(plan_key, lang):
    if _is_en(lang):
        return _FEATURES_EN.get(plan_key, PLANS[plan_key]["features"])
    return PLANS[plan_key]["features"]


def order_summary(plan_key, devices, period, full_rub, discount, lang="ru", usd_rate=None):
    p = PLANS[plan_key]
    to_pay = full_rub - discount
    m_full = money(full_rub, lang, usd_rate)
    m_disc = money(discount, lang, usd_rate)
    m_pay = money(to_pay, lang, usd_rate)
    if _is_en(lang):
        lines = ["🧾 <b>Checkout</b>", LINE,
                 f"{p['emoji']} Plan: <b>{p['title']}</b>",
                 f"📱 Devices: <b>{dev_title(devices, lang)}</b>",
                 f"📅 Period: <b>{per_title(period, lang)}</b>",
                 f"💰 Price: <b>{m_full}</b>"]
        if discount > 0:
            lines.append(f"🎁 Bonus applied: <b>−{m_disc}</b>")
            lines.append(f"💳 To pay: <b>{m_pay}</b>")
        lines += [LINE, "🌍 Choose a server location:",
                  "<i>✅ ready now · ⏳ pre-order (~10 min) · 🔒 Premium plans only</i>"]
        return "\n".join(lines)
    lines = ["🧾 <b>Оформление заказа</b>", LINE,
             f"{p['emoji']} Тариф: <b>{p['title']}</b>",
             f"📱 Устройств: <b>{dev_title(devices, lang)}</b>",
             f"📅 Период: <b>{per_title(period, lang)}</b>",
             f"💰 Стоимость: <b>{m_full}</b>"]
    if discount > 0:
        lines.append(f"🎁 Бонусом списываем: <b>−{m_disc}</b>")
        lines.append(f"💳 К оплате: <b>{m_pay}</b>")
    lines += [LINE, "🌍 Выбери локацию сервера:",
              "<i>✅ — сразу · ⏳ — под заказ (~10 мин) · 🔒 — только в Premium-тарифах</i>"]
    return "\n".join(lines)


def support(lang="ru"):
    if _is_en(lang):
        return (
            "💬 <b>Technical support</b>\n" + LINE + "\n"
            "If the VPN won't connect or is slow:\n"
            "1️⃣ Switch the server location\n"
            "2️⃣ Reconnect the tunnel in WireGuard\n\n"
            f"Still stuck? Message us: {SUPPORT_USERNAME}"
        )
    return (
        "💬 <b>Техническая поддержка</b>\n" + LINE + "\n"
        "Если VPN не подключается или работает медленно:\n"
        "1️⃣ Смени локацию сервера\n"
        "2️⃣ Переподключи туннель в WireGuard\n\n"
        f"Не помогло? Пиши нам: {SUPPORT_USERNAME}"
    )


def trial_intro(lang="ru"):
    if _is_en(lang):
        return (f"🎁 <b>Free trial — {TRIAL_DAYS} days</b>\n{LINE}\n"
                "Pick a location — I'll send a working config right now.\n"
                "No payment, no card 💳\n" + LINE + "\n🌍 Available servers:")
    return (f"🎁 <b>Пробный период — {TRIAL_DAYS} дня бесплатно</b>\n{LINE}\n"
            "Выбери локацию — пришлю рабочий конфиг прямо сейчас.\n"
            "Без оплаты и без карты 💳\n" + LINE + "\n🌍 Доступные серверы:")


def trial_used(lang="ru"):
    if _is_en(lang):
        return ("🎁 <b>Free trial already used</b>\n" + LINE + "\n"
                "Grab a subscription — it's quick and cheap 👇")
    return ("🎁 <b>Пробный период уже использован</b>\n" + LINE + "\n"
            "Оформи подписку — это быстро и недорого 👇")


def trial_busy_bonus(region, days, lang="ru"):
    if _is_en(lang):
        return ("🙏 <b>All trial servers are busy right now</b>\n" + LINE + "\n"
                f"But we didn't want to leave you empty-handed — so we added "
                f"<b>{days} days</b> to your subscription (<b>{region}</b>) for free! 🎁\n\n"
                "Thanks for being with us 💚")
    return ("🙏 <b>Все пробные серверы сейчас заняты</b>\n" + LINE + "\n"
            f"Но мы не хотим оставлять тебя без подарка — поэтому "
            f"добавили <b>{days} дня</b> к твоей подписке (<b>{region}</b>) бесплатно! 🎁\n\n"
            "Спасибо, что ты с нами 💚")


def trial_busy(lang="ru"):
    if _is_en(lang):
        return ("🙏 <b>All trial servers are busy right now</b>\n" + LINE + "\n"
                "We're adding new ones — check back a bit later.\n\n"
                "Meanwhile you can grab a subscription with any location 👇")
    return ("🙏 <b>Все пробные серверы сейчас заняты</b>\n" + LINE + "\n"
            "Мы уже добавляем новые — загляни чуть позже.\n\n"
            "А пока можешь оформить подписку с любой локацией 👇")


def referral(link, st, lang="ru"):
    cash = st.get("cash_rub", 0)
    if _is_en(lang):
        wd = (f"💸 You can withdraw it for real money via support (min {REF_MIN_PAYOUT} ₽)."
              if cash >= REF_MIN_PAYOUT
              else f"💸 Withdraw for real money from {REF_MIN_PAYOUT} ₽ (left: {max(0, REF_MIN_PAYOUT - cash)} ₽).")
        return (
            "👥 <b>Referral program</b>\n" + LINE + "\n"
            "Invite friends! For everyone who pays for a subscription you get:\n"
            f"💰 <b>{REF_PERCENT}%</b> of each of their payments — as real, withdrawable money\n"
            f"🎁 <b>{REF_REWARD_DAYS} days</b> added to your subscription\n"
            f"🏆 Milestone bonuses for 5 / 10 / 25 / 50 invited\n"
            f"{LINE}\n🔗 <b>Your link:</b>\n{link}\n{LINE}\n"
            f"👤 Invited: <b>{st['invited']}</b>\n"
            f"💵 Withdrawable: <b>{cash} ₽</b>\n"
            f"📈 Total earned: <b>{st['earned_rub']} ₽</b> · <b>{st['earned_days']}</b> days\n"
            f"{LINE}\n{wd}"
        )
    wd = (f"💸 Можно вывести реальными деньгами через поддержку (мин. {REF_MIN_PAYOUT} ₽)."
          if cash >= REF_MIN_PAYOUT
          else f"💸 Вывод реальными деньгами от {REF_MIN_PAYOUT} ₽ (осталось накопить: {max(0, REF_MIN_PAYOUT - cash)} ₽).")
    return (
        "👥 <b>Реферальная программа</b>\n" + LINE + "\n"
        "Приглашай друзей! За каждого, кто оплатит подписку, ты получаешь:\n"
        f"💰 <b>{REF_PERCENT}%</b> с каждой его покупки — реальными деньгами с выводом\n"
        f"🎁 <b>{REF_REWARD_DAYS} дня</b> к своей подписке\n"
        f"🏆 Бонусы за 5 / 10 / 25 / 50 приглашённых\n"
        f"{LINE}\n🔗 <b>Твоя ссылка:</b>\n{link}\n{LINE}\n"
        f"👤 Приглашено: <b>{st['invited']}</b>\n"
        f"💵 Доступно к выводу: <b>{cash} ₽</b>\n"
        f"📈 Всего заработано: <b>{st['earned_rub']} ₽</b> · <b>{st['earned_days']}</b> дн.\n"
        f"{LINE}\n{wd}"
    )


# ============ ИСТОРИЯ ПЛАТЕЖЕЙ ============

def pay_history(items, lang="ru", usd_rate=None):
    en = _is_en(lang)
    title = "🧾 <b>My payments</b>" if en else "🧾 <b>Мои платежи</b>"
    if not items:
        empty = "No payments yet." if en else "Платежей пока нет."
        return f"{title}\n{LINE}\n{empty}"
    lines = [title, LINE]
    for it in items:
        date = (it.get("at") or "")[:10]
        amt = money(it["amount"], lang, usd_rate)
        if it["kind"] == "topup":
            label = "Top-up" if en else "Пополнение"
            lines.append(f"➕ {date} · {label} · <b>{amt}</b> · {it.get('info','')}")
        else:
            p = PLANS.get(it.get("plan"), {}).get("title", it.get("plan", ""))
            reg = region_name(it.get("region", ""), lang)
            per = per_title(it.get("period", "month"), lang)
            if it.get("status") == "refunded":
                tag = "↩️ refund" if en else "↩️ возврат"
            else:
                tag = "🛒"
            lines.append(f"{tag} {date} · {p} · {reg} · {per} · <b>{amt}</b>")
    return "\n".join(lines)


# ============ ВЫВОД РЕФЕРАЛЬНЫХ ============

def payout_min_not_reached(cash, lang="ru"):
    if _is_en(lang):
        return (f"💸 Withdrawal is available from <b>{REF_MIN_PAYOUT} ₽</b>.\n"
                f"You have <b>{cash} ₽</b>. Keep inviting 👥")
    return (f"💸 Вывод доступен от <b>{REF_MIN_PAYOUT} ₽</b>.\n"
            f"У тебя <b>{cash} ₽</b>. Приглашай дальше 👥")


def payout_pending_already(lang="ru"):
    if _is_en(lang):
        return "⏳ You already have a pending withdrawal request. Please wait for it to be processed."
    return "⏳ У тебя уже есть заявка на вывод в обработке. Дождись её завершения."


def payout_created(amount, lang="ru"):
    if _is_en(lang):
        return (f"✅ <b>Withdrawal request created: {amount} ₽</b>\n{LINE}\n"
                f"Our team will contact you via {SUPPORT_USERNAME} to arrange the payout.")
    return (f"✅ <b>Заявка на вывод создана: {amount} ₽</b>\n{LINE}\n"
            f"С тобой свяжется поддержка {SUPPORT_USERNAME}, чтобы согласовать выплату.")


def payout_done_user(amount, lang="ru"):
    if _is_en(lang):
        return f"💸 Your withdrawal of <b>{amount} ₽</b> has been paid out. Thank you!"
    return f"💸 Твой вывод <b>{amount} ₽</b> выплачен. Спасибо!"


def payout_rejected_user(amount, lang="ru"):
    if _is_en(lang):
        return (f"↩️ Your withdrawal request ({amount} ₽) was declined and the amount "
                f"was returned to your referral balance.")
    return (f"↩️ Заявка на вывод ({amount} ₽) отклонена, сумма возвращена "
            f"на твой реферальный баланс.")


def admin_payout_alert(pid, user_id, amount, username=None, full_name=None):
    uname = f"@{username}" if username else "—"
    name = full_name or "—"
    return (f"💸 <b>ЗАЯВКА НА ВЫВОД #{pid}</b>\n{LINE}\n"
            f"👤 {name} ({uname})\n🆔 <code>{user_id}</code>\n"
            f"💵 Сумма: <b>{amount} ₽</b>\n{LINE}\n"
            f"Свяжись с пользователем и переведи. Затем отметь статус 👇")


def ref_milestone_msg(invited, bonus, lang="ru"):
    if _is_en(lang):
        return (f"🏆 <b>Milestone reached: {invited} invited!</b>\n"
                f"Bonus <b>+{bonus} ₽</b> added to your withdrawable balance. 🎉")
    return (f"🏆 <b>Достижение: {invited} приглашённых!</b>\n"
            f"Бонус <b>+{bonus} ₽</b> зачислен на выводимый баланс. 🎉")


# ============ ЗАМОРОЗКА ПОДПИСКИ ============

def freeze_offer(region, current_balance_str, lang="ru"):
    if _is_en(lang):
        return (f"⏸ <b>Pause subscription — {region}</b>\n{LINE}\n"
                f"Pausing adds <b>{FREEZE_DAYS} days</b> to your expiry date so you don't "
                f"lose time while away.\nPrice: <b>{FREEZE_PRICE} ₽</b> from balance "
                f"(you have {current_balance_str}).\n\nPause now?")
    return (f"⏸ <b>Заморозка подписки — {region}</b>\n{LINE}\n"
            f"Заморозка добавляет <b>{FREEZE_DAYS} дней</b> к сроку действия, чтобы ты "
            f"не терял дни, пока тебя нет.\nЦена: <b>{FREEZE_PRICE} ₽</b> с баланса "
            f"(у тебя {current_balance_str}).\n\nЗаморозить?")


def freeze_done(region, until_str, lang="ru"):
    if _is_en(lang):
        return (f"⏸ <b>Done!</b> {region} extended by {FREEZE_DAYS} days.\n"
                f"New expiry: <b>{until_str}</b>")
    return (f"⏸ <b>Готово!</b> {region} продлён на {FREEZE_DAYS} дней.\n"
            f"Новый срок: <b>{until_str}</b>")


def freeze_need_balance(need_str, have_str, lang="ru"):
    if _is_en(lang):
        return (f"😟 Not enough balance to pause.\nNeeded: <b>{need_str}</b>, you have <b>{have_str}</b>.")
    return (f"😟 Недостаточно баланса для заморозки.\nНужно: <b>{need_str}</b>, у тебя <b>{have_str}</b>.")


def freeze_cooldown(until_date, lang="ru"):
    if _is_en(lang):
        return (f"⏳ This subscription was paused recently.\n"
                f"Next pause will be available after <b>{until_date}</b>.")
    return (f"⏳ Эта подписка недавно замораживалась.\n"
            f"Следующая заморозка будет доступна после <b>{until_date}</b>.")


# ============ НИЗКИЙ БАЛАНС ПЕРЕД АВТОПРОДЛЕНИЕМ ============

def autopay_low_warn(region, need_str, have_str, lang="ru"):
    if _is_en(lang):
        return (f"⚠️ <b>Auto-renew soon — top up needed</b>\n{LINE}\n"
                f"Subscription {region} will auto-renew soon, but your balance is low.\n"
                f"Needed: <b>{need_str}</b>, you have <b>{have_str}</b>.\n"
                f"Top up to keep your access without interruptions 👇")
    return (f"⚠️ <b>Скоро автопродление — пополни баланс</b>\n{LINE}\n"
            f"Подписка {region} скоро продлится автоматически, но на балансе мало средств.\n"
            f"Нужно: <b>{need_str}</b>, у тебя <b>{have_str}</b>.\n"
            f"Пополни, чтобы не остаться без доступа 👇")


# ============ ВОЗВРАТ УШЕДШИХ (win-back) ============

def winback_msg(region, code, lang="ru"):
    if _is_en(lang):
        return (f"👋 <b>We miss you!</b>\n{LINE}\n"
                f"Your {region} subscription has expired. Come back with a personal "
                f"<b>−{WINBACK_PROMO_PERCENT}%</b> discount:\n\n"
                f"🎟 Promo code: <code>{code}</code>\n"
                f"⏳ Valid for {WINBACK_PROMO_DAYS} days. Apply it at checkout 👇")
    return (f"👋 <b>Скучаем!</b>\n{LINE}\n"
            f"Твоя подписка {region} закончилась. Возвращайся с личной скидкой "
            f"<b>−{WINBACK_PROMO_PERCENT}%</b>:\n\n"
            f"🎟 Промокод: <code>{code}</code>\n"
            f"⏳ Действует {WINBACK_PROMO_DAYS} дня. Введи его при оформлении 👇")


def howto_intro(lang="ru"):
    if _is_en(lang):
        return ("📖 <b>How to connect</b>\n" + LINE + "\n"
                "We use the free <b>WireGuard</b> app.\nPick your platform 👇")
    return ("📖 <b>Как подключиться</b>\n" + LINE + "\n"
            "Мы используем бесплатное приложение <b>WireGuard</b>.\nВыбери свою платформу 👇")


def faq(lang="ru"):
    if _is_en(lang):
        return (
            "❓ <b>FAQ — frequently asked questions</b>\n" + LINE + "\n"
            "<b>What is a VPN and what is it for?</b>\n"
            "It's an encrypted tunnel between you and the internet. It hides your real IP, "
            "bypasses blocks and protects traffic on public Wi-Fi.\n\n"
            "<b>How fast is it?</b>\n"
            "Up to 250 Mbps depending on the plan — enough for 4K, calls and gaming.\n\n"
            "<b>How many devices can I use?</b>\n"
            "Each config = 1 device. Pick the 2-device option, or buy several configs.\n\n"
            "<b>Do you keep logs?</b>\n"
            "No. Strict no-logs policy — we don't store your activity.\n\n"
            "<b>What if a server is slow or won't connect?</b>\n"
            "Switch the location and reconnect the tunnel. Still stuck — message support.\n\n"
            "<b>How do I pay?</b>\n"
            "Card, SBP or crypto. Balance top-ups let you pay any plan in one tap.\n\n"
            "<b>Can I get a refund?</b>\n"
            "If a pre-ordered server isn't ready in time, the amount returns to your balance "
            "automatically. For other cases — contact support.\n\n"
            "<b>How does auto-renew work?</b>\n"
            "Enable it in «📁 My connections». A day before expiry we charge your balance "
            "automatically and extend the subscription.\n\n"
            f"{LINE}\n💬 More questions? Tap «💬 Support»."
        )
    return (
        "❓ <b>FAQ — частые вопросы</b>\n" + LINE + "\n"
        "<b>Что такое VPN и зачем он нужен?</b>\n"
        "Это зашифрованный туннель между тобой и интернетом. Он скрывает твой реальный IP, "
        "обходит блокировки и защищает трафик в публичных Wi-Fi.\n\n"
        "<b>Какая скорость?</b>\n"
        "До 250 Мбит/с в зависимости от тарифа — хватает на 4K, звонки и игры.\n\n"
        "<b>Сколько устройств можно подключить?</b>\n"
        "Один конфиг = одно устройство. Выбери вариант на 2 устройства или купи несколько конфигов.\n\n"
        "<b>Вы храните логи?</b>\n"
        "Нет. Строгая политика no-logs — мы не храним информацию о твоей активности.\n\n"
        "<b>Что делать, если сервер тормозит или не подключается?</b>\n"
        "Смени локацию и переподключи туннель. Не помогло — напиши в поддержку.\n\n"
        "<b>Как оплатить?</b>\n"
        "Картой, через СБП или криптой. Можно пополнить баланс и оплачивать любые тарифы в один тап.\n\n"
        "<b>Можно ли вернуть деньги?</b>\n"
        "Если сервер по предзаказу не успел подготовиться вовремя — сумма автоматически "
        "возвращается на баланс. В остальных случаях — пиши в поддержку.\n\n"
        "<b>Как работает автопродление?</b>\n"
        "Включи его в разделе «📁 Мои подключения». За день до окончания мы автоматически "
        "спишем сумму с баланса и продлим подписку.\n\n"
        f"{LINE}\n💬 Остались вопросы? Жми «💬 Поддержка»."
    )


_GUIDES_RU = {
    "windows": ("💻 <b>WireGuard · Windows</b>\n" + LINE + "\n"
        "1️⃣ Скачай WireGuard: <a href=\"https://www.wireguard.com/install/\">wireguard.com/install</a>\n"
        "2️⃣ Открой → <b>«Импортировать туннели из файла»</b>\n"
        "3️⃣ Выбери мой файл <code>.conf</code>\n4️⃣ Нажми <b>«Подключить»</b>\n\n"
        "✅ Значок стал зелёным — VPN работает!"),
    "macos": ("💻 <b>WireGuard · macOS</b>\n" + LINE + "\n"
        "1️⃣ Установи WireGuard из <b>App Store</b>\n"
        "2️⃣ Меню сверху → <b>«Import tunnel(s) from file»</b>\n"
        "3️⃣ Выбери мой <code>.conf</code>\n4️⃣ Нажми <b>«Activate»</b>\n\n✅ Готово!"),
    "android": ("📱 <b>WireGuard · Android</b>\n" + LINE + "\n"
        "1️⃣ Установи WireGuard из <b>Google Play</b>\n2️⃣ Нажми <b>«+»</b> внизу\n"
        "3️⃣ <b>«Сканировать QR-код»</b> (наведи на мой QR) или <b>«Импорт из файла»</b>\n"
        "4️⃣ Включи переключатель\n\n✅ Готово!"),
    "iphone": ("🍏 <b>WireGuard · iPhone / iPad</b>\n" + LINE + "\n"
        "1️⃣ Установи WireGuard из <b>App Store</b>\n2️⃣ Нажми <b>«+»</b> вверху справа\n"
        "3️⃣ <b>«Создать из QR-кода»</b> (наведи на мой QR) или <b>«Создать из файла»</b>\n"
        "4️⃣ Разреши VPN и включи туннель\n\n✅ Готово!"),
}

_GUIDES_EN = {
    "windows": ("💻 <b>WireGuard · Windows</b>\n" + LINE + "\n"
        "1️⃣ Download WireGuard: <a href=\"https://www.wireguard.com/install/\">wireguard.com/install</a>\n"
        "2️⃣ Open → <b>«Import tunnel(s) from file»</b>\n"
        "3️⃣ Select my <code>.conf</code> file\n4️⃣ Click <b>«Activate»</b>\n\n"
        "✅ Icon turned green — VPN is on!"),
    "macos": ("💻 <b>WireGuard · macOS</b>\n" + LINE + "\n"
        "1️⃣ Install WireGuard from the <b>App Store</b>\n"
        "2️⃣ Top menu → <b>«Import tunnel(s) from file»</b>\n"
        "3️⃣ Select my <code>.conf</code>\n4️⃣ Click <b>«Activate»</b>\n\n✅ Done!"),
    "android": ("📱 <b>WireGuard · Android</b>\n" + LINE + "\n"
        "1️⃣ Install WireGuard from <b>Google Play</b>\n2️⃣ Tap <b>«+»</b> at the bottom\n"
        "3️⃣ <b>«Scan from QR code»</b> (point at my QR) or <b>«Import from file»</b>\n"
        "4️⃣ Toggle it on\n\n✅ Done!"),
    "iphone": ("🍏 <b>WireGuard · iPhone / iPad</b>\n" + LINE + "\n"
        "1️⃣ Install WireGuard from the <b>App Store</b>\n2️⃣ Tap <b>«+»</b> top right\n"
        "3️⃣ <b>«Create from QR code»</b> (point at my QR) or <b>«Create from file»</b>\n"
        "4️⃣ Allow VPN and turn the tunnel on\n\n✅ Done!"),
}


def guide(platform, lang="ru"):
    table = _GUIDES_EN if _is_en(lang) else _GUIDES_RU
    return table.get(platform, "Not found." if _is_en(lang) else "Инструкция не найдена.")


def delivery_caption(region_flag, region, expires_str, idx, total, lang="ru"):
    if _is_en(lang):
        head = "🔐 <b>Your secure tunnel is ready</b>"
        if total > 1:
            head = f"🔐 <b>Secure tunnel {idx}/{total} ready</b>"
        return (f"{head}\n{LINE}\n{region_flag} Location: <b>{region}</b>\n"
                f"⏳ Valid until: <code>{expires_str}</code>\n{LINE}\n"
                "Import the <code>.conf</code> into WireGuard or scan the QR 👇")
    head = "🔐 <b>Защищённый туннель готов</b>"
    if total > 1:
        head = f"🔐 <b>Защищённый туннель {idx}/{total} готов</b>"
    return (f"{head}\n{LINE}\n{region_flag} Локация: <b>{region}</b>\n"
            f"⏳ Действует до: <code>{expires_str}</code>\n{LINE}\n"
            "Импортируй <code>.conf</code> в WireGuard или отсканируй QR 👇")


# ---- админские уведомления (на русском, это владельцу) ----
def admin_stock_alert(region, kind, free):
    if kind == "empty":
        return (f"🔴 <b>Серверы закончились!</b>\n\nРегион <b>{region}</b>: 0 свободных.\n"
                f"Загрузи: <code>/add_config {region}</code>")
    return (f"🟡 <b>Мало серверов</b>\n\nРегион <b>{region}</b>: осталось <b>{free}</b> шт.\n"
            f"Пополни: <code>/add_config {region}</code>")


def balance_screen(bal_rub, lang="ru", usd_rate=None):
    bal = money(bal_rub, lang, usd_rate)
    if _is_en(lang):
        return (f"💰 <b>Your balance: {bal}</b>\n{LINE}\n"
                "Top up your balance and pay for any plan from it.\n"
                "Have a promo code? Tap «🎟 Promo code».")
    return (f"💰 <b>Твой баланс: {bal}</b>\n{LINE}\n"
            "Пополни баланс и оплачивай с него любые тарифы.\n"
            "Есть промокод? Жми «🎟 Промокод».")


def topup_intro(lang="ru"):
    if _is_en(lang):
        return (f"➕ <b>Top up balance</b>\n{LINE}\nChoose an amount:{topup_bonus_hint(lang)}")
    return (f"➕ <b>Пополнение баланса</b>\n{LINE}\nВыбери сумму:{topup_bonus_hint(lang)}")


def topup_bonus_hint(lang="ru"):
    from config import TOPUP_BONUS_TIERS
    if not TOPUP_BONUS_TIERS:
        return ""
    tiers = sorted(TOPUP_BONUS_TIERS)
    if _is_en(lang):
        parts = " · ".join(f"from {t}₽ +{p}%" for t, p in tiers)
        return f"\n\n🎁 Top-up bonus: {parts}"
    parts = " · ".join(f"от {t}₽ +{p}%" for t, p in tiers)
    return f"\n\n🎁 Бонус за пополнение: {parts}"


def topup_bonus_note(bonus_str, pct, lang="ru"):
    if _is_en(lang):
        return f"🎁 Bonus +{pct}%: <b>{bonus_str}</b> added to your balance!"
    return f"🎁 Бонус +{pct}%: на баланс начислено <b>{bonus_str}</b>!"


def topup_custom_ask(lang="ru"):
    if _is_en(lang):
        return "✏️ Send the amount in ₽ (e.g. 250). Min 50 ₽. /cancel to cancel."
    return "✏️ Пришли сумму в рублях (например 250). Минимум 50 ₽. /cancel — отмена."


def need_topup(to_pay_str, bal_str, lang="ru"):
    if _is_en(lang):
        return (f"😔 <b>Not enough balance</b>\n{LINE}\n"
                f"Price: <b>{to_pay_str}</b>\nYour balance: <b>{bal_str}</b>\n\n"
                "Top up your balance and try again 👇")
    return (f"😔 <b>Недостаточно средств на балансе</b>\n{LINE}\n"
            f"Стоимость: <b>{to_pay_str}</b>\nТвой баланс: <b>{bal_str}</b>\n\n"
            "Пополни баланс и попробуй снова 👇")


def topup_hold(to_pay_str, bal_str, ttl_min, lang="ru"):
    """Нехватка баланса, НО сервер забронирован за пользователем."""
    if _is_en(lang):
        return (f"🔒 <b>Server reserved for you</b>\n{LINE}\n"
                f"💳 To pay: <b>{to_pay_str}</b>\n💰 Your balance: <b>{bal_str}</b>\n\n"
                f"We're holding your server for <b>{ttl_min} min</b>. "
                "Top up below — then tap <b>«✅ Complete order»</b> and it's yours. 🎯")
    return (f"🔒 <b>Сервер забронирован за тобой</b>\n{LINE}\n"
            f"💳 К оплате: <b>{to_pay_str}</b>\n💰 Твой баланс: <b>{bal_str}</b>\n\n"
            f"Держим сервер за тобой <b>{ttl_min} мин</b>. "
            "Пополни ниже — затем жми <b>«✅ Завершить заказ»</b>, и он твой. 🎯")


def topup_paid(amount_str, bal_str, lang="ru"):
    if _is_en(lang):
        return (f"✅ <b>Balance topped up by {amount_str}!</b>\n"
                f"Current balance: <b>{bal_str}</b>")
    return (f"✅ <b>Баланс пополнен на {amount_str}!</b>\n"
            f"Текущий баланс: <b>{bal_str}</b>")


def promo_balance_added(amount_str, bal_str, lang="ru"):
    if _is_en(lang):
        return (f"🎁 <b>Promo applied!</b> +{amount_str} to your balance.\n"
                f"Current balance: <b>{bal_str}</b>")
    return (f"🎁 <b>Промокод применён!</b> +{amount_str} на баланс.\n"
            f"Текущий баланс: <b>{bal_str}</b>")


def preorder_offer(region, amount_str, minutes, lang="ru"):
    if _is_en(lang):
        return (f"😟 <b>No servers in {region} right now</b>\n{LINE}\n"
                f"We'll prepare your config within ~{minutes} minutes after payment.\n\n"
                f"Charge <b>{amount_str}</b> from your balance and place a pre-order?")
    return (f"😟 <b>Серверов в регионе {region} сейчас нет</b>\n{LINE}\n"
            f"Мы подготовим рабочий конфиг в течение ~{minutes} минут после оплаты — "
            f"переподключаться и что-то перенастраивать не нужно, всё заработает сразу.\n\n"
            f"Списать <b>{amount_str}</b> с баланса и оформить предзаказ?")


def preorder_created(minutes, lang="ru"):
    if _is_en(lang):
        return (f"✅ <b>Pre-order placed!</b>\n{LINE}\n"
                f"Your config will arrive within ~{minutes} minutes. Please wait 🙏")
    return (f"✅ <b>Предзаказ оформлен!</b>\n{LINE}\n"
            f"Рабочий конфиг придёт в течение ~{minutes} минут — переподключаться не нужно. "
            f"Немного подожди 🙏")


def preorder_refunded(amount_str, lang="ru"):
    if _is_en(lang):
        return (f"😔 <b>Sorry — we couldn't prepare the server in time.</b>\n"
                f"We've refunded <b>{amount_str}</b> back to your balance.")
    return (f"😔 <b>Извини — мы не успели подготовить сервер вовремя.</b>\n"
            f"Мы вернули <b>{amount_str}</b> на твой баланс.")


def admin_preorder_alert(region, plan, devices, period, rub, user_id,
                         username=None, full_name=None, balance=None, when=None):
    uname = f"@{username}" if username else "—"
    name = full_name or "—"
    bal = f"{balance} ₽" if balance is not None else "—"
    when_line = f"🕒 Время: {when}\n" if when else ""
    return (f"🛒 <b>НОВЫЙ ПРЕДЗАКАЗ — нужен сервер!</b>\n{LINE}\n"
            f"👤 Клиент: <b>{name}</b> ({uname})\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📍 Регион: <b>{region}</b>\n"
            f"🧾 Тариф: {plan} · {devices} устр · {period}\n"
            f"💵 Оплачено: {rub} ₽\n"
            f"💰 Остаток баланса: {bal}\n"
            f"{when_line}{LINE}\n"
            f"⚡️ Загрузи конфиг в этот регион — бот выдаст его клиенту автоматически.")


def admin_trial_alert(region, user_id, username=None, full_name=None, when=None):
    uname = f"@{username}" if username else "—"
    name = full_name or "—"
    when_line = f"🕒 Время: {when}\n" if when else ""
    return (f"🎁 <b>Активирован пробный период</b>\n{LINE}\n"
            f"👤 Клиент: <b>{name}</b> ({uname})\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📍 Регион: <b>{region}</b>\n"
            f"{when_line}")


def admin_preorder_delivered(region, user_id, username=None, full_name=None):
    uname = f"@{username}" if username else "—"
    name = full_name or "—"
    return (f"✅ <b>Предзаказ выдан клиенту</b>\n{LINE}\n"
            f"👤 Клиент: <b>{name}</b> ({uname})\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📍 Регион: <b>{region}</b>")


# ============ ЛОЯЛЬНОСТЬ / АВТОПРОДЛЕНИЕ / ПОДАРКИ ============

def loyalty_line(percent, lang="ru"):
    if percent <= 0:
        return ""
    if _is_en(lang):
        return f"⭐️ Loyalty discount applied: <b>−{percent}%</b>\n"
    return f"⭐️ Скидка лояльности применена: <b>−{percent}%</b>\n"


def footer_links(lang="ru"):
    """Строка ссылок как у 1REG: Правила | Саппорт | Новости (HTML-ссылки)."""
    en = _is_en(lang)
    support = (SUPPORT_URL.strip()
               or f"https://t.me/{SUPPORT_USERNAME.lstrip('@')}")
    parts = []
    rt = "Terms of use" if en else "Правила пользования"
    if RULES_URL.strip():
        parts.append(f'<a href="{RULES_URL.strip()}">{rt}</a>')
    else:
        parts.append(rt)  # ссылка не задана — просто текст
    parts.append(f'<a href="{support}">{"Support" if en else "Саппорт"}</a>')
    if NEWS_CHANNEL_URL.strip():
        parts.append(f'<a href="{NEWS_CHANNEL_URL.strip()}">{"News" if en else "Новости"}</a>')
    return " | ".join(parts)


def profile(u, percent, next_tier, lang="ru", usd_rate=None):
    """u — dict из db.user_card (с полями spent, invited, subs); percent — текущая скидка."""
    spent = money(u.get("spent", 0), lang, usd_rate)
    bal = money(u.get("balance_rub", 0), lang, usd_rate)
    autopay = u.get("autopay")
    subs = u.get("subs", [])
    active_subs = [s for s in subs if s["status"] == "sold"]
    active = len(active_subs)
    bought = len(subs)
    uid = u.get("user_id", "—")
    # строка статуса подписки
    if active_subs:
        s0 = active_subs[0]
        exp = (s0.get("expires_at") or "")[:10]
        sub_ru = f"Активна · {region_name(s0['region'], lang)} (до {exp})"
        sub_en = f"Active · {region_name(s0['region'], lang)} (until {exp})"
    else:
        sub_ru, sub_en = "Нет", "No"
    if _is_en(lang):
        lines = [
            f"👤 <b>{BRAND} · PROFILE</b>", LINE,
            f"┣ <b>ID:</b> <code>{uid}</code>",
            f"┣ <b>Subscription:</b> {sub_en}",
            f"┣ <b>Subscriptions bought:</b> {bought}",
            f"┣ <b>Active now:</b> {active}",
            f"┣ <b>Balance:</b> {bal}",
            f"┗ <b>Loyalty discount:</b> {percent}%",
        ]
        if next_tier:
            need = money(next_tier[0] - u.get("spent", 0), lang, usd_rate)
            lines.append(f"   ↑ {need} more to reach <b>{next_tier[1]}%</b>")
        lines += [
            LINE,
            f"💳 Total spent: <b>{spent}</b> · 👥 invited: <b>{u.get('invited', 0)}</b>",
            f"🔁 Auto-renew: <b>{'on ✅' if autopay else 'off'}</b>",
            LINE,
            footer_links(lang),
        ]
        return "\n".join(lines)
    lines = [
        f"👤 <b>{BRAND} · ПРОФИЛЬ</b>", LINE,
        f"┣ <b>ID:</b> <code>{uid}</code>",
        f"┣ <b>Подписка:</b> {sub_ru}",
        f"┣ <b>Подписок куплено:</b> {bought}",
        f"┣ <b>Активны сейчас:</b> {active}",
        f"┣ <b>Баланс:</b> {bal}",
        f"┗ <b>Скидка лояльности:</b> {percent}%",
    ]
    if next_tier:
        need = money(next_tier[0] - u.get("spent", 0), lang, usd_rate)
        lines.append(f"   ↑ ещё {need} до уровня <b>{next_tier[1]}%</b>")
    lines += [
        LINE,
        f"💳 Всего потрачено: <b>{spent}</b> · 👥 приглашено: <b>{u.get('invited', 0)}</b>",
        f"🔁 Автопродление: <b>{'включено ✅' if autopay else 'выключено'}</b>",
        LINE,
        footer_links(lang),
    ]
    return "\n".join(lines)


def prime_card(price, devices, period, lang="ru", usd_rate=None):
    price_str = money(price, lang, usd_rate)
    months = 12 if period == "year" else 1
    per_month = money(round(price / months), lang, usd_rate)
    per_dev = money(round(price / months / max(devices, 1)), lang, usd_rate)
    period_word = ("год" if period == "year" else "месяц") if not _is_en(lang) else (
        "year" if period == "year" else "month")
    if _is_en(lang):
        return (
            "👑 <b>PRIME — everything included</b>\n" + LINE + "\n"
            f"🚀 <b>{devices} devices</b> · <b>1 {period_word}</b> · top <b>Ultimate</b> plan\n"
            f"💸 Just <b>{per_month}/mo</b> for all — about <b>{per_dev}/mo per device</b>\n\n"
            "What's inside:\n"
            "⭐️ Premium servers in every country\n"
            "🛡 Ad blocking + double encryption\n"
            "⚡️ Max speed & priority (up to 250 Mbps)\n"
            "🔑 {n} separate configs — phone, laptop, TV, family\n\n".format(n=devices) +
            f"💵 Total: <b>{price_str}</b> / {period_word}\n{LINE}\n"
            f"After payment you get <b>{devices} devices</b> — activate each whenever you like in "
            "«My connections», picking a country per device. No need to choose servers now 👇"
        )
    return (
        "👑 <b>PRIME — всё включено</b>\n" + LINE + "\n"
        f"🚀 <b>{devices} устройств</b> · <b>1 {period_word}</b> · максимальный тариф <b>Ultimate</b>\n"
        f"💸 Всего <b>{per_month}/мес</b> за все — это ~<b>{per_dev}/мес</b> на устройство\n\n"
        "Что входит:\n"
        "⭐️ Premium-серверы в каждой стране\n"
        "🛡 Блокировка рекламы + двойное шифрование\n"
        "⚡️ Максимальная скорость и приоритет (до 250 Мбит/с)\n"
        "🔑 {n} отдельных конфигов — телефон, ноут, ТВ, семья\n\n".format(n=devices) +
        f"💵 Итого: <b>{price_str}</b> / {period_word}\n{LINE}\n"
        f"После оплаты получишь <b>{devices} устройств</b> — активируешь каждое когда захочешь "
        "в «Мои подключения», выбирая страну отдельно. Сразу выбирать серверы не нужно 👇"
    )


def rules(lang="ru"):
    if _is_en(lang):
        return (
            "📄 <b>Terms of use</b>\n" + LINE + "\n"
            "• The service is provided for lawful personal use only.\n"
            "• One config = the number of devices in your plan. Don't share configs publicly.\n"
            "• No refunds for already delivered configs, except by our discretion in support.\n"
            "• We don't log your traffic; abuse (spam, attacks, illegal activity) leads to a ban.\n"
            "• Prices and regions may change; active subscriptions keep their terms.\n\n"
            f"Questions? {SUPPORT_USERNAME}"
        )
    return (
        "📄 <b>Правила пользования</b>\n" + LINE + "\n"
        "• Сервис предоставляется только для законного личного использования.\n"
        "• Один конфиг = число устройств в твоём тарифе. Не выкладывай конфиги публично.\n"
        "• Возврат за уже выданные конфиги — только по решению поддержки.\n"
        "• Мы не логируем трафик; за злоупотребления (спам, атаки, незаконные действия) — бан.\n"
        "• Цены и регионы могут меняться; активные подписки сохраняют свои условия.\n\n"
        f"Вопросы? {SUPPORT_USERNAME}"
    )


def support_ticket_ask(lang="ru"):
    if _is_en(lang):
        return ("✍️ <b>Write to support</b>\n"
                "Describe your issue in one message — we'll forward it to our team and reply here.\n"
                "/cancel — cancel.")
    return ("✍️ <b>Обращение в поддержку</b>\n"
            "Опиши проблему одним сообщением — мы передадим её команде и ответим тебе здесь.\n"
            "/cancel — отмена.")


def support_ticket_sent(lang="ru"):
    if _is_en(lang):
        return "✅ Your message was sent to support. We'll reply here as soon as possible."
    return "✅ Обращение отправлено в поддержку. Ответим здесь в ближайшее время."


def admin_ticket(user_id, text, username=None, full_name=None):
    uname = f"@{username}" if username else "—"
    name = full_name or "—"
    return (f"🆘 <b>ОБРАЩЕНИЕ В ПОДДЕРЖКУ</b>\n{LINE}\n"
            f"👤 {name} ({uname})\n🆔 <code>{user_id}</code>\n{LINE}\n{text}")


def autopay_on(lang="ru"):
    if _is_en(lang):
        return ("🔁 <b>Auto-renew enabled</b>\n" + LINE + "\n"
                "A day before your subscription expires we'll charge your balance "
                "automatically and extend it. Keep enough balance to avoid interruptions.")
    return ("🔁 <b>Автопродление включено</b>\n" + LINE + "\n"
            "За день до окончания подписки мы автоматически спишем сумму с баланса и продлим её. "
            "Держи баланс пополненным, чтобы не было перерывов.")


def autopay_off(lang="ru"):
    if _is_en(lang):
        return "🔁 Auto-renew disabled. You'll renew manually."
    return "🔁 Автопродление выключено. Продлевать будешь вручную."


def autorenew_done(region, amount_str, until, lang="ru"):
    if _is_en(lang):
        return (f"🔁 <b>Auto-renewed!</b>\n"
                f"Subscription <b>{region}</b> extended.\n"
                f"💳 Charged: <b>{amount_str}</b>\n⏳ Until: <code>{until}</code>")
    return (f"🔁 <b>Подписка автопродлена!</b>\n"
            f"Подписка <b>{region}</b> продлена.\n"
            f"💳 Списано: <b>{amount_str}</b>\n⏳ До: <code>{until}</code>")


def autorenew_failed(region, amount_str, lang="ru"):
    if _is_en(lang):
        return (f"⚠️ <b>Auto-renew failed</b>\nNot enough balance to renew <b>{region}</b> "
                f"(<b>{amount_str}</b> needed). Top up and renew manually 👇")
    return (f"⚠️ <b>Не удалось автопродлить</b>\nНа балансе не хватило средств для продления "
            f"<b>{region}</b> (нужно <b>{amount_str}</b>). Пополни баланс и продли вручную 👇")


def gift_intro(lang="ru"):
    if _is_en(lang):
        return ("🎁 <b>Gift a balance code</b>\n" + LINE + "\n"
                "Pick an amount — we'll charge your balance and generate a one-time code. "
                "Send it to a friend; they activate it on «💰 Balance → 🎟 Promo code».")
    return ("🎁 <b>Подарить баланс</b>\n" + LINE + "\n"
            "Выбери сумму — мы спишем её с твоего баланса и выдадим одноразовый код. "
            "Передай его другу: он активирует код в «💰 Баланс → 🎟 Промокод».")


def gift_created(code, amount_str, bal_str, lang="ru"):
    if _is_en(lang):
        return (f"🎁 <b>Gift code created!</b>\n" + LINE + "\n"
                f"Amount: <b>{amount_str}</b>\nCode: <code>{code}</code>\n\n"
                f"Send this code to a friend.\n💰 Your balance: <b>{bal_str}</b>")
    return (f"🎁 <b>Подарочный код создан!</b>\n" + LINE + "\n"
            f"Сумма: <b>{amount_str}</b>\nКод: <code>{code}</code>\n\n"
            f"Передай этот код другу.\n💰 Твой баланс: <b>{bal_str}</b>")


def promo_already_used(lang="ru"):
    if _is_en(lang):
        return "❌ You've already used this code."
    return "❌ Ты уже активировал этот код."


# ============ КАПЧА / БОНУС ЗА КАНАЛ / НАПОМИНАНИЕ О ТРИАЛЕ ============

def captcha_q(target_emoji, lang="ru"):
    return (f"🤖 <b>Проверка, что ты не бот</b>\n\n"
            f"Нажми кнопку с эмодзи {target_emoji}, чтобы продолжить.")


def captcha_wrong(lang="ru"):
    return "❌ Не то. Попробуй ещё раз 👇"


def chanbonus_need_sub(days, channel_title, lang="ru"):
    if _is_en(lang):
        return (f"🎁 <b>+{days} days for a subscription</b>\n{LINE}\n"
                f"Subscribe to our news channel and get <b>+{days} days</b> added to your "
                f"active subscription.\n\n1) Tap «Subscribe»\n2) Then «I subscribed ✅»")
    return (f"🎁 <b>+{days} дня за подписку</b>\n{LINE}\n"
            f"Подпишись на наш новостной канал и получи <b>+{days} дня</b> к своей "
            f"активной подписке.\n\n1) Нажми «Подписаться»\n2) Затем «Я подписался ✅»")


def chanbonus_ok(days, region_ru, lang="ru"):
    if _is_en(lang):
        return f"✅ Done! <b>+{days} days</b> added to your subscription ({region_ru})."
    return f"✅ Готово! <b>+{days} дня</b> добавлено к подписке ({region_ru})."


def chanbonus_already(lang="ru"):
    if _is_en(lang):
        return "🎁 You've already claimed this bonus."
    return "🎁 Этот бонус ты уже получал."


def chanbonus_no_active(lang="ru"):
    if _is_en(lang):
        return ("⚠️ The bonus adds days to an <b>active</b> subscription, but you don't have one yet.\n"
                "Buy a subscription first, then claim the bonus 👇")
    return ("⚠️ Бонус добавляет дни к <b>активной</b> подписке, а её сейчас нет.\n"
            "Сначала оформи подписку, потом забери бонус 👇")


def chanbonus_not_subscribed(lang="ru"):
    if _is_en(lang):
        return "❌ I don't see your subscription yet. Subscribe and tap «I subscribed ✅»."
    return "❌ Подписку пока не вижу. Подпишись и нажми «Я подписался ✅»."


def trial_reminder_msg(code, percent, days, lang="ru"):
    if _is_en(lang):
        return (f"👋 How was the free trial?\n\n"
                f"Here's a personal <b>−{percent}%</b> on your first subscription.\n"
                f"Promo code: <code>{code}</code> (valid {days} days, one use).\n\n"
                f"Tap «Buy subscription» and enter it at checkout 👇")
    return (f"👋 Как тебе бесплатный пробный период?\n\n"
            f"Держи личную скидку <b>−{percent}%</b> на первую подписку.\n"
            f"Промокод: <code>{code}</code> (действует {days} дня, на одно применение).\n\n"
            f"Нажми «Купить подписку» и введи его при оплате 👇")


def admin_digest(s: dict):
    return ("📊 <b>Дайджест за сутки</b>\n" + LINE + "\n"
            f"🆕 Новые пользователи: <b>{s['new_users']}</b>\n"
            f"🎁 Активаций триала: <b>{s['trials']}</b>\n"
            f"💳 Платежей: <b>{s['sales_cnt']}</b> · выручка ≈ <b>{s['revenue']} ₽</b>\n"
            f"📨 Предзаказов в ожидании: <b>{s['pending_po']}</b>\n"
            f"📦 Свободных конфигов: <b>{s['free_left']}</b> · регионов с низким запасом: "
            f"<b>{s['low_stock']}</b>")


# ============ СЛОТ-ПОДПИСКА (многоустройственные тарифы) ============

def sub_order_summary(plan_key, devices, period, full_rub, discount, lang="ru", usd_rate=None):
    p = PLANS[plan_key]
    m_full = money(full_rub, lang, usd_rate)
    to_pay = full_rub - discount
    m_pay = money(to_pay, lang, usd_rate)
    if _is_en(lang):
        lines = ["🧾 <b>Order — multi-device plan</b>", LINE,
                 f"{p['emoji']} Plan: <b>{p['title']}</b>",
                 f"📱 Devices: <b>{devices}</b>",
                 f"📅 Period: <b>{per_title(period, lang)}</b>",
                 f"💰 Price: <b>{m_full}</b>"]
        if discount > 0:
            lines.append(f"🎁 Discount: <b>−{money(discount, lang, usd_rate)}</b>")
            lines.append(f"💳 To pay: <b>{m_pay}</b>")
        lines += [LINE,
                  f"After payment you get <b>{devices} device slots</b>. Activate each one when "
                  "you want in «My connections» — choose a country per device.",
                  "Pay from balance below 👇"]
        return "\n".join(lines)
    lines = ["🧾 <b>Заказ — тариф на несколько устройств</b>", LINE,
             f"{p['emoji']} Тариф: <b>{p['title']}</b>",
             f"📱 Устройств: <b>{devices}</b>",
             f"📅 Период: <b>{per_title(period, lang)}</b>",
             f"💰 Стоимость: <b>{m_full}</b>"]
    if discount > 0:
        lines.append(f"🎁 Скидка: <b>−{money(discount, lang, usd_rate)}</b>")
        lines.append(f"💳 К оплате: <b>{m_pay}</b>")
    lines += [LINE,
              f"После оплаты получишь <b>{devices} слота под устройства</b>. Каждое активируешь "
              "когда захочешь в «Мои подключения» — выберешь страну отдельно для каждого.",
              "Оплата с баланса ниже 👇"]
    return "\n".join(lines)


def sub_created(devices, lang="ru"):
    if _is_en(lang):
        return (f"✅ <b>Subscription is active!</b>\n\nYou have <b>{devices} device slots</b>.\n"
                "Open «My connections» and tap «➕ Activate a device» — pick a country for each "
                "device, one by one, whenever you like.")
    return (f"✅ <b>Подписка активна!</b>\n\nУ тебя <b>{devices} слота под устройства</b>.\n"
            "Зайди в «Мои подключения» и нажми «➕ Активировать устройство» — выбери страну для "
            "каждого устройства по одному, когда удобно.")


def sub_slot_block(s, lang="ru"):
    exp = (s.get("expires_at") or "")[:10]
    title = PLANS.get(s["plan"], {}).get("title", s["plan"])
    if _is_en(lang):
        return (f"👑 <b>{title}</b> · plan for {s['devices']} devices\n"
                f"🔌 Activated: <b>{s['activated']}/{s['devices']}</b> · ⏳ until <code>{exp}</code>\n"
                f"Free slots: <b>{s['free_slots']}</b>")
    return (f"👑 <b>{title}</b> · тариф на {s['devices']} устройств\n"
            f"🔌 Активировано: <b>{s['activated']}/{s['devices']}</b> · ⏳ до <code>{exp}</code>\n"
            f"Свободных слотов: <b>{s['free_slots']}</b>")


def sub_activate_pick(s, lang="ru"):
    nxt = s["activated"] + 1
    if _is_en(lang):
        return (f"🔌 <b>Activating device {nxt}/{s['devices']}</b>\n"
                "Choose a country for this device 👇")
    return (f"🔌 <b>Активация устройства {nxt}/{s['devices']}</b>\n"
            "Выбери страну для этого устройства 👇")


def sub_activated(region_disp, lang="ru"):
    if _is_en(lang):
        return f"✅ Device activated in {region_disp}! Here's its config 👇"
    return f"✅ Устройство активировано — {region_disp}! Вот его конфиг 👇"


# ============ СМЕНА РЕГИОНА (через одобрение админа) ============

def region_change_requested(lang="ru"):
    if _is_en(lang):
        return ("🔁 <b>Region change requested!</b>\n\n"
                "We'll switch you to the <b>fastest server</b> within ~5 minutes — a new config "
                "will arrive here automatically. The old one will stop working after that.")
    return ("🔁 <b>Запрос на смену региона принят!</b>\n\n"
            "В течение <b>~5 минут</b> заменим тебя на <b>самый быстрый сервер</b> — новый конфиг "
            "придёт сюда автоматически. Старый после этого перестанет работать.")


def admin_region_change(user_id, config_id, region, username=None, full_name=None):
    who = f"@{username}" if username else (full_name or "—")
    return ("🔁 <b>ЗАПРОС СМЕНЫ РЕГИОНА</b>\n" + LINE + "\n"
            f"👤 Клиент: {who}\n"
            f"🆔 ID: <code>{user_id}</code>\n"
            f"📍 Текущий регион: <b>{region}</b>\n"
            f"🧩 Конфиг #{config_id}\n" + LINE + "\n"
            "При одобрении бот сам выберет <b>самый быстрый</b> (с наибольшим запасом) регион "
            "и выдаст клиенту новый конфиг.")


def region_change_done(region_disp, lang="ru"):
    if _is_en(lang):
        return f"✅ Your region was switched to <b>{region_disp}</b>. Here's the new config 👇"
    return f"✅ Регион изменён на <b>{region_disp}</b>. Вот новый конфиг 👇"


def region_change_rejected(lang="ru"):
    if _is_en(lang):
        return ("❌ Your region change request was declined. Your current config keeps working. "
                "Contact support if you have questions.")
    return ("❌ Запрос на смену региона отклонён. Текущий конфиг продолжает работать. "
            "Если есть вопросы — напиши в поддержку.")
