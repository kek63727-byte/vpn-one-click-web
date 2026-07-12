"""
VPN Web App — Flask сервер
Принимает заказы из Telegram Mini App, создаёт платёж Lava Pay,
обрабатывает вебхук и выдаёт VPN конфиг через бота.
"""

import os
import hmac
import hashlib
import json
import uuid
import logging
from datetime import datetime

import requests
from flask import Flask, request, jsonify, send_from_directory
from dotenv import load_dotenv

load_dotenv()

# ── Logging ──
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

app = Flask(__name__, static_folder="static")

# ── Config ──
BOT_TOKEN       = os.getenv("BOT_TOKEN", "")
LAVA_SHOP_ID    = os.getenv("LAVA_SHOP_ID", "")
LAVA_SECRET     = os.getenv("LAVA_SECRET", "")
WEBAPP_URL      = os.getenv("WEBAPP_URL", "https://your-domain.railway.app")
# URL куда бот должен добавить конфиг (или путь к скрипту выдачи)
VPN_ISSUE_URL   = os.getenv("VPN_ISSUE_URL", "")  # опционально

LAVA_API_URL    = "https://api.lava.ru/business/invoice/create"
TELEGRAM_API    = f"https://api.telegram.org/bot{BOT_TOKEN}"

# ── Хранилище ожидающих платежей (в проде замени на Redis/БД) ──
pending_payments: dict[str, dict] = {}

# ── Тарифы ──
PLANS = {
    "1m":  {"days": 30,  "label": "1 месяц",    "price": 149},
    "3m":  {"days": 90,  "label": "3 месяца",   "price": 349},
    "6m":  {"days": 180, "label": "6 месяцев",  "price": 599},
    "12m": {"days": 365, "label": "12 месяцев", "price": 999},
}

# ────────────────────────────────────────────────────────────────
# Статика — отдаём index.html
# ────────────────────────────────────────────────────────────────
@app.route("/")
def index():
    return send_from_directory("static", "index.html")


# ────────────────────────────────────────────────────────────────
# POST /create_payment  ←  Mini App
# ────────────────────────────────────────────────────────────────
@app.route("/create_payment", methods=["POST"])
def create_payment():
    data = request.get_json(silent=True) or {}

    plan_id  = data.get("plan", "3m")
    user_id  = data.get("user_id")
    protocol = data.get("protocol", "wireguard")

    plan = PLANS.get(plan_id)
    if not plan:
        return jsonify({"error": "Неверный тариф"}), 400

    if not user_id:
        return jsonify({"error": "Не удалось определить пользователя"}), 400

    order_id = str(uuid.uuid4())

    # Сохраняем данные заказа
    pending_payments[order_id] = {
        "user_id":  user_id,
        "plan_id":  plan_id,
        "protocol": protocol,
        "days":     plan["days"],
        "label":    plan["label"],
        "price":    plan["price"],
        "created":  datetime.utcnow().isoformat(),
    }

    # ── Создаём инвойс в Lava Pay ──
    payload = {
        "shopId":     LAVA_SHOP_ID,
        "sum":        plan["price"],
        "orderId":    order_id,
        "hookUrl":    f"{WEBAPP_URL}/lava_webhook",
        "successUrl": f"{WEBAPP_URL}/?status=success",
        "failUrl":    f"{WEBAPP_URL}/?status=fail",
        "comment":    f"VPN {plan['label']} | user {user_id}",
        "expire":     30,   # минут
    }

    try:
        sign = _lava_sign(payload)
        resp = requests.post(
            LAVA_API_URL,
            json=payload,
            headers={
                "Signature": sign,
                "Accept":    "application/json",
            },
            timeout=10,
        )
        result = resp.json()
        log.info("Lava response: %s", result)

        payment_url = (
            result.get("data", {}).get("url")
            or result.get("url")
        )
        if not payment_url:
            raise ValueError(result.get("message", "Нет URL в ответе Lava"))

        return jsonify({"payment_url": payment_url, "order_id": order_id})

    except Exception as exc:
        log.error("Lava error: %s", exc)
        return jsonify({"error": str(exc)}), 500


