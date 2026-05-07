import asyncio
import logging
import sqlite3
import re
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, CommandObject, Command, StateFilter
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
import aiohttp
from aiohttp import web
import os
from dotenv import load_dotenv

load_dotenv()

# --- SOZLAMALAR ---
TOKEN = os.getenv("TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID"))
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CHANNEL_URL = os.getenv("CHANNEL_URL")

logging.basicConfig(level=logging.INFO)

# Global o'zgaruvchilar
bot = None
dp = Dispatcher()
bot_info = None

# Baza
db = sqlite3.connect("movies.db")
cursor = db.cursor()
cursor.execute("CREATE TABLE IF NOT EXISTS movies (movie_id INTEGER PRIMARY KEY, message_id INTEGER)")
cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
db.commit()

# FSM holatlari
class MovieUpload(StatesGroup):
    waiting_for_video = State()
    waiting_for_caption = State()

def add_user(user_id):
    cursor.execute("INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,))
    db.commit()

async def check_sub(user_id):
    try:
        member = await bot.get_chat_member(CHANNEL_ID, user_id)
        logging.info(f"👤 Foydalanuvchi {user_id} holati: {member.status}")
        return member.status in ["member", "administrator", "creator"]
    except Exception as e:
        logging.error(f"⚠️ OBUNA TEKSHIRISHDA XATO: {e}")
        return False

def get_msg_id(text):
    if not text: return None
    match = re.search(r"/(\d+)(?:\?|/|$)", text)
    if match:
        return int(match.group(1))
    return None

@dp.message(CommandStart())
async def start_cmd(message: types.Message, command: CommandObject):
    user_id = message.from_user.id
    add_user(user_id)
    logging.info(f"🚀 START: Foydalanuvchi {user_id}, Args: {command.args}")
    
    is_subscribed = await check_sub(user_id)
    if not is_subscribed:
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="Kanalga a'zo bo'lish", url=CHANNEL_URL))
        
        start_link = f"https://t.me/{bot_info.username}"
        if command.args:
            start_link += f"?start={command.args}"
        
        builder.row(types.InlineKeyboardButton(text="Tekshirish", url=start_link))
        await message.answer("❌ Botdan foydalanish uchun kanalimizga a'zo bo'lishingiz kerak!", reply_markup=builder.as_markup())
        return

    if command.args and command.args.isdigit():
        movie_number = int(command.args)
        cursor.execute("SELECT message_id FROM movies WHERE movie_id = ?", (movie_number,))
        result = cursor.fetchone()
        if result:
            try:
                await bot.copy_message(chat_id=user_id, from_chat_id=CHANNEL_ID, message_id=result[0])
                return
            except Exception as e:
                await message.answer(f"Xatolik: Bot kanalda admin emas! {e}")
                return
    await message.answer("Salom! Kino raqamini yuboring. 🎬")

@dp.message(F.text.isdigit())
async def movie_request_handler(message: types.Message):
    user_id = message.from_user.id
    text = message.text
    add_user(user_id)
    
    is_subscribed = await check_sub(user_id)
    if not is_subscribed:
        builder = InlineKeyboardBuilder()
        builder.row(types.InlineKeyboardButton(text="Kanalga a'zo bo'lish", url=CHANNEL_URL))
        start_link = f"https://t.me/{bot_info.username}?start={text}"
        builder.row(types.InlineKeyboardButton(text="Tekshirish", url=start_link))
        await message.answer("❌ Botdan foydalanish uchun kanalimizga a'zo bo'lishingiz kerak!", reply_markup=builder.as_markup())
        return

    num = int(text)
    cursor.execute("SELECT message_id FROM movies WHERE movie_id = ?", (num,))
    res = cursor.fetchone()
    if res:
        try:
            await bot.copy_message(chat_id=user_id, from_chat_id=CHANNEL_ID, message_id=res[0])
        except Exception as e:
            await message.answer(f"❌ Xatolik: {e}")
    else:
        await message.answer(f"❓ Bazadan `{num}` topilmadi.")

