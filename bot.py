import asyncio
import logging
import sqlite3
import os
from datetime import datetime
from aiohttp import web

from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    ReplyKeyboardMarkup, KeyboardButton,
    InlineKeyboardMarkup, InlineKeyboardButton,
    FSInputFile, ReplyKeyboardRemove, CallbackQuery
)

# ==================== SOZLAMALAR ====================
API_TOKEN = '8297594840:AAGjyGhsgaGWO0nQPX4mDvdmAN4BES9UVjY'
ADMIN_ID = 1063577925

bot = Bot(token=API_TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

logging.basicConfig(level=logging.INFO)

if not os.path.exists('photos'): os.makedirs('photos')

# ==================== BAZA BILAN ISHLASH ====================
conn = sqlite3.connect('bot.db', check_same_thread=False)
cursor = conn.cursor()

def init_db():
    cursor.execute('''CREATE TABLE IF NOT EXISTS categories (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT UNIQUE)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS products
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, category_id INTEGER, name TEXT, description TEXT,
                       code TEXT, price_som INTEGER, price_usd REAL, currency TEXT, photo TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS cart
                      (user_id INTEGER, product_id INTEGER, quantity INTEGER, PRIMARY KEY(user_id, product_id))''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS courses
                      (type TEXT PRIMARY KEY, description TEXT, price_som INTEGER)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS enrollments
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, fish TEXT, course_type TEXT, amount REAL, date TEXT)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS orders
                      (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, total_som REAL, date TEXT)''')
    # Standart sozlamalar
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('usd_rate', '12800')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('admin_info', 'Tel: +998901234567 | @admin_user')")
    cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('card_number', '8600 0000 0000 0000')")
    conn.commit()

init_db()

# ==================== FSM STATES ====================
class AdminStates(StatesGroup):
    add_category = State()
    usd_rate = State()
    admin_info = State()
    card_number = State()
    location = State()
    add_product = State() # Bu yerda bir nechta kichik qadamlar ishlatiladi
    edit_course = State()

class UserStates(StatesGroup):
    waiting_fish = State()
    waiting_payment_proof = State()

# ==================== YORDAMCHI FUNKSIYALAR ====================
def get_setting(key):
    cursor.execute("SELECT value FROM settings WHERE key=?", (key,))
    row = cursor.fetchone()
    return row[0] if row else ""

def get_usd_rate():
    return float(get_setting('usd_rate'))

# ==================== MENYULAR ====================
def get_main_menu(uid):
    kb = [
        [KeyboardButton(text="MAXSULOTLAR"), KeyboardButton(text="SAVATCHA")],
        [KeyboardButton(text="O'QUV KURS YANGILIKLARI"), KeyboardButton(text="BIZ BILAN BOG'LANISH")],
        [KeyboardButton(text="BIZNING MANZIL")]
    ]
    if uid == ADMIN_ID:
        kb.append([KeyboardButton(text="⚙️ SOZLAMALAR")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

admin_panel_kb = ReplyKeyboardMarkup(
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

# ==================== /START ====================
@dp.message(Command("start"))
async def cmd_start(message: types.Message):
    await message.answer("👑 Qirolicha botiga xush kelibsiz!", reply_markup=get_main_menu(message.from_user.id))

# ==================== MAXSULOTLAR ====================
@dp.message(F.text == "MAXSULOTLAR")
async def show_categories(message: types.Message):
    cursor.execute("SELECT id, name FROM categories")
    cats = cursor.fetchall()
    buttons = [[InlineKeyboardButton(text="🌟 BARCHA MAXSULOTLAR", callback_data="show_all")]]
    for cid, cname in cats:
        buttons.append([InlineKeyboardButton(text=cname, callback_data=f"viewcat_{cid}")])
    
    await message.answer("📂 Bo'limni tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=buttons))

@dp.callback_query(F.data == "show_all")
async def callback_show_all(callback: CallbackQuery):
    cursor.execute("SELECT * FROM products")
    prods = cursor.fetchall()
    await send_products(callback.message, prods)
    await callback.answer()

@dp.callback_query(F.data.startswith("viewcat_"))
async def callback_view_cat(callback: CallbackQuery):
    cat_id = callback.data.split("_")[1]
    cursor.execute("SELECT * FROM products WHERE category_id=?", (cat_id,))
    prods = cursor.fetchall()
    await send_products(callback.message, prods)
    await callback.answer()

async def send_products(message, prods):
    if not prods:
        await message.answer("Hozircha mahsulotlar yo'q.")
        return
    for p in prods:
        # p[0]:id, p[2]:name, p[3]:desc, p[5]:som, p[6]:usd, p[7]:curr, p[8]:photo
        price_str = f"{p[5]:,} so'm" if p[7] == "SOM" else f"${p[6]} (USD)"
        caption = f"<b>{p[2]}</b>\n\n{p[3]}\n\nNarxi: {price_str}\nKod: {p[4]}"
        kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="🛒 Savatchaga qo'shish", callback_data=f"addcart_{p[0]}") ]])
        
        if p[8] and os.path.exists(f"photos/{p[8]}"):
            await message.answer_photo(FSInputFile(f"photos/{p[8]}"), caption=caption, reply_markup=kb, parse_mode="HTML")
        else:
            await message.answer(caption, reply_markup=kb, parse_mode="HTML")

# ==================== SAVATCHA ====================
@dp.callback_query(F.data.startswith("addcart_"))
async def add_to_cart(callback: CallbackQuery):
    pid = int(callback.data.split("_")[1])
    uid = callback.from_user.id
    cursor.execute("INSERT INTO cart (user_id, product_id, quantity) VALUES (?, ?, 1) ON CONFLICT(user_id, product_id) DO UPDATE SET quantity = quantity + 1", (uid, pid))
    conn.commit()
    await callback.answer("Savatchaga qo'shildi!")

@dp.message(F.text == "SAVATCHA")
async def view_cart(message: types.Message):
    uid = message.from_user.id
    cursor.execute("""SELECT p.name, p.price_som, p.price_usd, p.currency, c.quantity FROM cart c 
                      JOIN products p ON c.product_id = p.id WHERE c.user_id=?""", (uid,))
    items = cursor.fetchall()
    if not items:
        await message.answer("Savatchangiz bo'sh.")
        return
    
    rate = get_usd_rate()
    total_som = 0
    msg = "🛒 <b>Savatchangiz:</b>\n\n"
    for name, p_som, p_usd, curr, qty in items:
        if curr == "USD":
            item_som = p_usd * rate * qty
            msg += f"• {name} | ${p_usd} x {qty} = 💵 ${p_usd*qty} ({(item_som):,.0f} so'm)\n"
            total_som += item_som
        else:
            item_som = p_som * qty
            msg += f"• {name} | {p_som:,} so'm x {qty} = 🇺🇿 {item_som:,} so'm\n"
            total_som += item_som
            
    msg += f"\n<b>Jami to'lov: {total_som:,.0f} so'm</b>"
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="💳 To'lov qilish", callback_data="checkout")],
        [InlineKeyboardButton(text="🗑 Savatni tozalash", callback_data="clear_savat")]
    ])
    await message.answer(msg, reply_markup=kb, parse_mode="HTML")