# ────────────────────────────────────────────────────────────────
# POST /lava_webhook  ←  Lava Pay
# ────────────────────────────────────────────────────────────────
@app.route("/lava_webhook", methods=["POST"])
def lava_webhook():
    raw = request.data
    data = request.get_json(silent=True) or {}

    log.info("Lava webhook received: %s", data)

    # Проверяем подпись
    received_sign = request.headers.get("Signature", "")
    if not _verify_lava_sign(data, received_sign):
        log.warning("Invalid Lava signature!")
        return jsonify({"error": "bad signature"}), 403

    status   = data.get("status")        # "success" | "fail" | "pending"
    order_id = data.get("orderId", "")

    if status != "success":
        log.info("Non-success status: %s", status)
        return jsonify({"ok": True})

    order = pending_payments.pop(order_id, None)
    if not order:
        log.warning("Unknown order_id: %s", order_id)
        return jsonify({"ok": True})

    # ── Выдаём VPN ──
    _issue_vpn(
        user_id  = order["user_id"],
        plan_id  = order["plan_id"],
        protocol = order["protocol"],
        days     = order["days"],
        label    = order["label"],
    )

    return jsonify({"ok": True})


# ────────────────────────────────────────────────────────────────
# Вспомогательные функции
# ────────────────────────────────────────────────────────────────
def _lava_sign(payload: dict) -> str:
    """Создаёт HMAC-SHA256 подпись для Lava Pay."""
    body = json.dumps(payload, separators=(",", ":"), ensure_ascii=False)
    return hmac.new(
        LAVA_SECRET.encode(),
        body.encode(),
        hashlib.sha256,
    ).hexdigest()


def _verify_lava_sign(data: dict, received: str) -> bool:
    """Проверяет подпись входящего вебхука от Lava."""
    if not LAVA_SECRET:
        return True  # dev режим без секрета
    expected = _lava_sign(data)
    return hmac.compare_digest(expected, received)


def _issue_vpn(user_id: int, plan_id: str, protocol: str, days: int, label: str):
    """
    Выдаёт VPN конфиг пользователю.

    Варианты:
    1. Если у тебя есть отдельный скрипт выдачи — вызывай его тут.
    2. Если конфиги хранятся в БД — бери следующий свободный и отправляй.
    3. Пример ниже — интеграция с твоим существующим ботом через API.
    """
    log.info("Issuing VPN: user=%s plan=%s proto=%s days=%s", user_id, plan_id, protocol, days)

    # ── Вариант A: Отправляем сообщение напрямую через Bot API ──
    # (Если конфиг генерируется динамически — поставь сюда свою логику)
    msg = (
        f"✅ *Оплата прошла!*\n\n"
        f"📦 Тариф: *{label}*\n"
        f"🔒 Протокол: *{protocol.upper()}*\n\n"
        f"Конфигурация выдаётся автоматически — подожди секунду..."
    )
    _send_telegram(user_id, msg)

    # ── Вариант B: Вызываем внутренний endpoint бота для выдачи конфига ──
    # Твой бот на Railway уже умеет выдавать конфиги — просто дёргаем его API
    if VPN_ISSUE_URL:
        try:
            resp = requests.post(
                VPN_ISSUE_URL,
                json={
                    "user_id":  user_id,
                    "plan_id":  plan_id,
                    "protocol": protocol,
                    "days":     days,
                },
                timeout=10,
            )
            log.info("VPN issue response: %s", resp.text)
        except Exception as exc:
            log.error("VPN issue error: %s", exc)
    else:
        # Если нет отдельного эндпоинта — добавь конфиг прямо сюда
        # или интегрируй с твоей функцией generate_config() из db.py
        log.warning("VPN_ISSUE_URL не задан — настрой выдачу конфига!")
        _send_telegram(
            user_id,
            "⚙️ Конфигурация создаётся... Бот пришлёт её в течение минуты.",
        )


def _send_telegram(chat_id: int, text: str):
    """Отправляет сообщение пользователю через Telegram Bot API."""
    try:
        requests.post(
            f"{TELEGRAM_API}/sendMessage",
            json={
                "chat_id":    chat_id,
                "text":       text,
                "parse_mode": "Markdown",
            },
            timeout=10,
        )
    except Exception as exc:
        log.error("Telegram send error: %s", exc)


# ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.getenv("PORT", 8080))
    app.run(host="0.0.0.0", port=port, debug=False)
