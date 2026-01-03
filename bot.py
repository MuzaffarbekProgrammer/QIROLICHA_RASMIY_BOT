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

# ==================== BARCHA TUGMALAR UCHUN UMUMIY HANDLER ====================
@dp.message(lambda m: m.text)
async def all_buttons(message: types.Message, state: FSMContext):
    text = message.text
    if message.from_user.id != ADMIN_ID and text in ["⚙️ SOZLAMALAR", "📂 Kategoriya qo'shish", "🛍 Maxsulot qo'shish", "🛍 Maxsulot o'chirish", "🎓 Kurs taxrirlash", "💱 Valyuta kursi", "👤 Admin ma'lumotlari", "💳 Karta raqami", "📍 Manzil", "📄 PDF hisobot"]:
        return

    if text == "MAXSULOTLAR":
        cursor.execute("SELECT id, name FROM categories")
        cats = cursor.fetchall()
        if not cats:
            await message.answer("Hozircha kategoriyalar yo'q.", reply_markup=admin_menu if message.from_user.id == ADMIN_ID else main_menu)
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
            await message.answer("🛒 Savatchangiz bo'sh.", reply_markup=admin_menu if message.from_user.id == ADMIN_ID else main_menu)
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
        await message.answer(info, reply_markup=admin_menu if message.from_user.id == ADMIN_ID else main_menu)

    elif text == "BIZNING MANZIL":
        cursor.execute("SELECT value FROM settings WHERE key='location'")
        row = cursor.fetchone()
        if row and "," in row[0]:
            try:
                lat, lng = map(float, row[0].split(","))
                await message.answer_location(latitude=lat, longitude=lng)
                await message.answer("Manzil yuqorida ko'rsatildi.", reply_markup=admin_menu if message.from_user.id == ADMIN_ID else main_menu)
                return
            except:
                pass
        await message.answer("Manzil hali kiritilmagan.", reply_markup=admin_menu if message.from_user.id == ADMIN_ID else main_menu)

    elif text == "⚙️ SOZLAMALAR":
        await message.answer("⚙️ Admin panel – tanlang:", reply_markup=admin_panel_menu)

    elif text == "📂 Kategoriya qo'shish":
        await message.answer("Yangi kategoriya nomini yozing:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(AdminStates.add_category_name)

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

    elif text == "💱 Valyuta kursi":
        await message.answer("1 USD = nechchi so'm? Yangi kursni yozing:", reply_markup=ReplyKeyboardRemove())
        await state.set_state(AdminStates.set_usd_rate)

    elif text == "📄 PDF hisobot":
        pdf_path = f"pdfs/hisobot_{datetime.now().strftime('%Y%m%d_%H%M')}.pdf"
        try:
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
        except Exception as e:
            await message.answer("PDF yaratishda xato yuz berdi. Reportlab o'rnatilmagan bo'lishi mumkin.")

    elif text == "🔙 Asosiy menyuga qaytish":
        await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=admin_menu)

# ==================== ADMIN HANDLERLAR (kategoriya, maxsulot, kurs, sozlamalar) ====================
@dp.message(AdminStates.add_category_name)
async def add_category_process(message: types.Message, state: FSMContext):
    name = message.text.strip()
    try:
        cursor.execute("INSERT INTO categories (name) VALUES (?)", (name,))
        conn.commit()
        await message.answer(f"✅ '{name}' kategoriyasi qo'shildi!", reply_markup=admin_panel_menu)
    except sqlite3.IntegrityError:
        await message.answer("❌ Bu nomdagi kategoriya allaqachon bor.", reply_markup=admin_panel_menu)
    await state.clear()

