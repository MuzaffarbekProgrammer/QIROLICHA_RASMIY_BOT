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

# ==================== ASOSIY TUGMALAR (state yo'q bo'lganda) ====================
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
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Barcha maxsulotlar", callback_data="all_products")]
        ] + [
            [InlineKeyboardButton(text=name, callback_data=f"cat_{cid}")] for cid, name in cats
        ])
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
            if "maps.google.com" in location or "goo.gl" in location:
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

# ==================== ADMIN PANEL TUGMALARI (state yo'q bo'lganda) ====================
@dp.message(lambda m: m.text in ["📂 Kategoriya qo'shish", "📂 Kategoriya o'chirish", "🛍 Maxsulot qo'shish", "🛍 Maxsulot o'chirish", "🎓 Kurs taxrirlash", "💱 Valyuta kursi", "👤 Admin ma'lumotlari", "💳 Karta raqami", "📍 Manzil", "📄 PDF hisobot", "🔙 Asosiy menyuga qaytish"])
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
        await message.answer("Manzilni istalgan formatda yozing (koordinata yoki Google Maps linki):", reply_markup=ReplyKeyboardRemove())
        await state.set_state(AdminStates.set_location)

    elif text == "📄 PDF hisobot":
        hisobot_path = f"pdfs/hisobot_{datetime.now().strftime('%Y%m%d_%H%M')}.txt"
        with open(hisobot_path, "w", encoding="utf-8") as f:
            f.write("Qirolicha Bot Hisoboti\n\n")
            f.write(f"Sana: {datetime.now().strftime('%d.%m.%Y %H:%M')}\n\n")
            f.write("Ro'yxatga olinganlar (kurslar):\n")
            cursor.execute("SELECT id, fish, course_type, amount, date FROM enrollments")
            enrolls = cursor.fetchall()
            if not enrolls:
                f.write("Hozircha yo'q.\n")
            for row in enrolls:
                f.write(f"{row[0]}. {row[1]} - {row[2]} - {row[3]} so'm - {row[4]}\n")
            f.write("\nBuyurtmalar (maxsulotlar):\n")
            cursor.execute("SELECT id, total_som, delivery_type, date FROM orders")
            orders = cursor.fetchall()
            if not orders:
                f.write("Hozircha yo'q.\n")
            for row in orders:
                f.write(f"{row[0]}. {row[1]:,} so'm - {row[2]} - {row[3]}\n")
        await message.answer_document(FSInputFile(hisobot_path), caption="Hisobot (text fayl)")
        os.remove(hisobot_path)

    elif text == "🔙 Asosiy menyuga qaytish":
        await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=admin_menu)

# ==================== STATE HANDLERLARI ====================
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

@dp.message(AdminStates.set_admin_info)
async def set_admin_info(message: types.Message, state: FSMContext):
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('admin_info', ?)", (message.text.strip(),))
    conn.commit()
    await message.answer("✅ Yangilandi!", reply_markup=admin_panel_menu)
    await state.clear()

@dp.message(AdminStates.set_card_number)
async def set_card(message: types.Message, state: FSMContext):
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('card_number', ?)", (message.text.strip(),))
    conn.commit()
    await message.answer("✅ Yangilandi!", reply_markup=admin_panel_menu)
    await state.clear()

@dp.message(AdminStates.set_location)
async def set_location(message: types.Message, state: FSMContext):
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES ('location', ?)", (message.text.strip(),))
    conn.commit()
    await message.answer("✅ Yangilandi!", reply_markup=admin_panel_menu)
    await state.clear()

# ==================== MAXSULOT QO'SHISH ====================
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