@dp.callback_query(F.data == "checkout")
async def checkout(callback: CallbackQuery, state: FSMContext):
    card = get_setting('card_number')
    await callback.message.answer(f"To'lov qilish uchun karta raqami:\n\n<code>{card}</code>\n\nTo'lovni amalga oshirib, screenshotni shu yerga yuboring.", parse_mode="HTML")
    await state.set_state(UserStates.waiting_payment_proof)
    await state.update_data(payment_for="product")
    await callback.answer()

# ==================== O'QUV KURSLARI ====================
@dp.message(F.text == "O'QUV KURS YANGILIKLARI")
async def kurs_news(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="Oddiy kurs", callback_data="kurs_reg_oddiy")],
        [InlineKeyboardButton(text="Master Klass", callback_data="kurs_reg_master")]
    ])
    await message.answer("🎓 Kurslarimiz haqida ma'lumot olish yoki yozilish uchun tanlang:", reply_markup=kb)

@dp.callback_query(F.data.startswith("kurs_reg_"))
async def kurs_reg(callback: CallbackQuery, state: FSMContext):
    ktype = callback.data.split("_")[2]
    cursor.execute("SELECT description, price_som FROM courses WHERE type=?", (ktype,))
    res = cursor.fetchone()
    desc = res[0] if res else "Hali ma'lumot kiritilmagan."
    price = res[1] if res else 0
    
    await callback.message.answer(f"🎓 <b>{ktype.upper()}</b>\n\n{desc}\n\nNarxi: {price:,} so'm\n\nRo'yxatdan o'tish uchun F.I.SH kiriting:")
    await state.set_state(UserStates.waiting_fish)
    await state.update_data(kurs_type=ktype, price=price)
    await callback.answer()

@dp.message(UserStates.waiting_fish)
async def process_fish(message: types.Message, state: FSMContext):
    await state.update_data(fish=message.text)
    card = get_setting('card_number')
    await message.answer(f"To'lovni amalga oshiring:\nKarta: <code>{card}</code>\n\nScreenshotni yuboring.", parse_mode="HTML")
    await state.set_state(UserStates.waiting_payment_proof)
    await state.update_data(payment_for="course")

