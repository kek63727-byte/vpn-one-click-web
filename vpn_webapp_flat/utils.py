import json
import re


def is_valid_wg(text: str) -> bool:
    """Проверяет, что строка — валидный WireGuard конфиг."""
    if not text:
        return False
    text_lower = text.lower()
    return "[interface]" in text_lower and "[peer]" in text_lower


def is_valid_vless(text: str) -> bool:
    """
    Проверяет, что строка — валидный happ/xray VLESS JSON конфиг.
    Минимальные критерии:
      - валидный JSON
      - есть outbounds с хотя бы одним protocol == 'vless'
      - у каждого vless outbound есть address и id пользователя
    """
    try:
        data = json.loads(text)
    except Exception:
        return False

    outbounds = data.get("outbounds")
    if not isinstance(outbounds, list) or not outbounds:
        return False

    vless_found = False
    for ob in outbounds:
        if ob.get("protocol") != "vless":
            continue
        try:
            vnext = ob["settings"]["vnext"]
            addr = vnext[0]["address"]
            uid = vnext[0]["users"][0]["id"]
            if addr and uid:
                vless_found = True
        except (KeyError, IndexError, TypeError):
            continue

    return vless_found


def vless_region_from_json(text: str) -> str:
    """
    Извлекает название региона из поля 'remarks' VLESS JSON.
    Например: '🇩🇪 Германия | Прямое' → 'Германия'
    Если remarks нет — возвращает 'VLESS'.
    """
    try:
        data = json.loads(text)
        remarks = data.get("remarks", "").strip()
        if not remarks:
            return "VLESS"
        # Убираем лишнее после '|'
        if "|" in remarks:
            remarks = remarks.split("|")[0].strip()
        # Убираем региональные индикаторы (флаги) U+1F1E0–U+1F1FF
        cleaned = "".join(
            c for c in remarks
            if not (0x1F1E0 <= ord(c) <= 0x1F1FF)
        ).strip()
        # Убираем прочие эмодзи U+1F600–U+1FFFF
        cleaned = "".join(
            c for c in cleaned
            if not (0x1F600 <= ord(c) <= 0x1FFFF)
        ).strip()
        return cleaned if cleaned else remarks
    except Exception:
        return "VLESS"


def vless_server_count(text: str) -> int:
    """Сколько VLESS серверов в конфиге (для информации при добавлении)."""
    try:
        data = json.loads(text)
        return sum(
            1 for ob in data.get("outbounds", [])
            if ob.get("protocol") == "vless"
        )
    except Exception:
        return 0


def make_qr_png(text: str) -> bytes:
    """Генерирует QR-код из текста, возвращает PNG bytes."""
    try:
        import qrcode
        import io
        qr = qrcode.make(text)
        buf = io.BytesIO()
        qr.save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        # Если qrcode не установлен — возвращаем пустой PNG (1x1 прозрачный)
        return (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89'
            b'\x00\x00\x00\nIDATx\x9cc\x00\x01\x00\x00\x05\x00\x01'
            b'\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82'
        )


def sub_token(config_id: int) -> str:
    """Короткий HMAC-токен для публичной ссылки на конфиг (для happ-диплинка)."""
    import hmac
    import hashlib
    from config import BOT_TOKEN
    return hmac.new(BOT_TOKEN.encode(), str(config_id).encode(), hashlib.sha256).hexdigest()[:20]


def sub_url(config_id: int) -> str:
    from config import PUBLIC_BASE_URL
    base = PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/sub/{config_id}/{sub_token(config_id)}"


def happ_deeplink(config_id: int) -> str:
    return f"happ://add/{sub_url(config_id)}"

def happ_open_url(config_id: int) -> str:
    """https-ссылка на промежуточную страницу-редирект (см. /happ-open в webapp.py).
    Открывается через tg.openLink() ВО ВНЕШНЕМ браузере — Telegram Mini App
    WebView блокирует custom URL-схемы (happ://) напрямую, а обычный внешний
    браузер (Safari/Chrome) их спокойно обрабатывает."""
    from config import PUBLIC_BASE_URL
    base = PUBLIC_BASE_URL.rstrip("/")
    return f"{base}/happ-open/{config_id}?t={sub_token(config_id)}"