@dp.message(lambda m: m.text == "📂 Kategoriya o'chirish" and m.from_user.id == ADMIN_ID)
async def delete_category_start(message: types.Message):
    cursor.execute("SELECT id, name FROM categories")
    cats = cursor.fetchall()
    if not cats:
        await message.answer("Kategoriyalar yo'q.", reply_markup=admin_panel_menu)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"delcat_{cid}")] for cid, name in cats
    ])
    await message.answer("O'chiriladigan kategoriyani tanlang:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("delcat_"))
async def delete_category_process(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    cursor.execute("DELETE FROM products WHERE category_id=?", (cat_id,))
    cursor.execute("DELETE FROM categories WHERE id=?", (cat_id,))
    conn.commit()
    await callback.message.answer("✅ Kategoriya va uning maxsulotlari o'chirildi!", reply_markup=admin_panel_menu)
    await callback.answer()

# Maxsulot qo'shish (valyuta bilan)
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
        price_som = int(price) if data['currency'] == "SOM" else 0
        price_usd = price if data['currency'] == "USD" else 0.0
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

# Maxsulot o'chirish
@dp.message(lambda m: m.text == "🛍 Maxsulot o'chirish" and m.from_user.id == ADMIN_ID)
async def delete_product_start(message: types.Message):
    cursor.execute("SELECT id, name FROM categories")
    cats = cursor.fetchall()
    if not cats:
        await message.answer("Kategoriyalar yo'q.", reply_markup=admin_panel_menu)
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"delprodcat_{cid}")] for cid, name in cats
    ])
    await message.answer("O'chirish uchun kategoriyani tanlang:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("delprodcat_"))
async def delete_product_category(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    cursor.execute("SELECT id, name FROM products WHERE category_id=?", (cat_id,))
    prods = cursor.fetchall()
    if not prods:
        await callback.message.answer("Bu kategoriyada maxsulot yo'q.", reply_markup=admin_panel_menu)
        await callback.answer()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=name, callback_data=f"delprod_{pid}")] for pid, name in prods
    ])
    await callback.message.answer("O'chiriladigan maxsulotni tanlang:", reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("delprod_"))
async def delete_product_process(callback: types.CallbackQuery):
    prod_id = int(callback.data.split("_")[1])
    cursor.execute("DELETE FROM products WHERE id=?", (prod_id,))
    conn.commit()
    await callback.message.answer("✅ Maxsulot o'chirildi!", reply_markup=admin_panel_menu)
    await callback.answer()

# Kurs taxrirlash
@dp.message(lambda m: m.text == "🎓 Kurs taxrirlash" and m.from_user.id == ADMIN_ID)
async def edit_course_start(message: types.Message, state: FSMContext):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Oddiy o'quv kursi", callback_data="editcourse_oddiy")],
        [InlineKeyboardButton(text="Master klass", callback_data="editcourse_master")]
    ])
    await message.answer("Kurs turini tanlang:", reply_markup=kb)

