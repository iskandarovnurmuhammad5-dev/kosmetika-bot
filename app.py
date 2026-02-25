import os
import asyncio
from aiogram import Bot, Dispatcher, F
from aiogram.types import Message, CallbackQuery
from aiogram.filters import Command
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder
from dotenv import load_dotenv

import db as DB

load_dotenv()
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN topilmadi. .env ni tekshiring.")
if ADMIN_ID == 0:
    raise RuntimeError("ADMIN_ID topilmadi. .env ni tekshiring.")

bot = Bot(BOT_TOKEN)
dp = Dispatcher()

# USER_STATE[user_id] = {"step": "...", ...}
USER_STATE = {}


def set_state(uid: int, **kwargs):
    USER_STATE[uid] = {**USER_STATE.get(uid, {}), **kwargs}


def get_state(uid: int):
    return USER_STATE.get(uid, {})


def clear_state(uid: int):
    USER_STATE.pop(uid, None)


def money(n: int) -> str:
    return f"{n:,}".replace(",", " ") + " so‘m"


def main_menu_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="🧴 Katalog")
    kb.button(text="🛒 Korzinka")
    kb.adjust(2)
    return kb.as_markup(resize_keyboard=True)


@dp.message(Command("start"))
async def start(message: Message):
    clear_state(message.from_user.id)
    await message.answer("Assalomu alaykum 🌸\nMenyudan tanlang:", reply_markup=main_menu_kb())


# ---------------- KATALOG ----------------
@dp.message(F.text == "🧴 Katalog")
async def catalog_categories(message: Message):
    cats = await DB.list_categories()
    if not cats:
        await message.answer("Hozircha katalog bo‘sh.")
        return

    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(text=c, callback_data=f"cat:{c}")
    kb.adjust(2)
    await message.answer("Kategoriya tanlang:", reply_markup=kb.as_markup())


@dp.callback_query(F.data.startswith("cat:"))
async def catalog_products(cb: CallbackQuery):
    category = cb.data.split("cat:", 1)[1]
    prods = await DB.list_products_by_category(category)

    if not prods:
        await cb.message.edit_text(f"'{category}' bo‘limida mahsulot yo‘q.")
        await cb.answer()
        return

    text_lines = [f"🧴 {category} mahsulotlari:\n"]
    kb = InlineKeyboardBuilder()
    for pid, name, price in prods[:30]:
        text_lines.append(f"• {name} — {money(price)}")
        kb.button(text=f"👁 {name}", callback_data=f"prod:{pid}")

    kb.adjust(1)
    kb.button(text="⬅️ Kategoriyalar", callback_data="cats:back")
    kb.adjust(1)

    await cb.message.edit_text("\n".join(text_lines), reply_markup=kb.as_markup())
    await cb.answer()


@dp.callback_query(F.data == "cats:back")
async def cats_back(cb: CallbackQuery):
    cats = await DB.list_categories()
    kb = InlineKeyboardBuilder()
    for c in cats:
        kb.button(text=c, callback_data=f"cat:{c}")
    kb.adjust(2)
    await cb.message.edit_text("Kategoriya tanlang:", reply_markup=kb.as_markup())
    await cb.answer()


@dp.callback_query(F.data.startswith("prod:"))
async def product_page(cb: CallbackQuery):
    pid = int(cb.data.split("prod:", 1)[1])
    p = await DB.get_product(pid)
    if not p:
        await cb.answer("Mahsulot topilmadi", show_alert=True)
        return

    _, name, category, price, desc = p
    reviews = await DB.get_reviews_for_product(pid, limit=3)

    rev_text = "\n📝 Oxirgi fikrlar:\n"
    if not reviews:
        rev_text += "— Hali fikrlar yo‘q."
    else:
        for r, t, _ in reviews:
            rev_text += f"⭐️{r} — {t}\n"
        rev_text = rev_text.rstrip()

    text = (
        f"🧴 {name}\n"
        f"💰 Narx: {money(price)}\n\n"
        f"{desc}\n"
        f"{rev_text}"
    )

    kb = InlineKeyboardBuilder()
    kb.button(text="➕ Korzinkaga qo‘shish", callback_data=f"cart:add:{pid}")
    kb.button(text="⬅️ Orqaga", callback_data=f"cat:{category}")
    kb.adjust(1)

    await cb.message.edit_text(text, reply_markup=kb.as_markup())
    await cb.answer()


