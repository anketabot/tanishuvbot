import asyncio
import json
import logging
import os
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton,
    WebAppInfo
)
from aiogram.utils.keyboard import InlineKeyboardBuilder
from aiogram.fsm.storage.memory import MemoryStorage
from aiohttp import web

import database as db
from config import BOT_TOKEN, WEBAPP_URL, ADMIN_PASSWORD

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

search_sessions = {}
pending_message_targets = {}


def main_menu_keyboard():
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🌐 Web App", web_app=WebAppInfo(url=f"{WEBAPP_URL}/index.html"))],
        [InlineKeyboardButton(text="👤 Mening anketam", callback_data="show_profile")],
        [InlineKeyboardButton(text="🔎 Qidirish", callback_data="start_search")],
    ])
    return keyboard


def format_user_card(user):
    gender_icon = "👨" if user.get("gender") == "erkak" else "👩"
    zodiac_text = user.get("zodiac") or "ko'rsatilmagan"

    return (
        f"{gender_icon} *{user['full_name']}*\n"
        f"🎂 Yosh: {user['age']}\n"
        f"📍 Shahar: {user['city']}\n"
        f"⭐ Burj: {zodiac_text}"
    )


async def send_candidate_card(message, user):
    text = format_user_card(user)

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❤️ Like", callback_data=f"like_{user['telegram_id']}"),
        InlineKeyboardButton(text="🚫 Blok", callback_data=f"block_{user['telegram_id']}")
    )
    builder.row(
        InlineKeyboardButton(text="✉️ Yozish", callback_data=f"write_{user['telegram_id']}")
    )

    if user.get("photo_file_id"):
        await message.answer_photo(
            user["photo_file_id"],
            caption=text,
            parse_mode="Markdown",
            reply_markup=builder.as_markup()
        )
    else:
        await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())


async def show_search_candidate(chat, user_id, index):
    session = search_sessions.get(user_id, {})
    users = session.get('users', [])
    if not users:
        await chat.answer('😔 Hech qanday nomzod topilmadi.')
        return

    if index >= len(users):
        await chat.answer('✅ Barcha nomzodlar ko\'rib chiqildi. Qayta qidirish uchun menyudan yana urinib ko\'ring.')
        search_sessions.pop(user_id, None)
        return

    user = users[index]
    text = format_user_card(user)
    text += f"\n\n🔎 {index + 1}/{len(users)} ta nomzoddan hozirgi"

    builder = InlineKeyboardBuilder()
    builder.row(
        InlineKeyboardButton(text="❤️ Like", callback_data=f"search_like:{user['telegram_id']}"),
        InlineKeyboardButton(text="⭐ Super Like", callback_data=f"search_super_like:{user['telegram_id']}")
    )
    builder.row(
        InlineKeyboardButton(text="❌ O'tkazib yuborish", callback_data="search_skip"),
        InlineKeyboardButton(text="💬 Xabar", callback_data=f"search_message:{user['telegram_id']}")
    )
    builder.row(
        InlineKeyboardButton(text="⬅ Asosiy menyu", callback_data="show_main_menu")
    )

    photo_id = user.get('photo_file_id')
    if photo_id:
        try:
            await chat.answer_photo(
                photo=photo_id,
                caption=text,
                parse_mode='Markdown',
                reply_markup=builder.as_markup()
            )
        except Exception as e:
            logger.error(f"Photo send error: {e}")
            await chat.answer(text, parse_mode='Markdown', reply_markup=builder.as_markup())
    else:
        await chat.answer(text, parse_mode='Markdown', reply_markup=builder.as_markup())


@dp.message(CommandStart())
async def start_handler(message: types.Message):
    args = message.text.split()
    telegram_id = message.from_user.id

    # Referral tekshirish (yangi tizim)
    if len(args) > 1 and args[1].startswith("ref_"):
        try:
            referrer_id = int(args[1].replace("ref_", ""))
            if referrer_id != telegram_id:
                success, msg = await db.process_referral(referrer_id, telegram_id)
                if success:
                    await bot.send_message(referrer_id, f"🎉 Yangi foydalanuvchi siz orqali qo'shildi!\n{msg}")
        except Exception as e:
            logger.error(f"Referral error: {e}")

    user = await db.get_user(telegram_id)

    await message.answer(
        f"👋 Assalomu alaykum, {message.from_user.first_name}!\n\n"
        "💙 *Do'stlik & Tanishuv Botiga xush kelibsiz!*\n\n"
        "Bu yerda siz yangi do'stlar topishingiz, muloqot qilishingiz mumkin.\n\n"
        "📋 *Kunlik limitlar:*\n"
        "• Like: 25 ta\n"
        "• Xabar yuborish: 25 ta\n"
        "• Super Like: 10 ta\n\n"
        "🌐 Web App orqali boshlang!",
        parse_mode="Markdown",
        reply_markup=main_menu_keyboard()
    )


