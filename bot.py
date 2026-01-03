import asyncio
import logging
import sqlite3
import os

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

# ==================== BAZA ====================
conn = sqlite3.connect('bot.db', check_same_thread=False)
cursor = conn.cursor()

cursor.execute('''CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS products
                  (id INTEGER PRIMARY KEY AUTOINCREMENT,
                   category_id INTEGER, name TEXT, description TEXT,
                   code TEXT, price_som INTEGER, price_usd REAL, photo TEXT)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS cart
                  (user_id INTEGER, product_id INTEGER, quantity INTEGER,
                   PRIMARY KEY(user_id, product_id))''')
cursor.execute('''CREATE TABLE IF NOT EXISTS courses
                  (type TEXT PRIMARY KEY, description TEXT, price_som INTEGER)''')
cursor.execute('''CREATE TABLE IF NOT EXISTS settings
                  (key TEXT PRIMARY KEY, value TEXT)''')
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
    add_product_price_som = State()
    add_product_price_usd = State()
    edit_course_type = State()
    edit_course_desc = State()
    edit_course_price = State()
    set_admin_info = State()
    set_card_number = State()
    set_location = State()

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
        [KeyboardButton(text="🎓 Kurs taxrirlash")],
        [KeyboardButton(text="👤 Admin ma'lumotlari"), KeyboardButton(text="💳 Karta raqami")],
        [KeyboardButton(text="📍 Manzil")],
        [KeyboardButton(text="🔙 Asosiy menyuga qaytish")]
    ],
    resize_keyboard=True
)

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
        cursor.execute("""SELECT p.name, p.price_som, c.quantity
                          FROM cart c JOIN products p ON c.product_id = p.id WHERE c.user_id=?""", (user_id,))
        items = cursor.fetchall()
        if not items:
            await message.answer("🛒 Savatchangiz bo'sh.", reply_markup=menu)
            return
        total = sum(price * qty for _, price, qty in items)
        msg_text = "<b>Savatchangiz:</b>\n\n" + "\n".join(f"• {name} × {qty} = {price*qty:,} so'm" for name, price, qty in items)
        msg_text += f"\n\n<b>Jami: {total:,} so'm</b>"
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

# ==================== ADMIN PANEL – BARCHA TUGMALAR ISHLAYDI ====================
@dp.message(lambda m: m.text == "📂 Kategoriya qo'shish" and m.from_user.id == ADMIN_ID)
async def add_category(message: types.Message, state: FSMContext):
    await message.answer("Yangi kategoriya nomini yozing:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.add_category_name)

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
    await message.answer("Narxni so'mda yozing:")
    await state.set_state(AdminStates.add_product_price_som)

@dp.message(AdminStates.add_product_price_som)
async def add_product_price_som(message: types.Message, state: FSMContext):
    try:
        price = int(message.text.strip().replace(" ", ""))
        await state.update_data(price_som=price)
        await message.answer("Narxni USDda yozing (bo'sh qoldirsangiz 0):")
        await state.set_state(AdminStates.add_product_price_usd)
    except ValueError:
        await message.answer("Raqam kiriting!")

@dp.message(AdminStates.add_product_price_usd)
async def add_product_price_usd(message: types.Message, state: FSMContext):
    text = message.text.strip().replace(" ", "")
    price_usd = float(text) if text else 0.0
    data = await state.get_data()
    cursor.execute("""INSERT INTO products
                      (category_id, name, description, code, price_som, price_usd, photo)
                      VALUES (?, ?, ?, ?, ?, ?, ?)""",
                   (data['cat_id'], data['name'], data['desc'], data['code'],
                    data['price_som'], price_usd, data.get('photo')))
    conn.commit()
    await message.answer("✅ Maxsulot muvaffaqiyatli qo'shildi!", reply_markup=admin_panel_menu)
    await state.clear()

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

@dp.message(lambda m: m.text == "🔙 Asosiy menyuga qaytish" and m.from_user.id == ADMIN_ID)
async def back_to_main(message: types.Message):
    await message.answer("Asosiy menyuga qaytdingiz.", reply_markup=admin_menu)

# ==================== QOLGAN CALLBACK VA HANDLERLAR ====================
@dp.callback_query(lambda c: c.data.startswith("cat_"))
async def show_products(callback: types.CallbackQuery):
    cat_id = int(callback.data.split("_")[1])
    cursor.execute("SELECT id, name, description, code, price_som, price_usd, photo FROM products WHERE category_id=?", (cat_id,))
    products = cursor.fetchall()
    menu = admin_menu if callback.from_user.id == ADMIN_ID else main_menu
    if not products:
        await callback.message.answer("Bu kategoriyada maxsulot yo'q.", reply_markup=menu)
        await callback.answer()
        return
    for p in products:
        pid, name, desc, code, price_som, price_usd, photo = p
        text = f"<b>{name}</b>\n{desc}\nKod: {code}\nNarx: {price_som:,} so'm"
        if price_usd:
            text += f" (~{price_usd} USD)"
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

@dp.callback_query(lambda c: c.data == "confirm_order")
async def confirm_order(callback: types.CallbackQuery, state: FSMContext):
    user_id = callback.from_user.id
    cursor.execute("SELECT SUM(p.price_som * c.quantity) FROM cart c JOIN products p ON c.product_id=p.id WHERE c.user_id=?", (user_id,))
    total = cursor.fetchone()[0] or 0
    cursor.execute("SELECT value FROM settings WHERE key='card_number'")
    card_row = cursor.fetchone()
    card = card_row[0] if card_row else "9860 0000 0000 0000"
    menu = admin_menu if user_id == ADMIN_ID else main_menu
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
async def ask_phone(callback: types.CallbackQuery):
    kb = ReplyKeyboardMarkup(
        keyboard=[[KeyboardButton(text="📞 Raqam yuborish", request_contact=True)]],
        resize_keyboard=True,
        one_time_keyboard=True
    )
    await callback.message.answer("Telefon raqamingizni yuboring:", reply_markup=kb)
    await callback.answer()

@dp.message(lambda m: m.contact)
async def final_order(message: types.Message):
    cursor.execute("SELECT value FROM settings WHERE key='admin_info'")
    info_row = cursor.fetchone()
    info = info_row[0] if info_row else "Admin bilan bog'laning"
    menu = admin_menu if message.from_user.id == ADMIN_ID else main_menu
    await message.answer(f"✅ Buyurtmangiz qabul qilindi!\n\n{info}", reply_markup=menu)
    cursor.execute("DELETE FROM cart WHERE user_id=?", (message.from_user.id,))
    conn.commit()

@dp.message(CartStates.waiting_screenshot)
async def cart_screenshot(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("Faqat rasm (screenshot) yuboring.")
        return
    await bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    menu = admin_menu if message.from_user.id == ADMIN_ID else main_menu
    await message.answer("📸 Screenshot adminga yuborildi. Tasdiqlashini kuting...", reply_markup=menu)
    await state.clear()

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

@dp.message(CourseStates.waiting_screenshot)
async def course_screenshot(message: types.Message, state: FSMContext):
    if not message.photo:
        await message.answer("Faqat rasm yuboring.")
        return
    await bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    menu = admin_menu if message.from_user.id == ADMIN_ID else main_menu
    await message.answer("📸 Screenshot adminga yuborildi. Tasdiqlash kutilmoqda.", reply_markup=menu)
    await state.clear()

# ==================== BOT ISHGA TUSHIRISH ====================
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