# ==================== TO'LOV SCREENSHOTINI QABUL QILISH ====================
@dp.message(UserStates.waiting_payment_proof, F.photo)
async def handle_screenshot(message: types.Message, state: FSMContext):
    data = await state.get_data()
    await message.answer("📸 Screenshot qabul qilindi. Admin tasdiqlashini kuting.")
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ TASDIQLASH", callback_data=f"adm_confirm_{message.from_user.id}_{data['payment_for']}")]
    ])
    
    info_txt = f"💰 YANGI TO'LOV!\nKimdan: {message.from_user.full_name}\nNima uchun: {data['payment_for']}\n"
    if data['payment_for'] == "course":
        info_txt += f"Kurs: {data['kurs_type']}\nF.I.SH: {data['fish']}"
        
    await bot.send_photo(ADMIN_ID, message.photo[-1].file_id, caption=info_txt, reply_markup=kb)
    await state.clear()

# ==================== ADMIN TASDIQLASHI ====================
@dp.callback_query(F.data.startswith("adm_confirm_"))
async def admin_confirmation(callback: CallbackQuery):
    _, _, uid, p_for = callback.data.split("_")
    uid = int(uid)
    
    await bot.send_message(uid, "✅ Admin to'lovingizni tasdiqladi!")
    
    if p_for == "product":
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🚶 O'ZIM OLIB KETAMAN", callback_data="dlv_self")],
            [InlineKeyboardButton(text="🚚 YETKAZIB BERISH", callback_data="dlv_courier")]
        ])
        await bot.send_message(uid, "Yetkazib berish usulini tanlang:", reply_markup=kb)
    else:
        await bot.send_message(uid, "🎓 Siz o'quv kursiga muvaffaqiyatli ro'yxatga olindingiz! Yaqin orada siz bilan bog'lanamiz.")
        # Bu yerda bazaga saqlash mumkin
        
    await callback.message.edit_reply_markup(reply_markup=None)
    await callback.answer("Tasdiqlandi")

@dp.callback_query(F.data.startswith("dlv_"))
async def delivery_process(callback: CallbackQuery):
    loc = get_setting('location')
    adm = get_setting('admin_info')
    text = f"✅ QABUL QILINDI!\n\n📍 Manzil: {loc}\n☎️ Admin: {adm}\n\nXaridingizdan mamnunmiz!"
    await callback.message.answer(text, reply_markup=get_main_menu(callback.from_user.id))
    cursor.execute("DELETE FROM cart WHERE user_id=?", (callback.from_user.id,))
    conn.commit()
    await callback.answer()

# ==================== SOZLAMALAR (ADMIN) ====================
@dp.message(F.text == "⚙️ SOZLAMALAR", F.from_user.id == ADMIN_ID)
async def settings_main(message: types.Message):
    await message.answer("⚙️ Sozlamalar bo'limi:", reply_markup=admin_panel_kb)

@dp.message(F.text == "💱 Valyuta kursi", F.from_user.id == ADMIN_ID)
async def set_usd_state(message: types.Message, state: FSMContext):
    current = get_setting('usd_rate')
    await message.answer(f"Hozirgi kurs: 1 USD = {current} so'm\nYangi kursni raqamlarda kiriting:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.usd_rate)

@dp.message(AdminStates.usd_rate)
async def save_usd(message: types.Message, state: FSMContext):
    if message.text.isdigit():
        cursor.execute("UPDATE settings SET value=? WHERE key='usd_rate'", (message.text,))
        conn.commit()
        await message.answer("✅ Kurs yangilandi!", reply_markup=admin_panel_kb)
        await state.clear()
    else:
        await message.answer("Faqat raqam kiriting!")

# ==================== BIZNING MANZIL ====================
@dp.message(F.text == "BIZNING MANZIL")
async def show_loc(message: types.Message):
    loc = get_setting('location')
    await message.answer(f"📍 Bizning manzil:\n\n{loc}")

# ==================== ADMIN: MAXSULOT QO'SHISH ====================
@dp.message(F.text == "🛍 Maxsulot qo'shish", F.from_user.id == ADMIN_ID)
async def adm_add_p(message: types.Message, state: FSMContext):
    cursor.execute("SELECT id, name FROM categories")
    cats = cursor.fetchall()
    if not cats:
        await message.answer("Avval kategoriya qo'shing!")
        return
    kb = [[InlineKeyboardButton(text=c[1], callback_data=f"addpcat_{c[0]}")] for c in cats]
    await message.answer("Kategoriyani tanlang:", reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("addpcat_"))
async def adm_p_cat(callback: CallbackQuery, state: FSMContext):
    await state.update_data(cat_id=callback.data.split("_")[1])
    await callback.message.answer("Maxsulot rasmini yuboring:", reply_markup=ReplyKeyboardRemove())
    await state.set_state(AdminStates.add_product)
    await callback.answer()

# Qolgan admin funksiyalari (o'chirish, tahrirlash) yuqoridagi mantiq kabi davom etadi...

# ==================== WEB SERVER VA ISHGA TUSHURISH ====================
async def handle_web(request): return web.Response(text="Bot is online")

async def main():
    app = web.Application()
    app.router.add_get('/', handle_web)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '0.0.0.0', 8000)
    await site.start()
    await dp.start_polling(bot)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        logging.info("Bot stopped")