@dp.message(F.text == "👤 Mening anketam")
async def my_profile(message: types.Message):
    user = await db.get_user(message.from_user.id)
    if not user:
        await message.answer("❌ Siz hali anketa to'ldirmagansiz. Iltimos, avval anketangizni to'ldiring.")
        return

    gender_icon = "👨" if user["gender"] == "erkak" else "👩"
    goals_text = ", ".join(user["goals"]) if user["goals"] else "ko'rsatilmagan"
    interests_text = ", ".join(user["interests"]) if user["interests"] else "ko'rsatilmagan"
    zodiac_text = user.get("zodiac") or "ko'rsatilmagan"

    # Limit status
    limit_status = await db.get_limit_status(message.from_user.id)
    if limit_status['unlimited']:
        limit_text = "\n✅ *Limitsiz foydalanish*"
    else:
        limit_text = f"\n📊 *Kunlik limitlar:*\n"
        limit_text += f"• Like: {limit_status['likes_used']}/25\n"
        limit_text += f"• Xabar: {limit_status['messages_used']}/25\n"
        limit_text += f"• Super Like: {limit_status['super_likes_used']}/10"

    text = (
        f"{gender_icon} *{user['full_name']}*\n"
        f"🎂 Yosh: {user['age']}\n"
        f"📍 Shahar: {user['city']}\n"
        f"⭐ Burj: {zodiac_text}\n"
        f"❤️ Maqsad: {goals_text}\n"
        f"🎯 Qiziqishlar: {interests_text}"
        f"{limit_text}"
    )

    if user.get("photo_file_id"):
        await message.answer_photo(user["photo_file_id"], caption=text, parse_mode="Markdown")
    else:
        await message.answer(text, parse_mode="Markdown")


@dp.callback_query(F.data == "start_search")
async def start_search_callback(callback: types.CallbackQuery):
    await callback.answer()

    builder = InlineKeyboardBuilder()
    builder.add(InlineKeyboardButton(text="👨 Erkak", callback_data="search_gender:erkak"))
    builder.add(InlineKeyboardButton(text="👩 Ayol", callback_data="search_gender:ayol"))
    builder.add(InlineKeyboardButton(text="🔄 Barchasi", callback_data="search_gender:all"))
    builder.add(InlineKeyboardButton(text="⬅ Orqaga", callback_data="show_main_menu"))

    await callback.message.answer(
        "Qidirish uchun kimni izlayapsiz?\n\n"
        "Erkak, ayol yoki barchasini tanlang.",
        reply_markup=builder.as_markup()
    )


@dp.callback_query(F.data.startswith("search_gender:"))
async def search_gender_callback(callback: types.CallbackQuery):
    await callback.answer("Qidirilmoqda...")

    gender_value = callback.data.split(":", 1)[1]
    filters = {}
    if gender_value != "all":
        filters["gender"] = gender_value

    users = await db.search_users(callback.from_user.id, filters)
    if not users:
        await callback.message.answer("😔 Hech kim topilmadi. Keyinroq yana urinib ko'ring.")
        return

    search_sessions[callback.from_user.id] = {'users': users, 'index': 0}
    await show_search_candidate(callback.message, callback.from_user.id, 0)


@dp.callback_query(F.data == 'search_skip')
async def search_skip_callback(callback: types.CallbackQuery):
    await callback.answer('Keyingi nomzodga o\'tkazildi')
    session = search_sessions.get(callback.from_user.id)
    if not session:
        await callback.message.answer('Qidiruv sessiyasi topilmadi. Qaytadan boshlang.')
        return

    index = session.get('index', 0) + 1
    session['index'] = index
    search_sessions[callback.from_user.id] = session
    await show_search_candidate(callback.message, callback.from_user.id, index)


@dp.callback_query(F.data.startswith('search_like:'))
async def search_like_callback(callback: types.CallbackQuery):
    to_user = int(callback.data.split(':', 1)[1])

    can_like = await db.check_and_increment_limit(callback.from_user.id, 'likes')
    if not can_like:
        await callback.answer('❌ Kunlik like limitingiz tugadi! 5 ta do\'st qo\'shganingizdan keyin 1 hafta, 10 ta bo\'lsa 1 oy limitsiz bo\'lasiz.', show_alert=True)
        return

    is_match = await db.add_like(callback.from_user.id, to_user)
    to_user_data = await db.get_user(to_user)
    my_data = await db.get_user(callback.from_user.id)

    if is_match and to_user_data and my_data:
        try:
            await bot.send_message(to_user, f"🎉 Match! {my_data['full_name']} ham sizni yoqtirdi!\n\nEndi muloqot boshlashingiz mumkin.")
            await callback.message.answer(f"🎉 Match! {to_user_data['full_name']} ham sizni yoqtirdi!\n\nEndi muloqot boshlashingiz mumkin.")
        except Exception:
            pass
    else:
        try:
            await bot.send_message(to_user, f"💌 {my_data['full_name']} sizni like qildi!\n\nWeb App'dagi Chat bo'limini tekshiring.")
        except Exception:
            pass
        await callback.answer('💙 Like yuborildi!', show_alert=False)

    await callback.answer('Like yuborildi!', show_alert=False)
    await _advance_search(callback)


