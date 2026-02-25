import os
import asyncio
from dotenv import load_dotenv

from aiogram import Bot, Dispatcher, F
from aiogram.types import Message
from aiogram.enums import ParseMode

# ---------- ENV ----------
load_dotenv()  # .env bo'lsa o'qiydi, bo'lmasa jim o'tadi (Railway'da env variables ishlaydi)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")  # Railway Variables'da ADMIN_ID bo'lishi shart

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. Railway Variables yoki .env ni tekshiring.")
if not ADMIN_ID:
    raise RuntimeError("ADMIN_ID topilmadi. Railway Variables yoki .env ni tekshiring.")

# ADMIN_ID ni int qilib olamiz (ba'zi joylarda solishtirish uchun kerak bo'ladi)
try:
    ADMIN_ID_INT = int(ADMIN_ID)
except ValueError:
    raise RuntimeError("ADMIN_ID raqam bo‘lishi kerak. @userinfobot dan olingan ID ni yozing.")

# ---------- BOT ----------
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

# ---------- HANDLERS ----------
@dp.message(F.text == "/start")
async def start_cmd(message: Message):
    await message.answer(
        "✅ Bot ishlayapti!\n\n"
        "Railway deploy OK.\n"
        "Keyingi qadam: katalog/mahsulot funksiyalarini qo‘shamiz."
    )

@dp.message()
async def echo(message: Message):
    # Oddiy test uchun: nima yozsangiz qaytaradi
    if message.text:
        await message.answer(f"Siz yozdingiz: <b>{message.text}</b>")
    else:
        await message.answer("Matn yuboring 🙂")

# ---------- MAIN ----------
async def main():
    # Agar DB init bo'lsa, keyin qo'shamiz:
    # import db as DB
    # await DB.init_db()
    # await DB.seed_products_if_empty()

    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
