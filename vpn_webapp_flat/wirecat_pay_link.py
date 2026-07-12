from telethon import TelegramClient
import asyncio

API_ID = 907866
API_HASH = "f9719b34968ef3eae3f803ab3e41ea12"

BOT = "@WireCatBot"


async def get_last_bot_message_with_buttons(client, limit=10):
    messages = await client.get_messages(BOT, limit=limit)

    for msg in messages:
        if msg.buttons:
            return msg

    return None


async def click_button_contains(message, text):
    if not message or not message.buttons:
        print(f"Нет кнопок для: {text}")
        return False

    for row in message.buttons:
        for button in row:
            print("Кнопка:", button.text)

            if text.lower() in button.text.lower():
                await message.click(text=button.text)
                print("Нажал:", button.text)
                return True

    print("Не нашел кнопку:", text)
    return False


async def main():
    client = TelegramClient(
        "sessions/account1",
        API_ID,
        API_HASH
    )

    await client.start()

    print("1. Отправляем /start")
    await client.send_message(BOT, "/start")
    await asyncio.sleep(2)

    print("2. Ищем кнопку Отлично")
    msg = await get_last_bot_message_with_buttons(client)
    await click_button_contains(msg, "Отлично")
    await asyncio.sleep(2)

    print("3. Ищем кнопку Главное меню")
    msg = await get_last_bot_message_with_buttons(client)
    await click_button_contains(msg, "Главное меню")
    await asyncio.sleep(2)

    print("4. Ищем кнопку Пополнить баланс")
    msg = await get_last_bot_message_with_buttons(client)
    await click_button_contains(msg, "Пополнить")
    await asyncio.sleep(2)

    print("5. Отправляем сумму 1720")
    await client.send_message(BOT, "1720")
    await asyncio.sleep(2)

    print("6. Ищем кнопку Криптовалюта")
    msg = await get_last_bot_message_with_buttons(client)
    await click_button_contains(msg, "Криптовалюта")
    await asyncio.sleep(3)

    print("7. Ищем ссылку оплаты")
    messages = await client.get_messages(BOT, limit=10)

    payment_link = None

    for msg in messages:
        print("=" * 30)
        print(msg.text)

        if msg.buttons:
            for row in msg.buttons:
                for button in row:
                    print("Кнопка:", button.text)

                    if getattr(button, "url", None):
                        payment_link = button.url

    if payment_link:
        print("\nССЫЛКА НА ОПЛАТУ:")
        print(payment_link)
    else:
        print("\nСсылка не найдена")

    await client.disconnect()


asyncio.run(main())