@dp.callback_query(F.data.startswith('search_super_like:'))
async def search_super_like_callback(callback: types.CallbackQuery):
    to_user = int(callback.data.split(':', 1)[1])

    can_super = await db.check_and_increment_limit(callback.from_user.id, 'super_likes')
    if not can_super:
        await callback.answer('❌ Kunlik Super Like limitingiz tugadi! 5 ta do\'st qo\'shganingizdan keyin 1 hafta, 10 ta bo\'lsa 1 oy limitsiz bo\'lasiz.', show_alert=True)
        return

    is_match = await db.add_like(callback.from_user.id, to_user)
    await db.increment_super_like_usage(callback.from_user.id)
    to_user_data = await db.get_user(to_user)
    my_data = await db.get_user(callback.from_user.id)

    if is_match and to_user_data and my_data:
        try:
            await bot.send_message(to_user, f"⭐ Super Like Match! {my_data['full_name']} sizga Super Like bosdi!\n\nEndi muloqot boshlashingiz mumkin.")
            await callback.message.answer(f"⭐ Super Like Match! {to_user_data['full_name']} ham sizni yoqtirdi!\n\nEndi muloqot boshlashingiz mumkin.")
        except Exception:
            pass
    else:
        try:
            await bot.send_message(to_user, f"⭐ {my_data['full_name']} sizga Super Like bosdi!\n\nWeb App'dagi Chat bo'limini tekshiring.")
        except Exception:
            pass

    await callback.answer('⭐ Super Like yuborildi!', show_alert=False)
    await _advance_search(callback)


@dp.callback_query(F.data.startswith('search_message:'))
async def search_message_callback(callback: types.CallbackQuery):
    to_user = int(callback.data.split(':', 1)[1])
    can_write = await db.can_write(callback.from_user.id, to_user)
    if not can_write:
        await callback.answer('❌ Avval like yoki super like yuborish kerak.', show_alert=True)
        return

    pending_message_targets[callback.from_user.id] = to_user
    await callback.answer('Xabar matnini yuboring. Men uni jo\'nataman.', show_alert=True)
    await callback.message.answer('💬 Xabar matnini yozing. Bitta xabar yuboriladi.')


async def _advance_search(callback):
    session = search_sessions.get(callback.from_user.id)
    if not session:
        return

    index = session.get('index', 0) + 1
    session['index'] = index
    search_sessions[callback.from_user.id] = session
    await show_search_candidate(callback.message, callback.from_user.id, index)


