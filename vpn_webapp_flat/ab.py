"""Простые A/B-эксперименты.

Бакетинг детерминированный по user_id (чётный → A, нечётный → B), поэтому один
пользователь всегда видит один и тот же вариант. Активный эксперимент и его варианты
задаются в config.py (AB_EXPERIMENT / AB_EXPERIMENTS). Анализ — в админке (📊 A/B):
сравниваем конверсию триал→оплата по вариантам.
"""

from config import AB_EXPERIMENT, AB_EXPERIMENTS


def active_experiment() -> str | None:
    """Ключ активного эксперимента или None, если выключено/некорректно."""
    exp = (AB_EXPERIMENT or "").strip()
    return exp if exp in AB_EXPERIMENTS else None


def variant_for(user_id: int) -> str:
    """Стабильный вариант 'A' или 'B' для пользователя."""
    return "A" if int(user_id) % 2 == 0 else "B"


def variant_params(user_id: int) -> dict:
    """Параметры варианта активного эксперимента для пользователя (или {})."""
    exp = active_experiment()
    if not exp:
        return {}
    variant = variant_for(user_id)
    return AB_EXPERIMENTS[exp]["variants"].get(variant, {})


def experiment_title(exp: str | None = None) -> str:
    exp = exp or active_experiment()
    if not exp:
        return "—"
    return AB_EXPERIMENTS[exp].get("title", exp)