# ==================== BARCHA MAXSULOTLAR VA KATEGORIYA KO'RSATISH ====================
@dp.callback_query(lambda c: c.data == "all_products")
async def show_all_products(callback: types.CallbackQuery):
    cursor.execute("SELECT id, name, description, code, price_som, price_usd, currency, photo FROM products")
    products = cursor.fetchall()
    if not products:
        await callback.message.answer("Maxsulotlar yo'q.")
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
            await callback.message.answer_photo(FSInputFile(f"photos/{photo}"), caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def show_products(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    cursor.execute("SELECT id, name, description, code, price_som, price_usd, currency, photo FROM products WHERE category_id=?", (cat_id,))
    products = cursor.fetchall()
    if not products:
        await callback.message.answer("Bu kategoriyada maxsulot yo'q.")
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
            await callback.message.answer_photo(FSInputFile(f"photos/{photo}"), caption=text, reply_markup=kb, parse_mode="HTML")
        else:
            await callback.message.answer(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()

# ==================== GURUH MODERATSIYASI ====================
@dp.message(lambda m: m.chat.type in ["group", "supergroup"])
async def group_moderation(message: types.Message):
    user_id = message.from_user.id
    group_id = message.chat.id

    if user_id == ADMIN_ID:
        return

    text = message.text or message.caption or ""
    has_link = bool(message.entities and any(e.type in ["url", "text_link"] for e in message.entities))
    bad_pattern = re.compile(r"(porno|sex|xxx|18\+|reklama|t\.me/join|http)", re.IGNORECASE)
    has_bad_content = bool(bad_pattern.search(text)) or has_link

    if has_bad_content:
        await message.delete()
        cursor.execute("INSERT INTO offenses (user_id, group_id, count) VALUES (?, ?, 1) "
                       "ON CONFLICT(user_id, group_id) DO UPDATE SET count = count + 1", (user_id, group_id))
        conn.commit()
        cursor.execute("SELECT count FROM offenses WHERE user_id=? AND group_id=?", (user_id, group_id))
        count = cursor.fetchone()[0]
        if count == 1:
            await bot.send_message(group_id, f"{message.from_user.first_name}, taqiqlangan kontent! 2-marta bo'lsa bloklanasiz.")
        elif count >= 2:
            await bot.ban_chat_member(group_id, user_id)
            await bot.send_message(group_id, f"{message.from_user.first_name} bloklandi.")
            cursor.execute("DELETE FROM offenses WHERE user_id=? AND group_id=?", (user_id, group_id))
            conn.commit()

    lower_text = text.lower()
    if any(word in lower_text for word in ["kurs", "o'quv", "master"]):
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Oddiy o'quv kursi", callback_data="course_oddiy")],
            [InlineKeyboardButton(text="Master klass", callback_data="course_master")]
        ])
        await message.answer("🎓 Kurslarimiz haqida:", reply_markup=kb)

    elif any(word in lower_text for word in ["manzil", "address", "joylashuv"]):
        cursor.execute("SELECT value FROM settings WHERE key='location'")
        row = cursor.fetchone()
        if row:
            location = row[0].strip()
            if "maps.google.com" in location or "goo.gl" in location:
                await message.answer(f"Manzil: {location}")
            elif "," in location:
                try:
                    lat, lng = map(float, location.split(","))
                    await message.answer_location(latitude=lat, longitude=lng)
                except:
                    await message.answer(f"Manzil: {location}")
            else:
                await message.answer(f"Manzil: {location}")
        else:
            await message.answer("Manzil hali kiritilmagan.")

    elif any(word in lower_text for word in ["admin", "telefon", "bog'lanish"]):
        cursor.execute("SELECT value FROM settings WHERE key='admin_info'")
        row = cursor.fetchone()
        info = row[0] if row else "Admin bilan bog'laning"
        await message.answer(info)

    elif any(word in lower_text for word in ["narx", "price", "qancha"]):
        cursor.execute("SELECT value FROM settings WHERE key='admin_info'")
        row = cursor.fetchone()
        info = row[0] if row else "Admin bilan bog'laning"
        await message.answer(f"Narxlar haqida admin bilan bog'laning:\n{info}")

# ==================== QOLGAN FUNKSİYALAR (to'lov, kurs, o'chirish va h.k.) oldingi kod bilan bir xil ====================

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
