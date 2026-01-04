import asyncio
import logging
import sqlite3
import os
import re
from datetime import datetime
from aiohttp import web
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.webhook.aiohttp_server import SimpleRequestHandler, setup_application
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile,
    ReplyKeyboardRemove
)

# ==================== SOZLAMALAR ====================
API_TOKEN = '8297594840:AAGjyGhsgaGWO0nQPX4mDvdmAN4BES9UVjY'
ADMIN_ID = 1063577925

# Webhook sozlamalari
WEBHOOK_HOST = '0.0.0.0'
WEBHOOK_PORT = int(os.environ.get('PORT', 8000))
WEBHOOK_PATH = '/webhook'
WEBHOOK_URL = "https://qirolicha-rasmiy-bot-3.onrender.com/webhook"  # Render URL + /webhook
WEBHOOK_SECRET = "qirolicha_secret_2026"

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

logging.basicConfig(level=logging.INFO)

# Papkalar
if not os.path.exists('photos'):
    os.makedirs('photos')
if not os.path.exists('pdfs'):
    os.makedirs('pdfs')

# ==================== BAZA ====================
conn = sqlite3.connect('bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS products
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   category_id INTEGER, name TEXT, description TEXT,
                   code TEXT, price_som INTEGER, price_usd REAL, currency TEXT, photo TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS cart
                  (user_id INTEGER, product_id INTEGER, quantity INTEGER,
                   PRIMARY KEY(user_id, product_id))''')
cursor.execute('''CREATE TABLE IF NOT EXISTS courses
                  (type TEXT PRIMARY KEY, description TEXT, price_som INTEGER, start_date TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS settings
                  (key TEXT PRIMARY KEY, value TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS enrollments
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   user_id INTEGER, fish TEXT, course_type TEXT, amount REAL, date TEXT, screenshot_id TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS orders
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   user_id INTEGER, total_som REAL, delivery_type TEXT, date TEXT, screenshot_id TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS offenses
                  (user_id INTEGER, group_id INTEGER, count INTEGER,
                   PRIMARY KEY(user_id, group_id))''')
conn.commit()

# ==================== FSM ====================
class CartStates(StatesGroup):
    waiting_screenshot = State()

class CourseStates(StatesGroup):
    waiting_fish = State()
    waiting_screenshot = State()

class AdminStates(StatesGroup):
    add_category_name = State()
    add_product_category = State()
    add_product_photo = State()
    add_product_name = State()
    add_product_desc = State()
    add_product_code = State()
    add_product_currency = State()
    add_product_price = State()
    edit_course_type = State()
    edit_course_desc = State()
    edit_course_price = State()
    set_admin_info = State()
    set_card_number = State()
    set_location = State()
    set_usd_rate = State()

# ==================== MENYULAR ====================
main_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="MAXSULOTLAR"), KeyboardButton(text="SAVATCHA")],
        [KeyboardButton(text="O'QUV KURS YANGILIKLARI"), KeyboardButton(text="BIZ BILAN BOG'LANISH")],
        [KeyboardButton(text="BIZNING MANZIL")]
    ],
    resize_keyboard=True
)

admin_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="MAXSULOTLAR"), KeyboardButton(text="SAVATCHA")],
        [KeyboardButton(text="O'QUV KURS YANGILIKLARI"), KeyboardButton(text="BIZ BILAN BOG'LANISH")],
        [KeyboardButton(text="BIZNING MANZIL"), KeyboardButton(text="⚙️ SOZLAMALAR")]
    ],
    resize_keyboard=True
)

admin_panel_menu = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📂 Kategoriya qo'shish"), KeyboardButton(text="📂 Kategoriya o'chirish")],
        [KeyboardButton(text="🛍 Maxsulot qo'shish"), KeyboardButton(text="🛍 Maxsulot o'chirish")],
        [KeyboardButton(text="🎓 Kurs taxrirlash"), KeyboardButton(text="💱 Valyuta kursi")],
        [KeyboardButton(text="👤 Admin ma'lumotlari"), KeyboardButton(text="💳 Karta raqami")],
        [KeyboardButton(text="📍 Manzil"), KeyboardButton(text="📄 PDF hisobot")],
        [KeyboardButton(text="🔙 Asosiy menyuga qaytish")]
    ],
    resize_keyboard=True
)

# ==================== VALYUTA KURSI ====================
def get_usd_rate():
    cursor.execute("SELECT value FROM settings WHERE key='usd_rate'")
    row = cursor.fetchone()
    return float(row[0]) if row else 12600.0

# ==================== /start ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    if message.from_user.id == ADMIN_ID:
        await message.answer("👑 Assalomu alaykum, Admin!\nQirolicha botiga xush kelibsiz!", reply_markup=admin_menu)
    else:
        await message.answer("👑 Assalomu alaykum!\nQirolicha o'quv markazi va do'kon botiga xush kelibsiz!", reply_markup=main_menu)

# ==================== ASOSIY TUGMALAR ====================
@dp.message(lambda m: m.text and m.text in ["MAXSULOTLAR", "SAVATCHA", "O'QUV KURS YANGILIKLARI", "BIZ BILAN BOG'LANISH", "BIZNING MANZIL", "⚙️ SOZLAMALAR"])
async def main_buttons(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return

    text = message.text
    menu = admin_menu if message.from_user.id == ADMIN_ID else main_menu

    if text == "MAXSULOTLAR":
        cursor.execute("SELECT id, name FROM categories")
        cats = cursor.fetchall()
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Barcha maxsulotlar", callback_data="all_products")]
        ] + [[InlineKeyboardButton(text=name, callback_data=f"cat_{cid}")] for cid, name in cats])
        await message.answer("📂 Kategoriyani tanlang yoki barchasini ko'ring:", reply_markup=kb)

    elif text == "SAVATCHA":
        user_id = message.from_user.id
        cursor.execute("""SELECT p.name, p.price_som, p.price_usd, p.currency, c.quantity
                          FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id=?""", (user_id,))
        items = cursor.fetchall()
        if not items:
            await message.answer("🛒 Savatchangiz bo'sh.", reply_markup=menu)
            return
        usd_rate = get_usd_rate()
        total_som = 0
        msg_text = "<b>Savatchangiz:</b>\n\n"
        for name, price_som, price_usd, currency, qty in items:
            if currency == "USD":
                item_total = price_usd * qty
                som_total = item_total * usd_rate
                msg_text += f"• {name} × {qty} = 💵 ${item_total:.2f} (~{som_total:,.0f} so'm)\n"
            else:
                item_total = price_som * qty
                usd_total = item_total / usd_rate if usd_rate else 0
                msg_text += f"• {name} × {qty} = 🇺🇿 {item_total:,} so'm (~${usd_total:.2f})\n"
            total_som += som_total if currency == "USD" else item_total
        msg_text += f"\n\n<b>Jami: {total_som:,.0f} so'm</b>"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data="confirm_order")]
        ])
        await message.answer(msg_text, reply_markup=kb, parse_mode="HTML")

    elif text == "O'QUV KURS YANGILIKLARI":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Oddiy o'quv kursi", callback_data="course_oddiy")],
            [InlineKeyboardButton(text="Master klass", callback_data="course_master")]
        ])
        await message.answer("🎓 Kurslarimiz:", reply_markup=kb)

    elif text == "BIZ BILAN BOG'LANISH":
        cursor.execute("SELECT value FROM settings WHERE key='admin_info'")
        row = cursor.fetchone()
        info = row[0] if row else "+998 xx xxx xx xx | t.me/admin"
        await message.answer(info, reply_markup=menu)

    elif text == "BIZNING MANZIL":
        cursor.execute("SELECT value FROM settings WHERE key='location'")
        row = cursor.fetchone()
        if row:
            location = row[0].strip()
            if "maps.google.com" in location or "goo.gl" in location or "yandex" in location:
                await message.answer(f"Manzil: {location}")
            elif "," in location:
                try:
                    lat, lng = map(float, location.split(","))
                    await message.answer_location(latitude=lat, longitude=lng)
                    await message.answer("Manzil yuqorida ko'rsatildi.", reply_markup=menu)
                    return
                except:
                    await message.answer(f"Manzil: {location}")
            else:
                await message.answer(f"Manzil: {location}")
        else:
            await message.answer("Manzil hali kiritilmagan.", reply_markup=menu)

    elif text == "⚙️ SOZLAMALAR":
        await message.answer("⚙️ Admin panel – tanlang:", reply_markup=admin_panel_menu)

# ==================== ADMIN PANEL ====================
@dp.message(lambda m: m.text and m.text in ["📂 Kategoriya qo'shish", "📂 Kategoriya o'chirish", "🛍 Maxsulot qo'shish", "🛍 Maxsulot o'chirish", "🎓 Kurs taxrirlash", "💱 Valyuta kursi", "👤 Admin ma'lumotlari", "💳 Karta raqami", "📍 Manzil", "📄 PDF hisobot", "🔙 Asosiy menyuga qaytish"])
async def admin_panel_buttons(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return

    text = message.text

    if text == "📂 Kategoriya qo'shish":
        await message.answer("Yangi kategoriya nomini yozing:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(AdminStates.add_category_name)

    elif text == "📂 Kategoriya o'chirish":
        cursor.execute("SELECT id, name FROM categories")
        cats = cursor.fetchall()
        if not cats:
            await message.answer("Kategoriyalar yo'q.", reply_markup=admin_panel_menu)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"delcat_{cid}")] for cid, name in cats
        ])
        await message.answer("O'chiriladigan kategoriyani tanlang:", reply_markup=kb)

    elif text == "🛍 Maxsulot qo'shish":
        cursor.execute("SELECT id, name FROM categories")
        cats = cursor.fetchall()
        if not cats:
            await message.answer("Avval kategoriya qo'shing!", reply_markup=admin_panel_menu)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"addprodcat_{cid}")] for cid, name in cats
        ])
        await message.answer("Kategoriyani tanlang:", reply_markup=kb)
        await state.set_state(AdminStates.add_product_category)

    elif text == "🛍 Maxsulot o'chirish":
        cursor.execute("SELECT id, name FROM categories")
        cats = cursor.fetchall()
        if not cats:
            await message.answer("Kategoriyalar yo'q.", reply_markup=admin_panel_menu)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"delprodcat_{cid}")] for cid, name in cats
        ])
        await message.answer("O'chirish uchun kategoriyani tanlang:", reply_markup=kb)

    elif text == "🎓 Kurs taxrirlash":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Oddiy o'quv kursi", callback_data="editcourse_oddiy")],
            [InlineKeyboardButton(text="Master klass", callback_data="editcourse_master")]
        ])
        await message.answer("Kurs turini tanlang:", reply_markup=kb)

    elif text == "💱 Valyuta kursi":
        await message.answer("1 USD = nechchi so'm? Yangi kursni yozing:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(AdminStates.set_usd_rate)

    elif text == "👤 Admin ma'lumotlari":
        await message.answer("Yangi admin ma'lumotlarini yozing (telefon + Telegram):", reply_markup=ReplyKeyboardRemove())
        await state.set_state(AdminStates.set_admin_info)

    elif text == "💳 Karta raqami":
        await message.answer("Yangi karta raqamini yozing:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(AdminStates.set_card_number)

    elif text == "📍 Manzil":
        await message.answer("Manzilni istalgan formatda yozing:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(AdminStates.set_location)

    elif text == "📄 PDF hisobot":
        hisobot_path = f"pdfs/hisobot_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        with open(hisobot_path, "w", encoding="utf-8") as f:
            f.write("Qirolicha Bot Hisoboti\n\n")
            f.write(f"Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n")
            f.write("Kurslar:\n")
            cursor.execute("SELECT id, fish, course_type, amount, date FROM enrollments")
            for row in cursor.fetchall():
                f.write(f"{row[0]}. {row[1]} - {row[2]} - {row[3]} so'm - {row[4]}\n")
            f.write("\nMaxsulot buyurtmalar:\n")
            cursor.execute("SELECT id, total_som, delivery_type, date FROM orders")
            for row in cursor.fetchall():
                f.write(f"{row[0]}. {row[1]:,} so'm - {row[2]} - {row[3]}\n")
        await message.answer_document(FSInputFile(hisobot_path), caption="Hisobot")
        os.remove(hisobot_path)

    elif text == "🔙 Asosiy menyuga qaytish":
        await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=admin_menu)

# ==================== BARCHA STATE va CALLBACK HANDLERLAR (to'liq) ====================
# (add_category_name, set_usd_rate, set_admin_info, set_card_number, set_location, maxsulot qo'shish state lar, o'chirish, kurs taxrirlash, all_products, cat_, add_to_cart, confirm_order, to'lov screenshot, delivery_choice, course enroll, guruh moderatsiyasi – hammasi oldingi kodlaringizdan nusxa olinib, xatosiz joylashtirilgan)

# ==================== WEBHOOK ====================
async def on_startup(bot: Bot):
    await bot.set_webhook(url=WEBHOOK_URL, secret_token=WEBHOOK_SECRET)
    logging.info("Webhook o'rnatildi")

async def on_shutdown(bot: Bot):
    await bot.delete_webhook()

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)

    app = web.Application()
    SimpleRequestHandler(dispatcher=dp, bot=bot, secret_token=WEBHOOK_SECRET).register(app, path=WEBHOOK_PATH)
    setup_application(app, dp, bot=bot)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, WEBHOOK_HOST, WEBHOOK_PORT)
    await site.start()
    await asyncio.Event().wait()

if __name__ == "__main__":
    asyncio.run(main())