@dp.message(F.from_user.id == ADMIN_ID, F.video | F.document)
async def admin_video_handler(message: types.Message, state: FSMContext):
    file_id = message.video.file_id if message.video else message.document.file_id
    file_type = "video" if message.video else "document"
    await state.update_data(file_id=file_id, file_type=file_type)
    await state.set_state(MovieUpload.waiting_for_caption)
    await message.answer("🎬 Video qabul qilindi! Endi kino uchun **tavsif** yuboring.")

@dp.message(F.from_user.id == ADMIN_ID, MovieUpload.waiting_for_caption)
async def admin_caption_handler(message: types.Message, state: FSMContext):
    data = await state.get_data()
    file_id, file_type = data['file_id'], data['file_type']
    caption = message.text or message.caption
    try:
        if file_type == "video":
            sent_msg = await bot.send_video(chat_id=CHANNEL_ID, video=file_id, caption=caption)
        else:
            sent_msg = await bot.send_document(chat_id=CHANNEL_ID, document=file_id, caption=caption)
        
        cursor.execute("SELECT MAX(movie_id) FROM movies")
        last_id = cursor.fetchone()[0]
        new_id = 101 if (last_id is None or last_id < 100) else last_id + 1
        cursor.execute("INSERT INTO movies (movie_id, message_id) VALUES (?, ?)", (new_id, sent_msg.message_id))
        db.commit()
        
        link = f"https://t.me/{bot_info.username}?start={new_id}"
        await message.answer(f"✅ Yuklandi! Raqami: `{new_id}`\n🔗 {link}")
    except Exception as e:
        await message.answer(f"❌ Xatolik: {e}")
    await state.clear()

@dp.message(F.from_user.id == ADMIN_ID, F.forward_from_chat | F.text.contains("t.me/") | F.caption.contains("t.me/"))
async def admin_link_handler(message: types.Message):
    msg_id = None
    if message.forward_from_chat and message.forward_from_chat.id == CHANNEL_ID:
        msg_id = message.forward_from_message_id
    elif message.text or message.caption:
        msg_id = get_msg_id((message.text or message.caption).strip())

    if msg_id:
        cursor.execute("SELECT MAX(movie_id) FROM movies")
        last_id = cursor.fetchone()[0]
        new_id = 101 if (last_id is None or last_id < 100) else last_id + 1
        cursor.execute("INSERT INTO movies (movie_id, message_id) VALUES (?, ?)", (new_id, msg_id))
        db.commit()
        link = f"https://t.me/{bot_info.username}?start={new_id}"
        await message.answer(f"✅ Saqlandi! Raqam: `{new_id}`\n🔗 {link}")

@dp.message(Command("stat"), F.from_user.id == ADMIN_ID)
async def stat_cmd(message: types.Message):
    cursor.execute("SELECT COUNT(user_id) FROM users")
    await message.answer(f"📊 Foydalanuvchilar: {cursor.fetchone()[0]} ta")

@dp.message(Command("send"), F.from_user.id == ADMIN_ID)
async def send_cmd(message: types.Message):
    if not message.reply_to_message:
        await message.answer("❌ Xabarga reply qiling.")
        return
    cursor.execute("SELECT user_id FROM users")
    users = cursor.fetchall()
    await message.answer("🚀 Boshlandi...")
    for user in users:
        try:
            await bot.copy_message(chat_id=user[0], from_chat_id=message.chat.id, message_id=message.reply_to_message.message_id)
            await asyncio.sleep(0.05)
        except Exception: pass
    await message.answer("✅ Tugadi!")

async def health_check(request):
    return web.Response(text="Bot is running!")

async def main():
    global bot_info, bot
    
    # Render uchun kichik web server (Web Service o'chib qolmasligi uchun)
    app = web.Application()
    app.router.add_get("/", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", int(os.getenv("PORT", 8080)))
    asyncio.create_task(site.start())
    
    while True:
        try:
            bot = Bot(token=TOKEN)
            bot_info = await bot.get_me()
            logging.info(f"Bot ishga tushdi: @{bot_info.username}")
            await dp.start_polling(bot)
            break
        except Exception as e:
            logging.error(f"Xatolik: {e}")
            await asyncio.sleep(5)

if __name__ == "__main__":
    asyncio.run(main())
