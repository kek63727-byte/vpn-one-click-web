"""Генерация QR-кода из текста конфига."""

import io

import qrcode


def make_qr_png(text: str) -> bytes:
    qr = qrcode.QRCode(border=2, box_size=8)
    qr.add_data(text)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def is_valid_wg(text: str) -> bool:
    """Грубая проверка, что это реальный WireGuard-конфиг, а не мусор."""
    if not text:
        return False
    t = text.replace("\r", "")
    low = t.lower()
    if "[interface]" not in low or "[peer]" not in low:
        return False
    # должны быть ключи и эндпоинт
    has_private = "privatekey" in low
    has_public = "publickey" in low
    has_endpoint = "endpoint" in low
    return has_private and has_public and has_endpoint
