import asyncio
import os
import sys

from aiogram import Bot

from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN", "")


async def main():
    if not BOT_TOKEN:
        print("Configure BOT_TOKEN no .env primeiro (veja README.md).")
        sys.exit(1)
    bot = Bot(BOT_TOKEN)
    updates = await bot.get_updates()
    if not updates:
        print("Nenhuma mensagem nova ainda. Mande /start para o seu bot no Telegram e rode de novo.")
    for u in updates:
        msg = u.message or u.edited_message
        if msg:
            print(f"chat_id={msg.chat.id} user={msg.from_user.full_name if msg.from_user else '?'} text={msg.text!r}")
    await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())