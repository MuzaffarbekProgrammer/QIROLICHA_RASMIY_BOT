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
@dp.message(lambda m: m.text and m.text in ["MAXSULOTLAR", "SAVATCHA", "O'QUV KURS YANGILIKLARI", "BIZ BILAN BOG'LANISH", "BIZNING MANZIL", "⚙️ SOZLAMALAR"])
async def main_buttons(message: types.Message):
    text = message.text
    if message.from_user.id != ADMIN_ID and text == "⚙️ SOZLAMALAR":
        return
    menu = admin_menu if message.from_user.id == ADMIN_ID else main_menu

    if text == "MAXSULOTLAR":
        cursor.execute("SELECT id, name FROM categories")
        cats = cursor.fetchall()
        if not cats:
            await message.answer("Hozircha kategoriyalar yo'q.", reply_markup=menu)
            return
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=name, callback_data=f"cat_{cid}")] for cid, name in cats
        ])
        await message.answer("📂 Kategoriyani tanlang:", reply_markup=kb)

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
        if row and "," in row[0]:
            try:
                lat, lng = map(float, row[0].split(","))
                await message.answer_location(latitude=lat, longitude=lng)
                await message.answer("Manzil yuqorida ko'rsatildi.", reply_markup=menu)
                return
            except:
                pass
        await message.answer("Manzil hali kiritilmagan.", reply_markup=menu)

    elif text == "⚙️ SOZLAMALAR":
        await message.answer("⚙️ Admin panel – tanlang:", reply_markup=admin_panel_menu)

# ==================== ADMIN PANEL TUGMALARI ====================
@dp.message(lambda m: m.text == "💱 Valyuta kursi" and m.from_user.id == ADMIN_ID)
async def set_usd_rate_start(message: types.Message, state: FSMContext):
    await message.answer("1 USD = nechchi so'm? (masalan: 12600)", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.set_usd_rate)

@dp.message(AdminStates.set_usd_rate)
async def set_usd_rate_process(message: types.Message, state: FSMContext):
    try:
        rate = float(message.text.strip().replace(" ", ""))
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('usd_rate', ?)", (str(rate),))
        conn.commit()
        await message.answer(f"✅ Valyuta kursi yangilandi: 1 USD = {rate:,} so'm", reply_markup=admin_panel_menu)
        await state.clear()
    except ValueError:
        await message.answer("Iltimos, to'g'ri raqam kiriting!")

@dp.message(lambda m: m.text == "📄 PDF hisobot" and m.from_user.id == ADMIN_ID)
async def pdf_report(message: types.Message):
    pdf_path = f"pdfs/hisobot_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    c = canvas.Canvas(pdf_path, pagesize=A4)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(200, 800, "Qirolicha Bot Hisoboti")
    c.setFont("Helvetica", 12)
    c.drawString(100, 760, f"Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}")
    c.drawString(100, 740, "Ro'yxatga olinganlar (kurslar):")
    cursor.execute("SELECT id, fish, course_type, amount, date FROM enrollments")
    enrolls = cursor.fetchall()
    y = 720
    for row in enrolls:
        c.drawString(100, y, f"{row[0]}. {row[1]} - {row[2]} - {row[3]} so'm - {row[4]}")
        y -= 20
    c.drawString(100, y - 20, "Buyurtmalar (maxsulotlar):")
    cursor.execute("SELECT id, total_som, delivery_type, date FROM orders")
    orders = cursor.fetchall()
    y -= 40
    for row in orders:
        c.drawString(100, y, f"{row[0]}. {row[1]:,} so'm - {row[2]} - {row[3]}")
        y -= 20
    c.save()
    await message.answer_document(FSInputFile(pdf_path), caption="Hisobot PDF")
    os.remove(pdf_path)

# ==================== MAXSULOT QO'SHISH (valyuta bilan) ====================
@dp.message(lambda m: m.text == "🛍 Maxsulot qo'shish" and m.from_user.id == ADMIN_ID)
async def add_product_start(message: types.Message, state: FSMContext):
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

