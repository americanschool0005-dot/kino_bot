# Telegram Kino Bot 🎬

Bu bot kinolarni raqami orqali qidirish va ularni foydalanuvchilarga ulashish uchun mo'ljallangan.

## Imkoniyatlar:
- 📢 Majburiy obuna (Channel Check).
- 📂 Kinolarni raqam bo'yicha qidirish (101 dan boshlanadi).
- 🛠 Admin Panel (Video yuklash, Havola orqali saqlash).
- 📊 Statistika va Xabar tarqatish (Broadcast).

## O'rnatish:
1. Kutubxonalarni o'rnating:
   ```bash
   pip install aiogram python-dotenv aiohttp
   ```
2. `.env` faylini yarating va quyidagilarni kiriting:
   ```env
   TOKEN=Sizning_Bot_Tokeningiz
   ADMIN_ID=Sizning_IDingiz
   CHANNEL_ID=-100...
   CHANNEL_URL=https://t.me/...
   ```
3. Botni ishga tushiring:
   ```bash
   python bot.py
   ```