# ---------------- KORZINKA ----------------
@dp.callback_query(F.data.startswith("cart:add:"))
async def cart_add(cb: CallbackQuery):
    pid = int(cb.data.split("cart:add:", 1)[1])
    set_state(cb.from_user.id, step="ask_qty", pid=pid)
    await cb.message.answer("Nechta qo‘shilsin? (1/2/3 yoki son yozing)")
    await cb.answer()


@dp.message(F.text == "🛒 Korzinka")
async def cart_menu(message: Message):
    clear_state(message.from_user.id)
    await show_cart(message)


async def show_cart(message: Message):
    cart = await DB.get_cart(message.from_user.id)
    if not cart:
        await message.answer("🛒 Korzinka bo‘sh.", reply_markup=main_menu_kb())
        return

    total = 0
    lines = []
    for pid, name, price, qty in cart:
        s = price * qty
        total += s
        lines.append(f"• {name} × {qty} = {money(s)}")

    text = "🛒 Korzinkangiz:\n\n" + "\n".join(lines) + f"\n\nJami: **{money(total)}**"

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Buyurtma berish", callback_data="checkout:start")
    kb.button(text="🧹 Tozalash", callback_data="cart:clear")
    kb.adjust(1)

    await message.answer(text, reply_markup=kb.as_markup(), parse_mode="Markdown")


@dp.callback_query(F.data == "cart:clear")
async def cart_clear(cb: CallbackQuery):
    await DB.clear_cart(cb.from_user.id)
    await cb.message.edit_text("🧹 Korzinka tozalandi.")
    await cb.answer()


# ---------------- CHECKOUT ----------------
@dp.callback_query(F.data == "checkout:start")
async def checkout_start(cb: CallbackQuery):
    cart = await DB.get_cart(cb.from_user.id)
    if not cart:
        await cb.answer("Korzinka bo‘sh", show_alert=True)
        return
    set_state(cb.from_user.id, step="checkout_name")
    await cb.message.answer("Ismingizni yozing:")
    await cb.answer()


# ---------------- ADMIN: delivered button ----------------
@dp.callback_query(F.data.startswith("admin:delivered:"))
async def admin_delivered(cb: CallbackQuery):
    if cb.from_user.id != ADMIN_ID:
        await cb.answer("Ruxsat yo‘q", show_alert=True)
        return

    order_id = int(cb.data.split("admin:delivered:", 1)[1])
    order = await DB.get_order(order_id)
    if not order:
        await cb.answer("Buyurtma topilmadi", show_alert=True)
        return

    await DB.set_order_status(order_id, "DELIVERED")
    user_id = int(order[1])

    kb = InlineKeyboardBuilder()
    kb.button(text="✍️ Fikr qoldirish", callback_data=f"review:start:{order_id}")
    kb.adjust(1)

    await bot.send_message(
        user_id,
        f"✅ Buyurtmangiz yetkazildi! (#{order_id})\nFikr qoldirasizmi?",
        reply_markup=kb.as_markup()
    )

    await cb.message.edit_text(f"✅ Buyurtma #{order_id} — DELIVERED qilindi.")
    await cb.answer("OK")