@dp.callback_query(lambda c: c.data.startswith("addprodcat_"))
async def add_product_category(callback: types.CallbackQuery, state: FSMContext):
    cat_id = int(callback.data.split("_")[1])
    await state.update_data(cat_id=cat_id)
    await callback.message.answer("Maxsulot rasmini yuboring (ixtiyoriy):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.add_product_photo)
    await callback.answer()

@dp.message(AdminStates.add_product_photo)
async def add_product_photo(message: types.Message, state: FSMContext):
    photo_name = None
    if message.photo:
        file = await bot.get_file(message.photo[-1].file_id)
        photo_name = f"{message.message_id}.jpg"
        await bot.download_file(file.file_path, f"photos/{photo_name}")
    await state.update_data(photo=photo_name)
    await message.answer("Maxsulot nomini yozing:")
    await state.set_state(AdminStates.add_product_name)

@dp.message(AdminStates.add_product_name)
async def add_product_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text.strip())
    await message.answer("Tavsif yozing:")
    await state.set_state(AdminStates.add_product_desc)

@dp.message(AdminStates.add_product_desc)
async def add_product_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text.strip())
    await message.answer("Kod yozing:")
    await state.set_state(AdminStates.add_product_code)

@dp.message(AdminStates.add_product_code)
async def add_product_code(message: types.Message, state: FSMContext):
    await state.update_data(code=message.text.strip())
    kb = ReplyKeyboardMarkup(keyboard=[
        [KeyboardButton(text="🇺🇿 So'm"), KeyboardButton(text="💵 USD")]
    ], resize_keyboard=True)
    await message.answer("Narx birligini tanlang:", reply_markup=kb)
    await state.set_state(AdminStates.add_product_currency)

@dp.message(AdminStates.add_product_currency)
async def add_product_currency(message: types.Message, state: FSMContext):
    currency = "SOM" if "So'm" in message.text else "USD"
    await state.update_data(currency=currency)
    await message.answer(f"{currency} da narxni yozing:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.add_product_price)

@dp.message(AdminStates.add_product_price)
async def add_product_price(message: types.Message, state: FSMContext):
    try:
        price = float(message.text.strip().replace(" ", ""))
        data = await state.get_data()
        if data['currency'] == "SOM":
            price_som = int(price)
            price_usd = 0.0
        else:
            price_som = 0
            price_usd = price
        cursor.execute("""INSERT INTO products
                          (category_id, name, description, code, price_som, price_usd, currency, photo)
                          VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                       (data['cat_id'], data['name'], data['desc'], data['code'],
                        price_som, price_usd, data['currency'], data.get('photo')))
        conn.commit()
        await message.answer("✅ Maxsulot muvaffaqiyatli qo'shildi!", reply_markup=admin_panel_menu)
        await state.clear()
    except ValueError:
        await message.answer("Raqam kiriting!")

# ==================== TO'LOV TASDIQLASH ====================
pending_payments = {}  # {user_id: {'type': 'course' or 'order', 'screenshot_message_id': id}}

@dp.message(CartStates.waiting_screenshot)
async def cart_screenshot(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("Faqat rasm yuboring.")
        return
    screenshot_id = message.message_id
    await bot.forward_message(ADMIN_ID, message.chat.id, screenshot_id)
    pending_payments[message.from_user.id] = {'type': 'order', 'screenshot_message_id': screenshot_id}
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
    pending_payments[message.from_user.id] = {'type': 'course', 'course_type': data['course_type'], 'screenshot_message_id': screenshot_id}
    await message.answer("📸 Screenshot adminga yuborildi. Tasdiqlash kutilmoqda.", reply_markup=main_menu)
    await state.clear()

@dp.message(lambda m: m.photo and m.from_user.id == ADMIN_ID)
async def admin_see_screenshot(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"confirm_payment_{message.message_id}")]
    ])
    await message.answer_photo(message.photo[-1].file_id, caption="To'lov screenshot – tasdiqlaysizmi?", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("confirm_payment_") and c.from_user.id == ADMIN_ID)
async def confirm_payment(callback: types.CallbackQuery):
    msg_id = int(callback.data.split("_")[2])
    # Foydalanuvchini topish uchun pending_payments dan qidiramiz (realda yaxshiroq saqlash kerak)
    user_id = None
    payment_type = None
    for uid, data in pending_payments.items():
        if data['screenshot_message_id'] == msg_id:
            user_id = uid
            payment_type = data['type']
            break
    if not user_id:
        await callback.answer("Foydalanuvchi topilmadi.")
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

# ==================== RENDER UCHUN WEB SERVER ====================
async def health(request):
    return web.Response(text="Bot is running!")

async def web_server():
    app = web.Application()
    app.router.add_get('/', health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8000)
    await site.start()
    logging.info("Web server started on port 8000")

# ==================== MAIN ====================
async def main():
    await asyncio.gather(
        web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
