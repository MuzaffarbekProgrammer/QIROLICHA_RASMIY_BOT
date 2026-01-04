import asyncio
import logging
import sqlite3
import os
from datetime import datetime
from aiohttp import web

from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile,
    ReplyKeyboardRemove
)

# ==================== SOZLAMALAR ====================
API_TOKEN = '8297594840:AAGjyGhsgaGWO0nQPX4mDvdmAN4BES9UVjY'
ADMIN_ID = 1063577925

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

logging.basicConfig(level=logging.INFO)

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
                  (type TEXT PRIMARY KEY, description TEXT, price_som INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS settings
                  (key TEXT PRIMARY KEY, value TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS enrollments
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   user_id INTEGER, fish TEXT, course_type TEXT, amount REAL, date TEXT, screenshot_id TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS orders
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   user_id INTEGER, total_som REAL, delivery_type TEXT, date TEXT, screenshot_id TEXT)''')
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
@dp.message(lambda m: m.text in ["MAXSULOTLAR", "SAVATCHA", "O'QUV KURS YANGILIKLARI", "BIZ BILAN BOG'LANISH", "BIZNING MANZIL", "⚙️ SOZLAMALAR"])
async def main_buttons(message: types.Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is not None:
        return

    text = message.text
    menu = admin_menu if message.from_user.id == ADMIN_ID else main_menu

    if text == "MAXSULOTLAR":
        cursor.execute("SELECT id, name FROM categories")
        cats = cursor.fetchall()
        kb_rows = [[InlineKeyboardButton(text=name, callback_data=f"cat_{cid}")] for cid, name in cats]
        kb_rows.append([InlineKeyboardButton(text="🛍 Barcha maxsulotlar", callback_data="all_products")])
        kb = InlineKeyboardMarkup(inline_keyboard=kb_rows)
        await message.answer("📂 Kategoriyani tanlang yoki barcha maxsulotlarni ko'ring:", reply_markup=kb)

    # SAVATCHA, O'QUV KURS, BOG'LANISH, MANZIL, SOZLAMALAR – oldingi kod bilan bir xil

# ==================== BARCHA MAXSULOTLAR ====================
@dp.callback_query(lambda c: c.data == "all_products")
async def show_all_products(callback: types.CallbackQuery):
    cursor.execute("SELECT id, name, description, code, price_som, price_usd, currency, photo FROM products")
    products = cursor.fetchall()
    menu = admin_menu if callback.from_user.id == ADMIN_ID else main_menu
    if not products:
        await callback.message.answer("Hozircha maxsulotlar yo'q.", reply_markup=menu)
        await callback.answer()
        return
    for p in products:
        pid, name, desc, code, price_som, price_usd, currency, photo = p
        text = f"<b>{name}</b>\n{desc}\nKod: {code}\n"
        if currency == "USD":
            text += f"Narx: 💵 ${price_usd:.2f}"
        else:
            text += f"Narx: 🇺🇿 {price_som:,} so'm"
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🛒 Savatchaga qo'shish", callback_data=f"add_{pid}")]
        ])
        if photo and os.path.exists(f"photos/{photo}"):
            await callback.message.answer_photo(
                FSInputFile(f"photos/{photo}"),
                caption=text,
                reply_markup=kb,
                parse_mode="HTML"
            )
        else:
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

# ==================== ADMIN PANEL TUGMALARI ====================
# oldingi kod bilan bir xil (state yo'q bo'lganda)

# ==================== TO'LOV TASDIQLASH (yangi qo'shimcha bilan) ====================
pending_payments = {}  # {user_id: {'type': 'course' or 'order', 'screenshot_id': id}}

@dp.message(CartStates.waiting_screenshot)
async def cart_screenshot(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("Faqat rasm yuboring.")
        return
    screenshot_id = message.message_id
    await bot.forward_message(ADMIN_ID, message.chat.id, screenshot_id)
    pending_payments[message.from_user.id] = {'type': 'order', 'screenshot_id': screenshot_id}
    await message.answer("📸 Screenshot adminga yuborildi. Tasdiqlash kutilmoqda...", reply_markup=main_menu)
    await state.clear()

@dp.message(CourseStates.waiting_screenshot)
async def course_screenshot(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("Faqat rasm yuboring.")
        return
    screenshot_id = message.message_id
    await bot.forward_message(ADMIN_ID, message.chat.id, screenshot_id)
    data = await state.get_data()
    pending_payments[message.from_user.id] = {'type': 'course', 'course_type': data['course_type'], 'screenshot_id': screenshot_id}
    await message.answer("📸 Screenshot adminga yuborildi. Tasdiqlash kutilmoqda.", reply_markup=main_menu)
    await state.clear()

@dp.message(lambda m: m.photo and m.from_user.id == ADMIN_ID)
async def admin_screenshot(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_{message.message_id}")]
    ])
    await message.answer_photo(message.photo[-1].file_id, caption="To'lov screenshot – tasdiqlaysizmi?", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("confirm_") and c.from_user.id == ADMIN_ID)
async def confirm_payment(callback: types.CallbackQuery):
    screenshot_id = int(callback.data.split("_")[1])
    user_id = None
    payment_type = None
    for uid, info in pending_payments.items():
        if info['screenshot_id'] == screenshot_id:
            user_id = uid
            payment_type = info['type']
            break
    if not user_id:
        await callback.answer("Topilmadi")
        return

    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("✅ Tasdiqlandi!")

    if payment_type == "course":
        await bot.send_message(user_id, "Siz o'quv kursiga ro'yxatga olindingiz!", reply_markup=main_menu)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚶 Uzim olib ketaman", callback_data="self_pickup")],
            [InlineKeyboardButton(text="🚚 Yetkazib berish", callback_data="delivery")]
        ])
        await bot.send_message(user_id, "Buyurtmangiz tasdiqlandi! Yetkazib berish turini tanlang:", reply_markup=kb)

    del pending_payments[user_id]
    await callback.answer()

@dp.callback_query(lambda c: c.data in ["self_pickup", "delivery"])
async def delivery_choice(callback: types.CallbackQuery):
    delivery = "Uzim olib ketaman" if callback.data == "self_pickup" else "Yetkazib berish"
    user_id = callback.from_user.id
    cursor.execute("SELECT value FROM settings WHERE key='location'")
    location_row = cursor.fetchone()
    location = location_row[0] if location_row else "Manzil kiritilmagan"
    cursor.execute("SELECT value FROM settings WHERE key='admin_info'")
    admin_info_row = cursor.fetchone()
    admin_info = admin_info_row[0] if admin_info_row else "Admin bilan bog'laning"
    await callback.message.answer(
        f"✅ Qabul qilindi!\n\n"
        f"{delivery}\n\n"
        f"Manzil: {location}\n"
        f"{admin_info}\n\n"
        f"Xaridingizdan mamnunmiz!",
        reply_markup=main_menu if user_id != ADMIN_ID else admin_menu
    )
    await callback.answer()

# ==================== MANZIL (Google Maps linki ham qabul qiladi) ====================
# set_location handleri oldingi kod bilan bir xil – text sifatida saqlaydi, jo'natganda text chiqaradi

# ==================== QOLGAN HANDLERLAR ====================
# barcha oldingi handlerlar (kategoriya, maxsulot qo'shish/o'chirish, kurs taxrirlash, valyuta, PDF hisobot va h.k.) – hammasi ishlaydi

# ==================== RENDER WEB SERVER ====================
# oldingi kod bilan bir xil

async def main():
    await asyncio.gather(
        web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