# ---------------- REVIEW FLOW ----------------
@dp.callback_query(F.data.startswith("review:start:"))
async def review_start(cb: CallbackQuery):
    order_id = int(cb.data.split("review:start:", 1)[1])
    uid = cb.from_user.id

    eligible = await DB.eligible_products_for_review(uid, order_id)
    if not eligible:
        await cb.answer("Review yozish uchun mahsulot yo‘q (yoki yozib bo‘lgansiz).", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for pid, name in eligible:
        kb.button(text=name, callback_data=f"review:pick:{order_id}:{pid}")
    kb.adjust(1)

    await cb.message.answer("Qaysi mahsulot bo‘yicha fikr yozasiz?", reply_markup=kb.as_markup())
    await cb.answer()


@dp.callback_query(F.data.startswith("review:pick:"))
async def review_pick(cb: CallbackQuery):
    _, _, order_id, pid = cb.data.split(":")
    order_id = int(order_id)
    pid = int(pid)
    uid = cb.from_user.id

    eligible = await DB.eligible_products_for_review(uid, order_id)
    ok_ids = {p for p, _ in eligible}
    if pid not in ok_ids:
        await cb.answer("Siz bu mahsulotga review yozolmaysiz (yoki yozib bo‘lgansiz).", show_alert=True)
        return

    kb = InlineKeyboardBuilder()
    for r in range(1, 6):
        kb.button(text=f"⭐️{r}", callback_data=f"review:rate:{order_id}:{pid}:{r}")
    kb.adjust(5)

    await cb.message.answer("Baho bering (1–5):", reply_markup=kb.as_markup())
    await cb.answer()


@dp.callback_query(F.data.startswith("review:rate:"))
async def review_rate(cb: CallbackQuery):
    _, _, order_id, pid, rating = cb.data.split(":")
    order_id = int(order_id)
    pid = int(pid)
    rating = int(rating)
    uid = cb.from_user.id

    # qayta tekshiruv
    eligible = await DB.eligible_products_for_review(uid, order_id)
    ok_ids = {p for p, _ in eligible}
    if pid not in ok_ids:
        await cb.answer("Siz bu mahsulotga review yozolmaysiz (yoki yozib bo‘lgansiz).", show_alert=True)
        return

    set_state(uid, step="review_text", review_order_id=order_id, review_product_id=pid, review_rating=rating)
    await cb.message.answer("Endi fikringizni yozing (matn):")
    await cb.answer()


# ---------------- UNIVERSAL TEXT ROUTER ----------------
@dp.message()
async def universal_router(message: Message):
    uid = message.from_user.id
    text = (message.text or "").strip()
    st = get_state(uid)
    step = st.get("step")

    # qty
    if step == "ask_qty":
        try:
            qty = int(text)
            if qty <= 0 or qty > 999:
                raise ValueError()
        except Exception:
            await message.answer("Iltimos son kiriting (masalan 1 yoki 2).")
            return

        pid = int(st["pid"])
        await DB.add_to_cart(uid, pid, qty)
        clear_state(uid)
        await message.answer("✅ Korzinkaga qo‘shildi.", reply_markup=main_menu_kb())
        return

    # checkout name
    if step == "checkout_name":
        if len(text) < 2:
            await message.answer("Ism juda qisqa. Qayta yozing.")
            return
        set_state(uid, full_name=text, step="checkout_phone")
        await message.answer("Telefon raqamingizni yozing (masalan: +998901234567):")
        return

    # checkout phone
    if step == "checkout_phone":
        if len(text) < 7:
            await message.answer("Telefon raqamni to‘g‘ri yozing.")
            return
        set_state(uid, phone=text, step="checkout_address")
        await message.answer("Manzilingizni yozing (shahar/tuman + uy):")
        return

    # checkout address -> create order
    if step == "checkout_address":
        if len(text) < 5:
            await message.answer("Manzil juda qisqa. Batafsilroq yozing.")
            return

        set_state(uid, address=text)
        data = get_state(uid)

        try:
            order_id = await DB.create_order_from_cart(
                user_id=uid,
                full_name=data["full_name"],
                phone=data["phone"],
                address=data["address"],
            )
        except ValueError:
            clear_state(uid)
            await message.answer("Korzinka bo‘sh. Avval mahsulot qo‘shing.", reply_markup=main_menu_kb())
            return

        clear_state(uid)
        await message.answer(f"✅ Buyurtma qabul qilindi! Buyurtma raqami: #{order_id}", reply_markup=main_menu_kb())

        # Admin’ga yuborish + Yetkazildi tugmasi
        items = await DB.get_order_items(order_id)
        total = sum(price * qty for (_, _, price, qty) in items)

        lines = [
            f"📦 **YANGI BUYURTMA #{order_id}**",
            f"User: @{message.from_user.username or '—'} (id={uid})",
            f"Ism: {data['full_name']}",
            f"Tel: {data['phone']}",
            f"Manzil: {data['address']}",
            "",
            "🧾 Mahsulotlar:",
        ]
        for (_, name, price, qty) in items:
            lines.append(f"• {name} × {qty} = {money(price * qty)}")
        lines.append(f"\nJami: **{money(total)}**")

        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Yetkazildi", callback_data=f"admin:delivered:{order_id}")
        kb.adjust(1)

        await bot.send_message(ADMIN_ID, "\n".join(lines), reply_markup=kb.as_markup(), parse_mode="Markdown")
        return

    # review text
    if step == "review_text":
        if len(text) < 3:
            await message.answer("Fikr juda qisqa. Biroz batafsilroq yozing.")
            return

        order_id = int(st["review_order_id"])
        pid = int(st["review_product_id"])
        rating = int(st["review_rating"])

        try:
            await DB.add_review(uid, pid, order_id, rating, text)
        except Exception:
            clear_state(uid)
            await message.answer("Bu mahsulot uchun siz allaqachon fikr yozgansiz ✅", reply_markup=main_menu_kb())
            return

        clear_state(uid)
        await message.answer("Rahmat! Fikringiz saqlandi 💖", reply_markup=main_menu_kb())
        return

    # fallback: hech narsa qilmaymiz
    return


async def main():
    await DB.init_db()
    await DB.seed_products_if_empty()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