@dp.callback_query(lambda c: c.data.startswith("editcourse_"))
async def edit_course_type(callback: types.CallbackQuery, state: FSMContext):
    ctype = callback.data.split("_")[1]
    await state.update_data(ctype=ctype)
    await callback.message.answer("Yangi tavsif yozing:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.edit_course_desc)
    await callback.answer()

@dp.message(AdminStates.edit_course_desc)
async def edit_course_desc(message: types.Message, state: FSMContext):
    await state.update_data(desc=message.text.strip())
    await message.answer("Yangi narxni so'mda yozing:")
    await state.set_state(AdminStates.edit_course_price)

@dp.message(AdminStates.edit_course_price)
async def edit_course_price(message: types.Message, state: FSMContext):
    try:
        price = int(message.text.strip().replace(" ", ""))
        data = await state.get_data()
        cursor.execute("INSERT OR REPLACE INTO courses (type, description, price_som) VALUES (?, ?, ?)",
                       (data['ctype'], data['desc'], price))
        conn.commit()
        await message.answer("✅ Kurs ma'lumotlari yangilandi!", reply_markup=admin_panel_menu)
        await state.clear()
    except ValueError:
        await message.answer("Raqam kiriting!")

# Admin ma'lumotlari, karta raqami, manzil
@dp.message(lambda m: m.text == "👤 Admin ma'lumotlari" and m.from_user.id == ADMIN_ID)
async def edit_admin_info(message: types.Message, state: FSMContext):
    await message.answer("Yangi admin ma'lumotlarini yozing (telefon + Telegram):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.set_admin_info)

@dp.message(AdminStates.set_admin_info)
async def set_admin_info(message: types.Message, state: FSMContext):
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_info', ?)", (message.text.strip(),))
    conn.commit()
    await message.answer("✅ Yangilandi!", reply_markup=admin_panel_menu)
    await state.clear()

@dp.message(lambda m: m.text == "💳 Karta raqami" and m.from_user.id == ADMIN_ID)
async def edit_card(message: types.Message, state: FSMContext):
    await message.answer("Yangi karta raqamini yozing:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.set_card_number)

@dp.message(AdminStates.set_card_number)
async def set_card(message: types.Message, state: FSMContext):
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('card_number', ?)", (message.text.strip(),))
    conn.commit()
    await message.answer("✅ Yangilandi!", reply_markup=admin_panel_menu)
    await state.clear()

@dp.message(lambda m: m.text == "📍 Manzil" and m.from_user.id == ADMIN_ID)
async def edit_location(message: types.Message, state: FSMContext):
    await message.answer("Manzilni latitude,longitude formatida yozing (masalan: 41.12345,69.12345):", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.set_location)

@dp.message(AdminStates.set_location)
async def set_location(message: types.Message, state: FSMContext):
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('location', ?)", (message.text.strip(),))
    conn.commit()
    await message.answer("✅ Yangilandi!", reply_markup=admin_panel_menu)
    await state.clear()

@dp.message(AdminStates.set_usd_rate)
async def set_usd_rate_process(message: types.Message, state: FSMContext):
    try:
        rate = float(message.text.strip().replace(" ", ""))
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('usd_rate', ?)", (str(rate),))
        conn.commit()
        await message.answer(f"✅ Valyuta kursi yangilandi: 1 USD = {rate:,} so'm", reply_markup=admin_panel_menu)
        await state.clear()
    except ValueError:
        await message.answer("Raqam kiriting!")

# ==================== MAXSULOTLAR KO'RSATISH ====================
@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def show_products(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    cursor.execute("SELECT id, name, description, code, price_som, price_usd, currency, photo FROM products WHERE category_id=?", (cat_id,))
    products = cursor.fetchall()
    menu = admin_menu if callback.from_user.id == ADMIN_ID else main_menu
    if not products:
        await callback.message.answer("Bu kategoriyada maxsulot yo'q.", reply_markup=menu)
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

@dp.callback_query(lambda c: c.data.startswith("add_"))
async def add_to_cart(callback: types.CallbackQuery):
    prod_id = int(callback.data.split("_")[1])
    user_id = callback.from_user.id
    cursor.execute("""INSERT INTO cart (user_id, product_id, quantity)
                      VALUES (?, ?, 1) ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + 1""",
                   (user_id, prod_id))
    conn.commit()
    await callback.answer("✅ Savatchaga qo'shildi!", show_alert=True)

# ==================== BUYURTMA TASDIQLASH ====================
@dp.callback_query(lambda c: c.data == "confirm_order")
async def confirm_order(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    cursor.execute("SELECT SUM(p.price_som * c.quantity) FROM cart c JOIN products p ON c.product_id=p.id WHERE c.user_id=?", (user_id,))
    total = cursor.fetchone()[0] or 0
    cursor.execute("SELECT value FROM settings WHERE key='card_number'")
    card_row = cursor.fetchone()
    card = card_row[0] if card_row else "9860 0000 0000 0000"
    if total > 500000:
        pay = total * 0.5
        await callback.message.answer(
            f"💳 Jami: {total:,} so'm\n50% oldindan to'lov: <b>{pay:,} so'm</b>\n\n"
            f"Karta: <code>{card}</code>\n\nScreenshot yuboring 👇",
            parse_mode="HTML"
        )
        await state.set_state(CartStates.waiting_screenshot)
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚶 Uzim olib ketaman", callback_data="self_pickup")],
            [InlineKeyboardButton(text="🚚 Yetkazib berish", callback_data="delivery")]
        ])
        await callback.message.answer("Yetkazish turini tanlang:", reply_markup=kb)
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
    await callback.message.answer(f"✅ Buyurtmangiz qabul qilindi!\n\n{delivery}\n\nManzil: {location}\n{admin_info}", reply_markup=main_menu if user_id != ADMIN_ID else admin_menu)
    cursor.execute("DELETE FROM cart WHERE user_id=?", (user_id,))
    conn.commit()
    await callback.answer()

# ==================== KURS RO'YXATDAN O'TISH ====================
@dp.callback_query(lambda c: c.data.startswith("course_") and not c.data.startswith("editcourse_"))
async def show_course(callback: types.CallbackQuery):
    ctype = callback.data.split("_")[1]
    cursor.execute("SELECT description FROM courses WHERE type=?", (ctype,))
    row = cursor.fetchone()
    menu = admin_menu if callback.from_user.id == ADMIN_ID else main_menu
    if not row:
        await callback.message.answer("Ma'lumot hali kiritilmagan.", reply_markup=menu)
        await callback.answer()
        return
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📝 Ro'yxatdan o'tish", callback_data=f"enroll_{ctype}")]
    ])
    await callback.message.answer(row[0], reply_markup=kb)
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("enroll_"))
async def enroll_start(callback: types.CallbackQuery, state: FSMContext):
    await callback.message.answer("F.I.Sh ni to'liq yozing:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(CourseStates.waiting_fish)
    await state.update_data(course_type=callback.data.split("_")[1])
    await callback.answer()

@dp.message(CourseStates.waiting_fish)
async def enroll_fish(message: types.Message, state: FSMContext):
    fish = message.text.strip()
    data = await state.get_data()
    ctype = data["course_type"]
    cursor.execute("SELECT price_som FROM courses WHERE type=?", (ctype,))
    row = cursor.fetchone()
    price = row[0] if row else 1000000
    pay = price * 0.5
    cursor.execute("SELECT value FROM settings WHERE key='card_number'")
    card_row = cursor.fetchone()
    card = card_row[0] if card_row else "9860 0000 0000 0000"
    await message.answer(
        f"🎓 Kurs: {ctype.capitalize()}\nF.I.Sh: {fish}\n50% to'lov: <b>{pay:,} so'm</b>\n\n"
        f"Karta: <code>{card}</code>\n\nScreenshot yuboring 👇",
        parse_mode="HTML"
    )
    await state.set_state(CourseStates.waiting_screenshot)

# ==================== TO'LOV SCREENSHOT ====================
pending_payments = {}

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
    course_type = None
    for uid, info in pending_payments.items():
        if info['screenshot_id'] == screenshot_id:
            user_id = uid
            payment_type = info['type']
            course_type = info.get('course_type')
            break
    if not user_id:
        await callback.answer("Topilmadi")
        return
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.message.answer("✅ Tasdiqlandi!")

    if payment_type == "course":
        await bot.send_message(user_id, "Siz o'quv kursiga ro'yxatga olindingiz!", reply_markup=main_menu)
        # Bazaga saqlash
        cursor.execute("INSERT INTO enrollments (user_id, fish, course_type, amount, date, screenshot_id) VALUES (?, ?, ?, ?, ?, ?)",
                       (user_id, "F.I.Sh", course_type, 0, datetime.now().strftime('%d.%m.%Y'), screenshot_id))
        conn.commit()
    else:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚶 Uzim olib ketaman", callback_data="self_pickup")],
            [InlineKeyboardButton(text="🚚 Yetkazib berish", callback_data="delivery")]
        ])
        await bot.send_message(user_id, "Buyurtmangiz tasdiqlandi! Yetkazib berish turini tanlang:", reply_markup=kb)
        # Bazaga saqlash
        cursor.execute("INSERT INTO orders (user_id, total_som, date, screenshot_id) VALUES (?, ?, ?, ?)",
                       (user_id, 0, datetime.now().strftime('%d.%m.%Y'), screenshot_id))
        conn.commit()

    if user_id in pending_payments:
        del pending_payments[user_id]
    await callback.answer()

# ==================== RENDER WEB SERVER ====================
async def health(request):
    return web.Response(text="Bot is running!")

async def web_server():
    app = web.Application()
    app.router.add_get('/', health)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8000)
    await site.start()

async def main():
    await asyncio.gather(
        web_server(),
        dp.start_polling(bot)
    )

if __name__ == "__main__":
    asyncio.run(main())
