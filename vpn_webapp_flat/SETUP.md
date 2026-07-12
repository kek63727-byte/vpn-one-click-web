# Деплой VPN Web App на Railway

## Что это за папка

```
vpn_webapp/
├── static/
│   └── index.html      ← Telegram Mini App (красивый UI выбора тарифа)
├── app.py              ← Flask сервер (создание платежа + вебхук Lava)
├── requirements.txt
├── Procfile
├── .env.example
└── SETUP.md            ← ты здесь
```

---

## Шаг 1 — Деплой на Railway

1. Создай **новый проект** на [railway.app](https://railway.app)  
   *(у тебя уже есть аккаунт с ботом — просто добавь новый сервис)*

2. В Railway → **New Service → GitHub Repo**  
   Либо: **New Service → Empty Service → Upload files**

3. Скопируй всю папку `vpn_webapp/` в репо и запушь

4. Railway автоматически обнаружит `Procfile` и запустит gunicorn

5. После деплоя скопируй URL вида:  
   `https://vpn-webapp-xxx.up.railway.app`

---

## Шаг 2 — Переменные окружения

В Railway → Settings → Variables добавь:

```
BOT_TOKEN        = твой токен бота
LAVA_SHOP_ID     = ID магазина из lava.ru
LAVA_SECRET      = секретный ключ из lava.ru
WEBAPP_URL       = https://vpn-webapp-xxx.up.railway.app
```

---

## Шаг 3 — Lava Pay

1. Зайди на [lava.ru](https://lava.ru) → Магазин → Настройки
2. Скопируй **Shop ID** и **Secret Key**
3. В разделе Уведомления укажи Webhook URL:  
   `https://vpn-webapp-xxx.up.railway.app/lava_webhook`

---

## Шаг 4 — BotFather

```
/mybots → выбери бота → Bot Settings → Menu Button → Edit Menu Button URL
```

Вставь: `https://vpn-webapp-xxx.up.railway.app`

Или добавь Web App кнопку в клавиатуру бота:

```python
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo

kb = InlineKeyboardMarkup(inline_keyboard=[[
    InlineKeyboardButton(
        text="💳 Оплатить",
        web_app=WebAppInfo(url="https://vpn-webapp-xxx.up.railway.app")
    )
]])
```

---

## Шаг 5 — Интеграция с твоим ботом (выдача конфига)

В `app.py` функция `_issue_vpn()` уже отправляет сообщение пользователю.  
Тебе нужно добавить логику выдачи конфига. Варианты:

### Вариант A: Импортировать логику из твоего `db.py`

Если `vpn_webapp` находится рядом с ботом — можешь импортировать напрямую:

```python
# в app.py
import sys
sys.path.insert(0, '/path/to/bot')
from db import get_next_free_config, activate_config_for_user
```

### Вариант B: Добавить endpoint в бот

В твоём боте (handlers_admin.py или новый файл):

```python
from aiohttp import web

async def internal_issue_vpn(request):
    data = await request.json()
    user_id  = data['user_id']
    plan_id  = data['plan_id']
    protocol = data['protocol']
    days     = data['days']
    
    # Твоя логика выдачи конфига
    config = await db.get_free_config(protocol)
    await db.activate_config(config.id, user_id, days)
    
    # Отправить конфиг пользователю
    await bot.send_message(user_id, f"Вот твой конфиг:\n```{config.key}```", parse_mode="Markdown")
    
    return web.json_response({"ok": True})

# Зарегистрируй маршрут в своём aiohttp приложении
app.router.add_post('/internal/issue_vpn', internal_issue_vpn)
```

Потом в `.env` webapp'а добавь:
```
VPN_ISSUE_URL = https://твой-бот.up.railway.app/internal/issue_vpn
```

### Вариант C: Вебхук через Telegram

Бот может слушать специальное сообщение от webapp:

```python
# В webapp после успешной оплаты отправляем боту через Bot API
# Бот ловит команду и выдаёт конфиг
```

---

## Изменить тарифы и цены

В `static/index.html` найди блок `<!-- PLANS -->` — правь прямо там.  
В `app.py` найди словарь `PLANS` — синхронизируй цены.

---

## Проверка работы

```bash
# Запустить локально
cd vpn_webapp
pip install -r requirements.txt
cp .env.example .env   # заполни значения
python app.py

# Открыть в браузере
open http://localhost:8080
```

---

## Частые вопросы

**Q: Пользователь оплатил, но конфиг не пришёл?**  
A: Проверь логи Railway → Deployments → Logs. Webhook от Lava мог не дойти — убедись что URL правильный и Railway возвращает 200.

**Q: Нужен ли HTTPS?**  
A: Да, Telegram Web App требует HTTPS. Railway даёт его автоматически.

**Q: Можно ли кастомизировать тарифы?**  
A: Да — меняй `PLANS` в `app.py` и карточки в `index.html`.