@dp.callback_query(F.data == "show_main_menu")
async def show_main_menu_callback(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.answer("Asosiy menyu:", reply_markup=main_menu_keyboard())


@dp.callback_query(F.data == "show_profile")
async def show_profile_callback(callback: types.CallbackQuery):
    await callback.answer()
    user = await db.get_user(callback.from_user.id)
    if not user:
        await callback.message.answer("❌ Siz hali anketa to'ldirmagansiz. Iltimos, avval anketangizni to'ldiring.")
        return

    gender_icon = "👨" if user["gender"] == "erkak" else "👩"
    goals_text = ", ".join(user["goals"]) if user["goals"] else "ko'rsatilmagan"
    interests_text = ", ".join(user["interests"]) if user["interests"] else "ko'rsatilmagan"
    zodiac_text = user.get("zodiac") or "ko'rsatilmagan"

    # Limit status
    limit_status = await db.get_limit_status(callback.from_user.id)
    if limit_status['unlimited']:
        limit_text = "\n✅ *Limitsiz foydalanish*"
    else:
        limit_text = f"\n📊 *Kunlik limitlar:*\n"
        limit_text += f"• Like: {limit_status['likes_used']}/25\n"
        limit_text += f"• Xabar: {limit_status['messages_used']}/25\n"
        limit_text += f"• Super Like: {limit_status['super_likes_used']}/10"

    text = (
        f"{gender_icon} *{user['full_name']}*\n"
        f"🎂 Yosh: {user['age']}\n"
        f"📍 Shahar: {user['city']}\n"
        f"⭐ Burj: {zodiac_text}\n"
        f"❤️ Maqsad: {goals_text}\n"
        f"🎯 Qiziqishlar: {interests_text}"
        f"{limit_text}"
    )

    if user.get("photo_file_id"):
        await callback.message.answer_photo(user["photo_file_id"], caption=text, parse_mode="Markdown")
    else:
        await callback.message.answer(text, parse_mode="Markdown")


@dp.message()
async def handle_pending_message(message: types.Message):
    to_user = pending_message_targets.get(message.from_user.id)
    if not to_user:
        return

    text = message.text or ''
    if not text.strip():
        await message.answer('❌ Bo\'sh xabar jo\'natib bo\'lmaydi.')
        pending_message_targets.pop(message.from_user.id, None)
        return

    can_write = await db.can_write(message.from_user.id, to_user)
    if not can_write:
        await message.answer('❌ Avval like yuborish kerak!')
        pending_message_targets.pop(message.from_user.id, None)
        return

    can_msg = await db.check_and_increment_limit(message.from_user.id, 'messages')
    if not can_msg:
        await message.answer('❌ Kunlik xabar yuborish limitingiz tugadi! 5 ta do\'st qo\'shganingizdan keyin 1 hafta, 10 ta bo\'lsa 1 oy limitsiz bo\'lasiz.')
        pending_message_targets.pop(message.from_user.id, None)
        return

    match_id = await db.get_match_id(message.from_user.id, to_user)
    if not match_id:
        await message.answer('❌ Avval like yuborish kerak!')
        pending_message_targets.pop(message.from_user.id, None)
        return

    await db.send_chat_message(match_id, message.from_user.id, text.strip())
    await message.answer('✅ Xabar yuborildi!')

    to_user_data = await db.get_user(to_user)
    if to_user_data:
        try:
            await bot.send_message(to_user, f"💬 {message.from_user.first_name} dan yangi xabar:\n{text.strip()[:100]}")
        except Exception:
            pass

    pending_message_targets.pop(message.from_user.id, None)


@dp.message(F.web_app_data)
async def web_app_data_handler(message: types.Message):
    """WebApp dan kelgan ma'lumotlarni qabul qilish"""
    try:
        data = json.loads(message.web_app_data.data)
        action = data.get("action")

        if action == "save_profile":
            profile_data = data.get("profile", {})
            profile_data["username"] = message.from_user.username
            profile_data["telegram_id"] = message.from_user.id

            success = await db.save_user(message.from_user.id, profile_data)
            if success:
                await message.answer(
                    "✅ *Anketangiz muvaffaqiyatli saqlandi!*\n\nEndi qidirish orqali yangi do'stlar toping. 🔍",
                    parse_mode="Markdown",
                    reply_markup=main_menu_keyboard()
                )
            else:
                await message.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")

        elif action == "like_user":
            to_user = int(data.get("to_user"))

            # Limit tekshirish
            can_like = await db.check_and_increment_limit(message.from_user.id, 'likes')
            if not can_like:
                await message.answer(
                    "❌ Kunlik like limitingiz tugadi!\n\n"
                    "Guruhga 5 ta odam qo'shsangiz → 1 hafta limitsiz\n"
                    "Guruhga 10 ta odam qo'shsangiz → 1 oy limitsiz\n\n"
                    "Yoki ertaga yangi limit bilan davom etasiz."
                )
                return

            logger.info(f"Like action from {message.from_user.id} to {to_user}")
            is_match = await db.add_like(message.from_user.id, to_user)
            to_user_data = await db.get_user(to_user)
            my_data = await db.get_user(message.from_user.id)
            logger.info(f"Like result: is_match={is_match}, to_user_data={to_user_data is not None}, my_data={my_data is not None}")
            if is_match:
                if to_user_data and my_data:
                    await message.answer(
                        f"🎉 *Match! {to_user_data['full_name']} ham sizni yoqtirdi!*\n\nEndi muloqot boshlashingiz mumkin.",
                        parse_mode="Markdown"
                    )
                    try:
                        await bot.send_message(
                            to_user,
                            f"🎉 *Match! {my_data['full_name']} ham sizni yoqtirdi!*\n\nEndi muloqot boshlashingiz mumkin.",
                            parse_mode="Markdown"
                        )
                        logger.info(f"Match notification sent to {to_user}")
                    except Exception as e:
                        logger.error(f"Match notify error: {e}", exc_info=True)
                else:
                    await message.answer("🎉 Match bo'ldi! Endi muloqot qiling.")
            else:
                await message.answer("💙 Like yuborildi! Agar u ham sizni yoqtirsa, xabar beramiz.")
                if to_user_data and my_data:
                    try:
                        await bot.send_message(
                            to_user,
                            f"💌 *{my_data['full_name']}* sizni like qildi!\n\nWeb App'dagi Chat bo'limini tekshiring.",
                            parse_mode="Markdown"
                        )
                        logger.info(f"Like notification sent to {to_user} from {message.from_user.id}")
                    except Exception as e:
                        logger.error(f"Like notification error for user {to_user}: {e}", exc_info=True)
                else:
                    logger.warning(f"Could not send like notification: to_user_data={to_user_data}, my_data={my_data}")

        elif action == "super_like_user":
            to_user = int(data.get("to_user"))
            sticker = data.get("sticker", '')

            # Super Like limit tekshirish
            can_super = await db.check_and_increment_limit(message.from_user.id, 'super_likes')
            if not can_super:
                await message.answer(
                    "❌ Kunlik Super Like limitingiz tugadi!\n\n"
                    "Guruhga 5 ta odam qo'shsangiz → 1 hafta limitsiz\n"
                    "Guruhga 10 ta odam qo'shsangiz → 1 oy limitsiz\n\n"
                    "Yoki ertaga yangi limit bilan davom etasiz."
                )
                return

            is_match = await db.add_like(message.from_user.id, to_user)
            to_user_data = await db.get_user(to_user)
            my_data = await db.get_user(message.from_user.id)

            if is_match:
                if to_user_data and my_data:
                    try:
                        await bot.send_message(
                            to_user,
                            f"⭐ *Super Like Match!* {my_data['full_name']} sizga Super Like bosdi!\n\nEndi muloqot boshlashingiz mumkin.",
                            parse_mode="Markdown"
                        )
                        await message.answer(
                            f"🎉 *Super Like Match!* {to_user_data['full_name']} ham sizni yoqtirdi!\n\nEndi muloqot boshlashingiz mumkin.",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Super Like Match notify error: {e}")
            else:
                if to_user_data and my_data:
                    try:
                        await bot.send_message(
                            to_user,
                            f"⭐ *{my_data['full_name']}* sizga Super Like bosdi!\n\nWeb App'dagi Chat bo'limini tekshiring.",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Super Like notify error: {e}")
                await message.answer("⭐ Super Like yuborildi!")

        elif action == "block_user":
            blocked_id = int(data.get("blocked_id"))
            await db.block_user(message.from_user.id, blocked_id)
            await message.answer("🚫 Foydalanuvchi bloklandi.")

        elif action == "send_message":
            to_user = int(data.get("to_user"))
            message_text = data.get("message", '').strip()

            # Message limit tekshirish
            can_msg = await db.check_and_increment_limit(message.from_user.id, 'messages')
            if not can_msg:
                await message.answer(
                    "❌ Kunlik xabar yuborish limitingiz tugadi!\n\n"
                    "Guruhga 5 ta odam qo'shsangiz → 1 hafta limitsiz\n"
                    "Guruhga 10 ta odam qo'shsangiz → 1 oy limitsiz\n\n"
                    "Yoki ertaga yangi limit bilan davom etasiz."
                )
                return

            # Chat yuborish logikasi
            match_id = await db.get_match_id(message.from_user.id, to_user)
            if match_id:
                await db.send_chat_message(match_id, message.from_user.id, message_text)
                await message.answer("✅ Xabar yuborildi!")
                to_user_data = await db.get_user(to_user)
                if to_user_data:
                    try:
                        await bot.send_message(
                            to_user,
                            f"💬 *{message.from_user.first_name}* dan yangi xabar:\n{message_text[:100]}",
                            parse_mode="Markdown"
                        )
                    except Exception as e:
                        logger.error(f"Message notify error: {e}")
            else:
                await message.answer("❌ Avval like yuborish kerak!")

        elif action == "search":
            filters = data.get("filters", {})
            users = await db.search_users(message.from_user.id, filters)
            if not users:
                await message.answer("😔 Qidiruv bo'yicha hech kim topilmadi. Filtrlarni o'zgartiring.")
                return

            for u in users[:5]:
                gender_icon = "👨" if u["gender"] == "erkak" else "👩"
                goals_text = ", ".join(u["goals"]) if u["goals"] else "—"
                interests_text = ", ".join(u["interests"]) if u["interests"] else "—"

                text = (
                    f"{gender_icon} *{u['full_name']}*\n"
                    f"🎂 Yosh: {u['age']}\n"
                    f"📍 Shahar: {u['city']}\n"
                    f"❤️ Maqsad: {goals_text}\n"
                    f"🎯 Qiziqishlar: {interests_text}"
                )

                builder = InlineKeyboardBuilder()
                builder.add(InlineKeyboardButton(text="❤️ Like", callback_data=f"like_{u['telegram_id']}"))
                builder.add(InlineKeyboardButton(text="🚫 Blok", callback_data=f"block_{u['telegram_id']}"))
                builder.add(InlineKeyboardButton(text="✉️ Yozish", callback_data=f"write_{u['telegram_id']}"))

                if u.get("photo_file_id"):
                    await message.answer_photo(
                        u["photo_file_id"],
                        caption=text,
                        parse_mode="Markdown",
                        reply_markup=builder.as_markup()
                    )
                else:
                    await message.answer(text, parse_mode="Markdown", reply_markup=builder.as_markup())

    except Exception as e:
        logger.error(f"WebApp data error: {e}")
        await message.answer("❌ Xatolik yuz berdi.")


@dp.callback_query(F.data.startswith("like_"))
async def like_callback(callback: types.CallbackQuery):
    to_user = int(callback.data.replace("like_", ""))

    # Limit tekshirish
    can_like = await db.check_and_increment_limit(callback.from_user.id, 'likes')
    if not can_like:
        await callback.answer("❌ Kunlik like limitingiz tugadi!", show_alert=True)
        return

    is_match = await db.add_like(callback.from_user.id, to_user)
    if is_match:
        to_user_data = await db.get_user(to_user)
        my_data = await db.get_user(callback.from_user.id)
        await callback.message.answer(f"🎉 Match! {to_user_data['full_name']} ham sizni yoqtirdi!")
        await bot.send_message(to_user, f"🎉 Match! {my_data['full_name']} ham sizni yoqtirdi!")
    else:
        await callback.answer("💙 Like yuborildi!", show_alert=False)


@dp.callback_query(F.data.startswith("block_"))
async def block_callback(callback: types.CallbackQuery):
    blocked_id = int(callback.data.replace("block_", ""))
    await db.block_user(callback.from_user.id, blocked_id)
    await callback.answer("🚫 Bloklandi", show_alert=True)


@dp.callback_query(F.data.startswith("write_"))
async def write_callback(callback: types.CallbackQuery):
    to_user = int(callback.data.replace("write_", ""))
    can = await db.can_write(callback.from_user.id, to_user)
    if can:
        to_user_data = await db.get_user(to_user)
        username = to_user_data.get("username")
        if username:
            await callback.answer(f"@{username} ga yozishingiz mumkin!", show_alert=True)
        else:
            await callback.answer("Bu foydalanuvchining username yo'q.", show_alert=True)
    else:
        await callback.answer("❌ Avval like yuborish kerak!", show_alert=True)


# ========== HTTP API ==========

def serialize_value(value):
    if isinstance(value, (list, tuple)):
        return [serialize_value(v) for v in value]
    if hasattr(value, 'isoformat'):
        return value.isoformat()
    return value


def serialize_user(user):
    clean_user = {}
    for key, value in user.items():
        clean_user[key] = serialize_value(value)
    return clean_user


@web.middleware
async def cors_middleware(request, handler):
    if request.method == 'OPTIONS':
        return web.Response(
            text='',
            status=200,
            headers={
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, PUT, DELETE, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization',
                'Access-Control-Max-Age': '86400',
            }
        )

    response = await handler(request)
    response.headers['Access-Control-Allow-Origin'] = '*'
    response.headers['Access-Control-Allow-Methods'] = 'GET, POST, PUT, DELETE, OPTIONS'
    response.headers['Access-Control-Allow-Headers'] = 'Content-Type, Authorization'
    return response


async def search_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        filters = data.get('filters', {})
        if telegram_id is None:
            telegram_id = 0
        users = await db.search_users(int(telegram_id), filters)
        clean_users = [serialize_user(u) for u in users]
        return web.json_response({'success': True, 'users': clean_users})
    except Exception as e:
        logger.error(f"SEARCH API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def profile_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if telegram_id is None:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)
        user = await db.get_user(int(telegram_id))
        if user:
            return web.json_response({'success': True, 'user': serialize_user(user)})
        return web.json_response({'success': True, 'user': None})
    except Exception as e:
        logger.error(f"PROFILE API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def save_profile_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        profile = data.get('profile', {})
        if telegram_id is None:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)
        if not profile:
            return web.json_response({'success': False, 'error': 'profile required'}, status=400)
        profile['telegram_id'] = int(telegram_id)
        profile['username'] = profile.get('username')
        success = await db.save_user(int(telegram_id), profile)
        return web.json_response({'success': success})
    except Exception as e:
        logger.error(f"SAVE PROFILE API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def admin_users_api(request):
    try:
        data = await request.json()
        if ADMIN_PASSWORD and data.get('admin_password') != ADMIN_PASSWORD:
            return web.json_response({'success': False, 'error': 'Unauthorized'}, status=403)
        users = await db.get_all_users()
        clean_users = [serialize_user(u) for u in users]
        return web.json_response({'success': True, 'users': clean_users})
    except Exception as e:
        logger.error(f"ADMIN USERS API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def admin_analytics_api(request):
    try:
        data = await request.json()
        if ADMIN_PASSWORD and data.get('admin_password') != ADMIN_PASSWORD:
            return web.json_response({'success': False, 'error': 'Unauthorized'}, status=403)
        stats = await db.get_user_stats()
        top_cities = await db.get_top_cities(10)
        return web.json_response({'success': True, 'analytics': {
            'total': stats.get('total', 0),
            'male': stats.get('male', 0),
            'female': stats.get('female', 0),
            'avg_age': float(stats.get('avg_age')) if stats.get('avg_age') is not None else None,
            'top_cities': top_cities
        }})
    except Exception as e:
        logger.error(f"ADMIN ANALYTICS API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ========== CHAT API ENDPOINTS ==========

async def likes_received_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if not telegram_id:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)
        likes = await db.get_pending_likes(int(telegram_id))
        return web.json_response({'success': True, 'likes': [serialize_user(u) for u in likes]})
    except Exception as e:
        logger.error(f"LIKES RECEIVED API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def accept_like_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        from_user = data.get('from_user')
        if not telegram_id or not from_user:
            return web.json_response({'success': False, 'error': 'Missing params'}, status=400)

        match_id = await db.accept_like(int(telegram_id), int(from_user))
        if match_id:
            to_data = await db.get_user(int(telegram_id))
            from_data = await db.get_user(int(from_user))
            if to_data and from_data:
                try:
                    await bot.send_message(
                        int(from_user),
                        f"🎉 *{to_data['full_name']}* sizning like-ingizni qabul qildi!\n\n💬 Endi Web App'dagi Chat bo'limidan suhbat boshlashingiz mumkin.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Notify liker error: {e}")
                try:
                    await bot.send_message(
                        int(telegram_id),
                        f"✅ Siz *{from_data['full_name']}* bilan muloqotni boshladingiz!",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Notify accepter error: {e}")
            return web.json_response({'success': True, 'match_id': match_id})
        return web.json_response({'success': False, 'error': 'Like not found'}, status=404)
    except Exception as e:
        logger.error(f"ACCEPT LIKE API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def reject_like_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        from_user = data.get('from_user')
        if not telegram_id or not from_user:
            return web.json_response({'success': False, 'error': 'Missing params'}, status=400)

        rejected = await db.reject_like(int(telegram_id), int(from_user))
        if rejected:
            to_data = await db.get_user(int(telegram_id))
            from_data = await db.get_user(int(from_user))
            if to_data and from_data:
                try:
                    await bot.send_message(
                        int(from_user),
                        f"❌ *{to_data['full_name']}* sizni rad qildi.\n\nKeyinroq yana sinab ko'ring.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Notify reject error: {e}")
            return web.json_response({'success': True})
        return web.json_response({'success': False, 'error': 'Like topilmadi'}, status=404)
    except Exception as e:
        logger.error(f"REJECT LIKE API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def matches_api(request):
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if not telegram_id:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)
        matches = await db.get_matches(int(telegram_id))
        return web.json_response({'success': True, 'matches': [serialize_user(m) for m in matches]})
    except Exception as e:
        logger.error(f"MATCHES API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def chat_messages_api(request):
    try:
        data = await request.json()
        match_id = data.get('match_id')
        if not match_id:
            return web.json_response({'success': False, 'error': 'match_id required'}, status=400)
        messages = await db.get_chat_messages(int(match_id))
        return web.json_response({'success': True, 'messages': [serialize_user(m) for m in messages]})
    except Exception as e:
        logger.error(f"CHAT MESSAGES API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def send_chat_api(request):
    try:
        data = await request.json()
        match_id = data.get('match_id')
        sender_id = data.get('sender_id')
        message = data.get('message', '').strip()
        if not match_id or not sender_id or not message:
            return web.json_response({'success': False, 'error': 'Missing params'}, status=400)

        # Xabar yuborish limit tekshirish
        can_msg = await db.check_and_increment_limit(int(sender_id), 'messages')
        if not can_msg:
            return web.json_response({
                'success': False,
                'error': 'limit_exceeded',
                'message': 'Kunlik xabar yuborish limitingiz tugadi!'
            }, status=403)

        logger.info(f"Chat message from {sender_id} in match {match_id}: {message[:50]}")
        success = await db.send_chat_message(int(match_id), int(sender_id), message)
        if success:
            logger.info(f"Chat message saved successfully")
        return web.json_response({'success': success})
    except Exception as e:
        logger.error(f"SEND CHAT API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def can_write_api(request):
    try:
        data = await request.json()
        from_user = data.get('from_user')
        to_user = data.get('to_user')
        if from_user is None or to_user is None:
            return web.json_response({'success': False, 'error': 'Missing params'}, status=400)
        can = await db.can_write(int(from_user), int(to_user))
        return web.json_response({'success': True, 'can_write': can})
    except Exception as e:
        logger.error(f"CAN WRITE API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def initiate_chat_api(request):
    try:
        data = await request.json()
        from_user = data.get('from_user')
        to_user = data.get('to_user')
        if not from_user or not to_user:
            return web.json_response({'success': False, 'error': 'Missing params'}, status=400)

        can = await db.can_write(int(from_user), int(to_user))
        if not can:
            return web.json_response({'success': False, 'error': 'Unauthorized'}, status=403)

        match_id = await db.create_match(int(from_user), int(to_user))
        if match_id:
            return web.json_response({'success': True, 'match_id': match_id})
        return web.json_response({'success': False, 'error': 'Failed to create match'}, status=500)
    except Exception as e:
        logger.error(f"INITIATE CHAT API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def like_send_api(request):
    try:
        data = await request.json()
        from_user = data.get('from_user')
        to_user = data.get('to_user')
        super_like = bool(data.get('super_like', False))
        sticker = data.get('sticker', '')
        if not from_user or not to_user:
            return web.json_response({'success': False, 'error': 'Missing params'}, status=400)

        # Limit tekshirish
        limit_type = 'super_likes' if super_like else 'likes'
        can_use = await db.check_and_increment_limit(int(from_user), limit_type)
        if not can_use:
            return web.json_response({
                'success': False,
                'error': 'limit_exceeded',
                'message': f"Kunlik {limit_type} limitingiz tugadi!"
            }, status=403)

        is_match = await db.add_like(int(from_user), int(to_user))
        if super_like:
            await db.increment_super_like_usage(int(from_user))
        match_id = await db.get_match_id(int(from_user), int(to_user)) if is_match else None
        to_user_data = await db.get_user(int(to_user))
        from_user_data = await db.get_user(int(from_user))

        if is_match:
            if to_user_data and from_user_data:
                try:
                    super_like_label = "⭐ *Super Like Match!* " if super_like else "🎉 *Match!* "
                    super_like_note = f"\n\n{sticker} Bu super like edi." if super_like and sticker else ""
                    await bot.send_message(
                        int(to_user),
                        f"{super_like_label}{from_user_data['full_name']} sizga "
                        + ("Super Like bosdi!" if super_like else "ham sizni yoqtirdi!")
                        + super_like_note
                        + "\n\nEndi muloqot boshlashingiz mumkin.",
                        parse_mode="Markdown"
                    )
                    await bot.send_message(
                        int(from_user),
                        f"{super_like_label}{to_user_data['full_name']} ham sizni yoqtirdi!"
                        + (f"\n\n{sticker} Super Like yuborildi." if super_like and sticker else "")
                        + "\n\nEndi muloqot boshlashingiz mumkin.",
                        parse_mode="Markdown"
                    )
                except Exception as e:
                    logger.error(f"Match notify error: {e}")
            return web.json_response({'success': True, 'match': True, 'match_id': match_id, 'super_like': super_like})
        else:
            if to_user_data and from_user_data:
                try:
                    if super_like:
                        msg = (
                            f"⭐ *{from_user_data['full_name']}* sizga Super Like bosdi!"
                            + (f"\n\n{sticker} Bu super like edi." if sticker else "")
                            + "\n\nWeb App'dagi Chat bo'limini tekshiring."
                        )
                    else:
                        msg = (
                            f"💌 *{from_user_data['full_name']}* sizni like qildi!"
                            + "\n\nWeb App'dagi Chat bo'limini tekshiring."
                        )
                    await bot.send_message(int(to_user), msg, parse_mode="Markdown")
                    logger.info(f"Like notification sent to {to_user} from {from_user} (super_like={super_like})")
                except Exception as e:
                    logger.error(f"Like notification error for user {to_user}: {e}")
            return web.json_response({'success': True, 'match': False, 'match_id': None, 'super_like': super_like})
    except Exception as e:
        logger.error(f"LIKE SEND API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ========== LIMIT API ENDPOINTS ==========

async def limit_status_api(request):
    """Foydalanuvchining kunlik limit statusini olish"""
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if not telegram_id:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)
        status = await db.get_limit_status(int(telegram_id))
        return web.json_response({'success': True, 'limits': status})
    except Exception as e:
        logger.error(f"LIMIT STATUS API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


async def referral_status_api(request):
    """Foydalanuvchining referral statusini olish"""
    try:
        data = await request.json()
        telegram_id = data.get('telegram_id')
        if not telegram_id:
            return web.json_response({'success': False, 'error': 'telegram_id required'}, status=400)
        status = await db.get_referral_status(int(telegram_id))
        bot_info = await bot.get_me()
        status['referral_link'] = await db.get_referral_link(int(telegram_id), bot_info.username)
        return web.json_response({'success': True, 'referral': status})
    except Exception as e:
        logger.error(f"REFERRAL STATUS API xatolik: {e}", exc_info=True)
        return web.json_response({'success': False, 'error': str(e)}, status=500)


# ========== MAIN ==========

async def main():
    await db.init_db()
    logger.info("Bot ishga tushdi...")

    app = web.Application()
    app.middlewares.append(cors_middleware)

    app.router.add_post('/api/search', search_api)
    app.router.add_post('/api/profile', profile_api)
    app.router.add_post('/api/save_profile', save_profile_api)
    app.router.add_post('/api/admin/users', admin_users_api)
    app.router.add_post('/api/admin/analytics', admin_analytics_api)

    # Chat routes
    app.router.add_post('/api/likes/received', likes_received_api)
    app.router.add_post('/api/likes/send', like_send_api)
    app.router.add_post('/api/likes/accept', accept_like_api)
    app.router.add_post('/api/likes/reject', reject_like_api)
    app.router.add_post('/api/matches', matches_api)
    app.router.add_post('/api/chat/messages', chat_messages_api)
    app.router.add_post('/api/chat/send', send_chat_api)
    app.router.add_post('/api/can_write', can_write_api)
    app.router.add_post('/api/initiate_chat', initiate_chat_api)

    # Limit routes
    app.router.add_post('/api/limits/status', limit_status_api)
    app.router.add_post('/api/referral/status', referral_status_api)

    runner = web.AppRunner(app)
    await runner.setup()

    port = int(os.environ.get('PORT', 8080))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    logger.info(f"✅ HTTP API server started on port {port}")

    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
