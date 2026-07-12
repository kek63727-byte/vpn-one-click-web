from telethon import TelegramClient
import asyncio

API_ID = 907866
API_HASH = "f9719b34968ef3eae3f803ab3e41ea12"

async def main():
    client = TelegramClient(
        "sessions/account1",
        API_ID,
        API_HASH
    )

    await client.start()

    me = await client.get_me()

    print("Авторизован:")
    print(me.id)
    print(me.first_name)

    await client.send_message(
        "me",
        "Telethon работает"
    )

    await client.disconnect()

asyncio.run(main())
