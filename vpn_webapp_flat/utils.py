"""
Добавить в utils.py рядом с is_valid_wg()
"""

import json


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
        # Убираем эмодзи-флаги и лишнее после '|'
        if "|" in remarks:
            remarks = remarks.split("|")[0].strip()
        # Убираем эмодзи (символы вне ASCII + пробелы в начале)
        cleaned = "".join(c for c in remarks if ord(c) < 0x1F600 or ord(c) > 0x1FFFF).strip()
        # Убираем оставшиеся unicode-флаги (regional indicator symbols U+1F1E0–U+1F1FF)
        cleaned = "".join(
            c for c in cleaned
            if not (0x1F1E0 <= ord(c) <= 0x1F1FF)
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
