"""Расчёт цен и параметров оплаты: Telegram Stars / ЮKassa / Crypto Pay / LAVA."""

from math import ceil

from aiogram.types import LabeledPrice

from config import (
    CRYPTO_ASSET,
    CRYPTO_PAY_TOKEN,
    CRYPTO_TESTNET,
    CURRENCY,
    LAVA_SECRET_KEY,
    LAVA_SHOP_ID,
    PAYMENT_MODE,
    PLANS,
    PROVIDER_TOKEN,
    RUB_PER_STAR,
    USD_RUB_RATE,
    USDT_RUB_RATE,
)


def price_rub(plan: str, devices: int, period: str) -> int:
    import store
    return store.get_price(plan, devices, period)


def loyalty_percent_for(spent_rub: int) -> int:
    """Накопительная скидка по сумме всех покупок (в ₽)."""
    from config import LOYALTY_TIERS
    pct = 0
    for threshold, percent in LOYALTY_TIERS:
        if spent_rub >= threshold:
            pct = percent
    return pct


def topup_bonus_for(amount_rub: int) -> tuple[int, int]:
    """Бонус за пополнение: возвращает (бонус_₽, процент). Берёт максимальный подходящий тариф."""
    from config import TOPUP_BONUS_TIERS
    pct = 0
    for threshold, percent in sorted(TOPUP_BONUS_TIERS):
        if amount_rub >= threshold:
            pct = percent
    bonus = amount_rub * pct // 100
    return bonus, pct


def to_stars(rub: int) -> int:
    return max(1, ceil(rub / RUB_PER_STAR))


def invoice_params(title: str, description: str, payload: str, rub: int) -> dict:
    """Параметры для bot.send_invoice (Stars / ЮKassa)."""
    if PAYMENT_MODE == "yookassa":
        return dict(
            title=title,
            description=description,
            payload=payload,
            provider_token=PROVIDER_TOKEN,
            currency=CURRENCY,
            prices=[LabeledPrice(label=title, amount=rub * 100)],  # копейки
        )
    stars = to_stars(rub)
    return dict(
        title=title,
        description=f"{description}\n\nК оплате: {stars} ⭐️",
        payload=payload,
        provider_token="",
        currency="XTR",
        prices=[LabeledPrice(label=title, amount=stars)],
    )


# ---------- Crypto Pay (@CryptoBot) ----------

def _crypto_client():
    # ленивый импорт: библиотека нужна только в режиме crypto
    from aiocryptopay import AioCryptoPay, Networks
    network = Networks.TEST_NET if CRYPTO_TESTNET else Networks.MAIN_NET
    return AioCryptoPay(token=CRYPTO_PAY_TOKEN, network=network)


async def get_usdt_rub_rate() -> float:
    """Актуальный курс USDT→RUB с CryptoBot. При ошибке — курс из .env."""
    crypto = _crypto_client()
    try:
        rates = await crypto.get_exchange_rates()
        for r in rates:
            src = getattr(r, "source", None) or getattr(r, "asset", None)
            tgt = getattr(r, "target", None)
            if src == CRYPTO_ASSET and tgt == "RUB":
                rate = float(getattr(r, "rate", 0))
                if rate > 0:
                    return rate
    except Exception:
        pass
    finally:
        await crypto.close()
    return float(USDT_RUB_RATE)


async def get_usd_rub_rate() -> float:
    """Курс USD→RUB. USDT≈USD, берём с CryptoBot; fallback — USD_RUB_RATE из .env."""
    crypto = _crypto_client()
    try:
        rates = await crypto.get_exchange_rates()
        for r in rates:
            src = getattr(r, "source", None) or getattr(r, "asset", None)
            tgt = getattr(r, "target", None)
            if src in ("USDT", "USD") and tgt == "RUB":
                rate = float(getattr(r, "rate", 0))
                if rate > 0:
                    return rate
    except Exception:
        pass
    finally:
        await crypto.close()
    return float(USD_RUB_RATE)


async def price_usd_str(rub: int) -> str:
    """Возвращает строку цены в долларах для отображения, напр. '$4.05'."""
    rate = await get_usd_rub_rate()
    usd = rub / rate if rate else rub / float(USD_RUB_RATE)
    return f"${usd:.2f}"


def price_usd_str_sync(rub: int, rate: float) -> str:
    usd = rub / rate if rate else rub / float(USD_RUB_RATE)
    return f"${usd:.2f}"


async def create_crypto_invoice(order_id: int, rub: int, description: str):
    """Создаёт счёт в Crypto Pay по актуальному курсу. Возвращает (invoice_id, pay_url)."""
    rate = await get_usdt_rub_rate()
    crypto = _crypto_client()
    try:
        amount = round(rub / rate, 2)
        invoice = await crypto.create_invoice(
            asset=CRYPTO_ASSET,
            amount=amount,
            description=description[:1024],
            payload=str(order_id),
        )
    finally:
        await crypto.close()
    pay_url = (
        getattr(invoice, "bot_invoice_url", None)
        or getattr(invoice, "mini_app_invoice_url", None)
        or getattr(invoice, "web_app_invoice_url", None)
        or getattr(invoice, "pay_url", None)
    )
    return invoice.invoice_id, pay_url


async def check_crypto_invoice(invoice_id: int) -> bool:
    """True, если счёт оплачён."""
    crypto = _crypto_client()
    try:
        result = await crypto.get_invoices(invoice_ids=invoice_id)
    finally:
        await crypto.close()
    # разные версии библиотеки возвращают по-разному — нормализуем
    if hasattr(result, "items"):
        items = result.items
    elif isinstance(result, list):
        items = result
    elif result is None:
        items = []
    else:
        items = [result]
    if not items:
        return False
    return getattr(items[0], "status", None) == "paid"


# ---------- LAVA Business (business.lava.ru) ----------

_LAVA_CREATE_URL = "https://api.lava.ru/business/invoice/create"
_LAVA_STATUS_URL = "https://api.lava.ru/business/invoice/status"


def _lava_sign(body: str) -> str:
    import hashlib
    import hmac
    return hmac.new(LAVA_SECRET_KEY.encode(), body.encode(), hashlib.sha256).hexdigest()


async def _lava_post(url: str, body_dict: dict) -> dict:
    import json

    import aiohttp
    # подписываем РОВНО ту строку, которую отправляем
    raw = json.dumps(body_dict, ensure_ascii=False)
    headers = {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Signature": _lava_sign(raw),
    }
    async with aiohttp.ClientSession() as session:
        async with session.post(url, data=raw, headers=headers, timeout=30) as resp:
            return await resp.json(content_type=None)


async def create_lava_invoice(order_id: int, rub: int, comment: str):
    """Создаёт счёт в LAVA Business. Возвращает (invoice_id, pay_url)."""
    body = {
        "sum": float(rub),
        "orderId": str(order_id),
        "shopId": LAVA_SHOP_ID,
        "comment": comment[:255],
        "expire": 60,
    }
    data = await _lava_post(_LAVA_CREATE_URL, body)
    d = data.get("data") or data
    pay_url = d.get("url") or d.get("payUrl")
    invoice_id = d.get("id") or d.get("invoiceId")
    if not pay_url:
        raise RuntimeError(f"LAVA create error: {data}")
    return invoice_id, pay_url


async def check_lava_invoice(order_id: int) -> bool:
    """True, если счёт оплачён (по orderId)."""
    body = {"shopId": LAVA_SHOP_ID, "orderId": str(order_id)}
    data = await _lava_post(_LAVA_STATUS_URL, body)
    d = data.get("data") or data
    status = (d.get("status") or "").lower()
    return status in ("success", "paid", "completed")
